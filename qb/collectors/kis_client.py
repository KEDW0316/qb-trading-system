"""
한국투자증권 API 클라이언트
Korean Investment Securities API Client

KIS API 기본 클라이언트 클래스 구현
공식 GitHub 참조: https://github.com/koreainvestment/open-trading-api
"""

import json
import time
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from utils.kis_auth import KISAuth


class KISClient:
    """한국투자증권 API 기본 클라이언트 클래스"""
    
    def __init__(self, mode: str = 'paper'):
        """
        KIS 클라이언트 초기화
        
        Args:
            mode: 'prod' (실전투자) 또는 'paper' (모의투자)
        """
        self.logger = logging.getLogger(__name__)
        self.mode = mode.lower()
        
        # KIS 인증 인스턴스 생성
        self.auth = KISAuth(mode=self.mode)
        
        # Rate limiting 관리
        self.request_times: List[float] = []
        self.max_requests_per_sec = 5  # 초당 최대 요청 수
        self.daily_request_count = 0
        self.last_request_day = datetime.now().day
        
        # 기본 타임아웃 설정
        self.default_timeout = 30
        
        self.logger.info(f"KISClient initialized in {self.mode} mode")
    
    async def _manage_rate_limit(self) -> None:
        """API 호출 속도 제한 관리"""
        now = time.time()
        
        # 1초 이내 요청들만 유지
        self.request_times = [t for t in self.request_times if now - t < 1.0]
        
        # 현재 초당 요청 수가 제한에 도달했으면 대기
        if len(self.request_times) >= self.max_requests_per_sec:
            wait_time = 1.0 - (now - self.request_times[0])
            if wait_time > 0:
                self.logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
        
        # 일일 요청 수 관리
        current_day = datetime.now().day
        if current_day != self.last_request_day:
            self.daily_request_count = 0
            self.last_request_day = current_day
        
        self.daily_request_count += 1
        
        # 현재 시간 기록
        self.request_times.append(time.time())
    
    async def request(
        self, 
        method: str, 
        endpoint: str, 
        tr_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None, 
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 3
    ) -> Any:
        """
        API 요청 공통 로직 (재시도, 에러 처리 포함)
        
        Args:
            method: HTTP 메소드 (GET, POST, PUT, DELETE)
            endpoint: API 엔드포인트
            tr_id: 거래ID (Transaction ID)
            params: URL 파라미터
            data: 요청 본문 데이터
            headers: 추가 헤더
            retry_count: 재시도 횟수
            
        Returns:
            API 응답 데이터
            
        Raises:
            Exception: API 요청 실패시
        """
        await self._manage_rate_limit()
        
        # 토큰 확인 및 갱신
        token = self.auth.get_token()
        
        # 요청 헤더 구성
        if tr_id:
            request_headers = self.auth.get_trading_headers(tr_id)
        else:
            request_headers = self.auth.get_auth_headers()
        
        if headers:
            request_headers.update(headers)
        
        url = f"{self.auth.base_url}{endpoint}"
        
        # 재시도 로직
        last_exception = None
        
        for attempt in range(retry_count):
            try:
                self.logger.debug(
                    f"Request {attempt + 1}/{retry_count}: {method} {url}"
                    f"{f' (TR_ID: {tr_id})' if tr_id else ''}"
                )
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.default_timeout)) as session:
                    request_kwargs = {
                        "headers": request_headers
                    }
                    
                    if params:
                        request_kwargs["params"] = params
                    
                    if data:
                        request_kwargs["json"] = data
                    
                    async with session.request(method, url, **request_kwargs) as response:
                        response_text = await response.text()
                        
                        self.logger.debug(
                            f"Response {response.status}: {response_text[:200]}..."
                        )
                        
                        if response.status == 200:
                            try:
                                return json.loads(response_text)
                            except json.JSONDecodeError:
                                return response_text
                        
                        elif response.status == 401:  # 인증 오류
                            self.logger.warning("Authentication error, refreshing token")
                            # 토큰 재발급 시도
                            try:
                                self.auth._current_token = None  # 현재 토큰 무효화
                                token = self.auth.get_token()  # 새 토큰 발급
                                # 헤더 업데이트
                                if tr_id:
                                    request_headers = self.auth.get_trading_headers(tr_id)
                                else:
                                    request_headers = self.auth.get_auth_headers()
                                if headers:
                                    request_headers.update(headers)
                            except Exception as e:
                                self.logger.error(f"Token refresh failed: {e}")
                            
                            if attempt < retry_count - 1:  # 마지막 시도가 아니면 재시도
                                continue
                        
                        # 기타 HTTP 오류
                        error_msg = f"HTTP {response.status}: {response_text}"
                        self.logger.error(error_msg)
                        last_exception = Exception(error_msg)
                        
                        if attempt < retry_count - 1:
                            continue
                        
            except asyncio.TimeoutError:
                error_msg = f"Request timeout after {self.default_timeout}s"
                self.logger.warning(error_msg)
                last_exception = Exception(error_msg)
                
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt  # 지수 백오프
                    self.logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                    
            except aiohttp.ClientError as e:
                error_msg = f"Client error: {str(e)}"
                self.logger.warning(error_msg)
                last_exception = Exception(error_msg)
                
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt  # 지수 백오프
                    self.logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                    
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                self.logger.error(error_msg)
                last_exception = Exception(error_msg)
                
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    self.logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
        
        # 모든 재시도 실패
        if last_exception:
            raise last_exception
        else:
            raise Exception(f"Request failed after {retry_count} attempts")
    
    @property
    def account_info(self) -> tuple:
        """계좌 정보 반환"""
        return self.auth.account_info
    
    @property
    def is_paper_trading(self) -> bool:
        """모의투자 여부"""
        return self.auth.is_paper_trading()
    
    def get_daily_request_count(self) -> int:
        """일일 요청 수 반환"""
        return self.daily_request_count
    
    def get_current_rate_limit_status(self) -> Dict[str, Any]:
        """현재 rate limit 상태 반환"""
        now = time.time()
        recent_requests = [t for t in self.request_times if now - t < 1.0]
        
        return {
            "requests_last_second": len(recent_requests),
            "max_requests_per_second": self.max_requests_per_sec,
            "daily_request_count": self.daily_request_count,
            "can_make_request": len(recent_requests) < self.max_requests_per_sec
        }
    
    def __str__(self) -> str:
        account_number, account_product = self.account_info
        return f"KISClient(mode={self.mode}, account={account_number}, daily_requests={self.daily_request_count})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    # ==================== API 래퍼 함수들 ====================
    
    async def get_account_balance(self) -> Dict[str, Any]:
        """
        계좌 잔고 및 보유 종목 조회
        
        Returns:
            계좌 잔고 정보 및 보유 종목 목록
        """
        endpoint = "/uapi/domestic-stock/v1/trading/inquire-balance"
        tr_id = "TTTC8434R" if self.mode == 'prod' else "VTTC8434R"
        
        account_number, account_product = self.account_info
        
        params = {
            "CANO": account_number,
            "ACNT_PRDT_CD": account_product,
            "AFHR_FLPR_YN": "N",  # 시간외단가적용여부
            "OFL_YN": "N",        # 오프라인여부  
            "INQR_DVSN": "01",    # 조회구분(01: 대출일별, 02: 종목별)
            "UNPR_DVSN": "01",    # 단가구분(01: 기준가, 02: 현재가)
            "FUND_STTL_ICLD_YN": "N",    # 펀드결제분포함여부
            "FNCG_AMT_AUTO_RDPT_YN": "N", # 융자금액자동상환여부
            "PRCS_DVSN": "01",    # 처리구분(00: 전일매매포함, 01: 전일매매미포함)
            "CTX_AREA_FK100": "",  # 연속조회검색조건100
            "CTX_AREA_NK100": ""   # 연속조회키100
        }
        
        return await self.request("GET", endpoint, tr_id=tr_id, params=params)
    
    async def get_stock_price(self, stock_code: str) -> Dict[str, Any]:
        """
        종목 현재가 조회
        
        Args:
            stock_code: 종목코드 (예: "005930")
            
        Returns:
            종목 현재가 정보
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-price"
        tr_id = "FHKST01010100"
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 조건시장분류코드
            "FID_INPUT_ISCD": stock_code     # 입력종목코드
        }
        
        return await self.request("GET", endpoint, tr_id=tr_id, params=params)
    
    async def get_stock_orderbook(self, stock_code: str) -> Dict[str, Any]:
        """
        종목 호가 정보 조회
        
        Args:
            stock_code: 종목코드 (예: "005930")
            
        Returns:
            종목 호가 정보 (매수/매도 호가)
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        tr_id = "FHKST01010200"
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 조건시장분류코드
            "FID_INPUT_ISCD": stock_code     # 입력종목코드
        }
        
        return await self.request("GET", endpoint, tr_id=tr_id, params=params)
    
    async def get_stock_daily_chart(
        self, 
        stock_code: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None, 
        period: Optional[int] = None,
        adjusted: bool = True
    ) -> Dict[str, Any]:
        """
        종목 일봉 차트 조회
        
        Args:
            stock_code: 종목코드 (예: "005930")
            start_date: 시작일자 (YYYYMMDD, 생략시 period 또는 기본값 사용)
            end_date: 종료일자 (YYYYMMDD, 생략시 오늘)
            period: 조회 기간 (일 단위, start_date가 없을 때 사용)
            adjusted: 수정주가 여부 (True: 수정주가, False: 원주가)
            
        Returns:
            종목 일봉 차트 데이터
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
        tr_id = "FHKST01010400"
        
        # 날짜 설정
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        
        if not start_date and period:
            start_date = (datetime.now() - timedelta(days=period)).strftime("%Y%m%d")
        elif not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",    # 조건시장분류코드
            "FID_INPUT_ISCD": stock_code,      # 입력종목코드
            "FID_PERIOD_DIV_CODE": "D",       # 기간분류코드 (D: 일봉)
            "FID_ORG_ADJ_PRC": "1" if adjusted else "0",  # 수정주가원주가구분코드
            "FID_INPUT_DATE_1": start_date,    # 입력날짜1
            "FID_INPUT_DATE_2": end_date,      # 입력날짜2
        }
        
        return await self.request("GET", endpoint, tr_id=tr_id, params=params)
    
    async def place_order(
        self,
        stock_code: str,
        side: str,  # "buy" or "sell"
        quantity: int,
        price: Optional[int] = None,
        order_type: str = "limit"  # "limit" or "market"
    ) -> Dict[str, Any]:
        """
        주식 주문 실행
        
        Args:
            stock_code: 종목코드 (예: "005930")
            side: 매수/매도 구분 ("buy", "sell")
            quantity: 주문 수량
            price: 주문 가격 (시장가 주문 시 None 또는 0)
            order_type: 주문 유형 ("limit": 지정가, "market": 시장가)
            
        Returns:
            주문 결과 정보
        """
        endpoint = "/uapi/domestic-stock/v1/trading/order-cash"
        
        # 매수/매도 구분 코드 변환
        side_code = "02" if side.lower() == "buy" else "01"  # 02: 매수, 01: 매도
        
        # TR ID 설정 (실전/모의투자 구분)
        if side.lower() == "buy":
            tr_id = "TTTC0802U" if self.mode == 'prod' else "VTTC0802U"
        else:
            tr_id = "TTTC0801U" if self.mode == 'prod' else "VTTC0801U"
        
        # 주문 구분 코드
        order_division = "01" if order_type == "market" else "00"  # 00: 지정가, 01: 시장가
        
        # 주문 가격 설정
        if order_type == "market" or price is None:
            order_price = "0"
        else:
            order_price = str(price)
        
        account_number, account_product = self.account_info
        
        data = {
            "CANO": account_number,           # 계좌번호
            "ACNT_PRDT_CD": account_product,  # 계좌상품코드
            "PDNO": stock_code,               # 상품번호 (종목코드)
            "ORD_DVSN": order_division,       # 주문구분
            "ORD_QTY": str(quantity),         # 주문수량
            "ORD_UNPR": order_price,          # 주문단가
            "CTAC_TLNO": "",                  # 연락처전화번호
            "SLL_BUY_DVSN_CD": side_code,     # 매도매수구분코드
            "ALGO_NO": ""                     # 알고리즘번호
        }
        
        return await self.request("POST", endpoint, tr_id=tr_id, data=data)
    
    async def cancel_order(
        self,
        order_number: str,
        stock_code: str,
        quantity: int,
        org_order_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        주문 취소
        
        Args:
            order_number: 주문번호
            stock_code: 종목코드
            quantity: 취소 수량
            org_order_number: 원주문번호 (정정 주문의 경우)
            
        Returns:
            주문 취소 결과
        """
        endpoint = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
        tr_id = "TTTC0803U" if self.mode == 'prod' else "VTTC0803U"
        
        account_number, account_product = self.account_info
        
        data = {
            "CANO": account_number,                    # 계좌번호
            "ACNT_PRDT_CD": account_product,           # 계좌상품코드
            "KRX_FWDG_ORD_ORGNO": "",                 # 한국거래소전송주문조직번호
            "ORGN_ODNO": org_order_number or order_number,  # 원주문번호
            "ORD_DVSN": "00",                         # 주문구분
            "RVSE_CNCL_DVSN_CD": "02",               # 정정취소구분코드 (02: 취소)
            "PDNO": stock_code,                       # 상품번호
            "ORD_QTY": str(quantity),                 # 주문수량
            "ORD_UNPR": "0",                          # 주문단가
            "CTAC_TLNO": "",                          # 연락처전화번호
            "RSVN_ORD_YN": "N"                        # 예약주문여부
        }
        
        return await self.request("POST", endpoint, tr_id=tr_id, data=data)
    
    async def modify_order(
        self,
        order_number: str,
        stock_code: str,
        quantity: int,
        price: int,
        org_order_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        주문 정정
        
        Args:
            order_number: 주문번호
            stock_code: 종목코드
            quantity: 정정 수량
            price: 정정 가격
            org_order_number: 원주문번호
            
        Returns:
            주문 정정 결과
        """
        endpoint = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
        tr_id = "TTTC0803U" if self.mode == 'prod' else "VTTC0803U"
        
        account_number, account_product = self.account_info
        
        data = {
            "CANO": account_number,                    # 계좌번호
            "ACNT_PRDT_CD": account_product,           # 계좌상품코드
            "KRX_FWDG_ORD_ORGNO": "",                 # 한국거래소전송주문조직번호
            "ORGN_ODNO": org_order_number or order_number,  # 원주문번호
            "ORD_DVSN": "00",                         # 주문구분
            "RVSE_CNCL_DVSN_CD": "01",               # 정정취소구분코드 (01: 정정)
            "PDNO": stock_code,                       # 상품번호
            "ORD_QTY": str(quantity),                 # 주문수량
            "ORD_UNPR": str(price),                   # 주문단가
            "CTAC_TLNO": "",                          # 연락처전화번호
            "RSVN_ORD_YN": "N"                        # 예약주문여부
        }
        
        return await self.request("POST", endpoint, tr_id=tr_id, data=data)
    
    async def get_order_history(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        주문 내역 조회
        
        Args:
            start_date: 조회 시작일 (YYYYMMDD, 생략시 오늘)
            end_date: 조회 종료일 (YYYYMMDD, 생략시 시작일과 같음)
            
        Returns:
            주문 내역 정보
        """
        endpoint = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        tr_id = "TTTC8001R" if self.mode == 'prod' else "VTTC8001R"
        
        if not start_date:
            start_date = datetime.now().strftime("%Y%m%d")
        if not end_date:
            end_date = start_date
            
        account_number, account_product = self.account_info
        
        params = {
            "CANO": account_number,         # 계좌번호
            "ACNT_PRDT_CD": account_product, # 계좌상품코드
            "INQR_STRT_DT": start_date,     # 조회시작일자
            "INQR_END_DT": end_date,        # 조회종료일자
            "SLL_BUY_DVSN_CD": "00",        # 매도매수구분코드 (00: 전체)
            "INQR_DVSN": "00",              # 조회구분 (00: 역순)
            "PDNO": "",                      # 상품번호 (전체)
            "CCLD_DVSN": "00",              # 체결구분 (00: 전체)
            "ORD_GNO_BRNO": "",             # 주문채번지점번호
            "ODNO": "",                      # 주문번호
            "INQR_DVSN_3": "00",            # 조회구분3
            "INQR_DVSN_1": "",              # 조회구분1
            "CTX_AREA_FK100": "",           # 연속조회검색조건100
            "CTX_AREA_NK100": ""            # 연속조회키100
        }
        
        return await self.request("GET", endpoint, tr_id=tr_id, params=params)