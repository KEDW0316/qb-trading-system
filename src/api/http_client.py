"""
KIS API HTTP Client
한국 및 미국 주식 API 호출을 지원하는 통합 래퍼 클래스
"""

import aiohttp
import logging
from typing import Dict, List, Tuple, Optional, Any, Literal
from datetime import datetime
from enum import Enum

from src.auth.kis_auth import KISAuthManager
from src.utils.rate_limiter import RateLimiter


class Market(Enum):
    """시장 구분"""
    KOREA = "KR"
    USA = "US"


class Exchange(Enum):
    """거래소 코드"""
    # 한국
    KOSPI = "UN"  # 유가증권
    KOSDAQ = "UQ"  # 코스닥
    # 미국
    NASDAQ = "NASD"
    NYSE = "NYSE"
    AMEX = "AMEX"
    # 기타
    HONGKONG = "SEHK"
    SHANGHAI = "SHAA"
    SHENZHEN = "SZAA"
    JAPAN = "TKSE"
    VIETNAM_HANOI = "HASE"
    VIETNAM_HCMC = "VNSE"


class KISHttpClient:
    """KIS API HTTP 클라이언트 - 한국/미국 주식 통합 지원"""
    
    def __init__(self, auth_manager: KISAuthManager, rate_limiter: RateLimiter):
        """
        초기화
        Args:
            auth_manager: 인증 관리자
            rate_limiter: Rate Limit 관리자
        """
        self.auth_manager = auth_manager
        self.rate_limiter = rate_limiter
        self.logger = logging.getLogger(__name__)
        
        # API Base URL
        self.base_url = auth_manager._get_api_base_url()
        
        # 환경별 TR_ID 설정 (한국 + 미국)
        self.tr_ids = self._get_tr_ids(auth_manager.env)
    
    def _get_tr_ids(self, env: str) -> Dict[str, Dict[str, str]]:
        """환경별 TR_ID 매핑 (한국/미국 통합)"""
        if env == "prod":
            return {
                "korea": {
                    "current_price": "FHKST01010100",     # 실전 현재가
                    "daily_chart": "FHKST01010400",       # 실전 일봉
                    "account_balance": "TTTC8434R",       # 실전 잔고
                    "place_buy_order": "TTTC0802U",       # 실전 매수
                    "place_sell_order": "TTTC0801U",      # 실전 매도
                    "order_list": "TTTC8001R",            # 실전 주문내역
                    "cancel_order": "TTTC0803U"           # 실전 주문취소
                },
                "usa": {
                    "current_price": "HHDFS00000300",     # 미국 현재가
                    "daily_chart": "FHKST03030100",       # 미국 일봉/주봉/월봉
                    "account_balance": "TTTS3012R",       # 미국 잔고
                    "place_buy_order": "TTTT1002U",       # 미국 매수
                    "place_sell_order": "TTTT1006U",      # 미국 매도
                    "order_list": "TTTS3035R",            # 미국 주문내역
                    "cancel_order": "TTTT1004U"           # 미국 주문취소/정정
                }
            }
        else:  # vps (모의투자)
            return {
                "korea": {
                    "current_price": "FHKST01010100",     # 모의 현재가 (실전과 동일)
                    "daily_chart": "FHKST01010400",       # 모의 일봉 (실전과 동일)
                    "account_balance": "VTTC8434R",       # 모의 잔고
                    "place_buy_order": "VTTC0802U",       # 모의 매수
                    "place_sell_order": "VTTC0801U",      # 모의 매도
                    "order_list": "VTTC8001R",            # 모의 주문내역
                    "cancel_order": "VTTC0803U"           # 모의 주문취소
                },
                "usa": {
                    "current_price": "HHDFS00000300",     # 미국 현재가 (실전과 동일)
                    "daily_chart": "FHKST03030100",       # 미국 일봉/주봉/월봉 (실전과 동일)
                    "account_balance": "VTTS3012R",       # 미국 모의 잔고
                    "place_buy_order": "VTTT1002U",       # 미국 모의 매수
                    "place_sell_order": "VTTT1006U",      # 미국 모의 매도
                    "order_list": "VTTS3035R",            # 미국 모의 주문내역
                    "cancel_order": "VTTT1004U"           # 미국 모의 주문취소/정정
                }
            }
    
    async def _make_request(self, 
                          method: str,
                          endpoint: str, 
                          tr_id: str,
                          params: Dict = None,
                          data: Dict = None) -> Dict:
        """
        API 요청 실행
        Args:
            method: HTTP 메서드 (GET, POST)
            endpoint: API 엔드포인트
            tr_id: 거래 ID
            params: Query parameters
            data: Request body
        Returns:
            API 응답 데이터
        """
        # Rate Limit 체크
        await self.rate_limiter.acquire()
        
        # 토큰 가져오기
        token = await self.auth_manager.get_access_token()
        
        # 헤더 구성
        headers = {
            "Authorization": f"Bearer {token}",
            "appkey": self.auth_manager.credentials.app_key,
            "appsecret": self.auth_manager.credentials.app_secret,
            "tr_id": tr_id,
            "Content-Type": "application/json"
        }
        
        # URL 구성
        url = f"{self.base_url}{endpoint}"
        
        # API 호출
        async with aiohttp.ClientSession() as session:
            if method.upper() == "GET":
                async with session.get(url, headers=headers, params=params) as response:
                    result = await response.json()
            else:  # POST
                async with session.post(url, headers=headers, json=data) as response:
                    result = await response.json()
            
            # 에러 체크
            if result.get("rt_cd") != "0":
                error_msg = result.get("msg1", "Unknown error")
                self.logger.error(f"API Error: {error_msg}")
                raise Exception(f"API Error: {error_msg}")
            
            return result
    
    def _get_market_from_exchange(self, exchange: str) -> str:
        """거래소 코드로 시장 구분"""
        us_exchanges = ["NASD", "NYSE", "AMEX"]
        kr_exchanges = ["UN", "UQ"]
        
        if exchange in us_exchanges:
            return "usa"
        elif exchange in kr_exchanges:
            return "korea"
        else:
            # 기타 해외 시장도 overseas로 처리
            return "usa"
    
    def _is_korean_stock_code(self, code: str) -> bool:
        """한국 주식 코드인지 확인 (6자리 숫자)"""
        return len(code) == 6 and code.isdigit()
    
    # ============= 한국 주식 API (기존 메서드 - 호환성 유지) =============
    
    async def get_current_price(self, stock_code: str) -> Dict:
        """
        현재가 조회
        Args:
            stock_code: 종목코드 (예: "005930")
        Returns:
            현재가 정보
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-price"
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "UN",  # 주식
            "FID_INPUT_ISCD": stock_code
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["korea"]["current_price"],
            params=params
        )
        
        return result.get("output", {})
    
    async def get_daily_chart(self, 
                            stock_code: str,
                            start_date: str = "",
                            end_date: str = "",
                            period: str = "D") -> List[Dict]:
        """
        일봉 차트 데이터 조회
        Args:
            stock_code: 종목코드
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            period: 기간 구분 (D: 일, W: 주, M: 월)
        Returns:
            차트 데이터 리스트
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        
        # 날짜 기본값 설정
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = "20250801"  # 기본 1년 전
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "UN",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0"  # 수정주가 사용 안함
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["korea"]["daily_chart"],
            params=params
        )
        
        return result.get("output", [])
    
    async def get_account_balance(self) -> Tuple[List[Dict], Dict]:
        """
        계좌 잔고 조회
        Returns:
            (보유종목 리스트, 계좌 요약 정보)
        """
        endpoint = "/uapi/domestic-stock/v1/trading/inquire-balance"
        
        params = {
            "CANO": self.auth_manager.credentials.account_no.split('-')[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "AFHR_FLPR_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "FUND_STTL_ICLD_YN": "N",
            "INQR_DVSN": "01",
            "OFL_YN": "N",
            "PRCS_DVSN": "00",
            "UNPR_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["korea"]["account_balance"],
            params=params
        )
        
        stocks = result.get("output1", [])
        summary = result.get("output2", [{}])[0] if result.get("output2") else {}
        
        return stocks, summary
    
    async def place_order(self,
                         stock_code: str,
                         order_type: str,
                         quantity: int,
                         price: int = 0,
                         order_div: str = "03",
                         exchange: str = "SOR") -> Dict:
        """
        주문 실행
        Args:
            stock_code: 종목코드
            order_type: 주문유형 ("buy" or "sell")
            quantity: 수량
            price: 가격 (시장가는 0)
            order_div: 주문구분 (00: 지정가, 01: 시장가)
            exchange: 거래소 (KRX: 정규장, NXT: 야간거래)
        Returns:
            주문 결과
        """
        endpoint = "/uapi/domestic-stock/v1/trading/order-cash"
        print(order_div)
        # TR_ID 선택
        tr_id = self.tr_ids["korea"]["place_buy_order"] if order_type == "buy" else self.tr_ids["korea"]["place_sell_order"]
        
        data = {
            "CANO": self.auth_manager.credentials.account_no.split('-')[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "PDNO": stock_code,
            "ORD_DVSN": order_div,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price) if order_div == "00" else "0",
            "EXCG_ID_DVSN_CD": exchange,  # 거래소 구분 (KRX, NXT 등)
            "SLL_TYPE": "",               # 매도유형 (매도시에만 사용)
            "CNDT_PRIC": ""               # 조건가격
        }
        print(data)
        
        result = await self._make_request(
            "POST",
            endpoint,
            tr_id,
            data=data
        )
        
        return result.get("output", {})
    
    async def get_order_list(self) -> List[Dict]:
        """
        주문 내역 조회 (주식일별주문체결조회)
        Returns:
            주문 내역 리스트
        """
        endpoint = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        
        # 주식일별주문체결조회 파라미터 (3개월 이내)
        params = {
            "CANO": self.auth_manager.credentials.account_no.split('-')[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "INQR_STRT_DT": datetime.now().strftime("%Y%m%d"),  # 오늘
            "INQR_END_DT": datetime.now().strftime("%Y%m%d"),   # 오늘
            "SLL_BUY_DVSN_CD": "00",   # 00:전체, 01:매도, 02:매수
            "PDNO": "",                # 종목번호 (공란:전체)
            "CCLD_DVSN": "00",         # 00:전체, 01:체결, 02:미체결
            "INQR_DVSN": "00",         # 00:역순, 01:정순
            "INQR_DVSN_3": "00",       # 00:전체, 01:현금, 02:신용, 03:담보, 04:대주, 05:대여
            "ORD_GNO_BRNO": "",        # 주문채번지점번호
            "ODNO": "",                # 주문번호
            "INQR_DVSN_1": "",         # 조회구분1 (공란:전체, 1:ELW, 2:프리보드)
            "CTX_AREA_FK100": "",      # 연속조회검색조건100
            "CTX_AREA_NK100": ""       # 연속조회키100
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["korea"]["order_list"],
            params=params
        )
        
        return result.get("output", [])
    
    async def cancel_order(self, order_no: str, quantity: int = 0) -> Dict:
        """
        주문 취소
        Args:
            order_no: 주문번호
            quantity: 취소수량 (0이면 전량 취소)
        Returns:
            취소 결과
        """
        endpoint = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
        
        data = {
            "CANO": self.auth_manager.credentials.account_no.split('-')[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "KRX_FWDG_ORD_ORGNO": "",  # 원주문 관리점
            "ORGN_ODNO": order_no,     # 원주문번호
            "ORD_DVSN": "00",          # 주문구분
            "RVSE_CNCL_DVSN_CD": "02", # 취소
            "ORD_QTY": str(quantity) if quantity > 0 else "0",
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y" if quantity == 0 else "N"
        }
        
        result = await self._make_request(
            "POST",
            endpoint,
            self.tr_ids["korea"]["cancel_order"],
            data=data
        )
        
        return result.get("output", {})
    
    # ============= 미국 주식 API (신규 메서드) =============
    
    async def get_us_current_price(self, 
                                  symbol: str,
                                  exchange: str = "NASD") -> Dict:
        """
        미국 주식 현재가 조회
        Args:
            symbol: 티커 심볼 (예: "AAPL", "TSLA")
            exchange: 거래소 코드 (NASD, NYSE, AMEX)
        Returns:
            현재가 정보
        """
        endpoint = "/uapi/overseas-price/v1/quotations/price"
        
        params = {
            "AUTH": "",  
            "EXCD": "NAS" if exchange == "NASD" else ("NYS" if exchange == "NYSE" else exchange[:3]),
            "SYMB": symbol
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["usa"]["current_price"],
            params=params
        )
        
        return result.get("output", {})
    
    async def get_us_daily_chart(self,
                                symbol: str,
                                start_date: str = "",
                                end_date: str = "",
                                period: str = "D",
                                exchange: str = "NASD") -> Tuple[List[Dict], Dict]:
        """
        미국 주식 일봉/주봉/월봉 차트 데이터 조회
        Args:
            symbol: 티커 심볼 (예: "AAPL")
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            period: 기간 구분 (D: 일, W: 주, M: 월, Y: 년)
            exchange: 거래소 코드
        Returns:
            (차트 데이터 리스트, 요약 정보)
        """
        endpoint = "/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"
        
        # 날짜 기본값 설정
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            from datetime import timedelta
            start = datetime.now() - timedelta(days=90)
            start_date = start.strftime("%Y%m%d")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "N",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["usa"]["daily_chart"],
            params=params
        )
        
        chart_data = result.get("output2", [])
        summary = result.get("output1", {})
        
        return chart_data, summary
    
    async def get_us_account_balance(self) -> Tuple[List[Dict], Dict]:
        """
        미국 주식 계좌 잔고 조회
        Returns:
            (보유종목 리스트, 계좌 요약 정보)
        """
        endpoint = "/uapi/overseas-stock/v1/trading/inquire-balance"
        
        params = {
            "CANO": self.auth_manager.credentials.account_no.split('-')[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["usa"]["account_balance"],
            params=params
        )
        
        stocks = result.get("output1", [])
        summary = result.get("output2", {})
        
        return stocks, summary
    
    async def place_us_order(self,
                            symbol: str,
                            order_type: str,
                            quantity: int,
                            price: float = 0,
                            order_div: str = "00",
                            exchange: str = "NASD") -> Dict:
        """
        미국 주식 주문 실행
        Args:
            symbol: 티커 심볼 (예: "AAPL")
            order_type: 주문유형 ("buy" or "sell")
            quantity: 수량
            price: 가격 (시장가는 0)
            order_div: 주문구분 (00: 지정가)
            exchange: 거래소 (NASD, NYSE, AMEX)
        Returns:
            주문 결과
        """
        endpoint = "/uapi/overseas-stock/v1/trading/order"
        
        tr_id = self.tr_ids["usa"]["place_buy_order"] if order_type == "buy" else self.tr_ids["usa"]["place_sell_order"]
        
        data = {
            "CANO": self.auth_manager.credentials.account_no.split('-')[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "OVRS_EXCG_CD": exchange,
            "PDNO": symbol,
            "ORD_QTY": str(quantity),
            "OVRS_ORD_UNPR": str(price) if price > 0 else "0",
            "CTAC_TLNO": "",
            "MGCO_APTM_ODNO": "",
            "SLL_TYPE": "00" if order_type == "sell" else "",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": order_div
        }
        
        result = await self._make_request(
            "POST",
            endpoint,
            tr_id,
            data=data
        )
        
        return result.get("output", {})
    
    async def cancel_us_order(self,
                             order_no: str,
                             quantity: int = 0,
                             exchange: str = "NASD") -> Dict:
        """
        미국 주식 주문 취소/정정
        Args:
            order_no: 주문번호
            quantity: 정정수량 (0이면 전량 취소)
            exchange: 거래소 코드
        Returns:
            취소/정정 결과
        """
        endpoint = "/uapi/overseas-stock/v1/trading/order-rvsecncl"
        
        rvse_cncl_dvsn_cd = "02" if quantity == 0 else "01"
        
        data = {
            "CANO": self.auth_manager.credentials.account_no.split('-')[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "OVRS_EXCG_CD": exchange,
            "ORGN_ODNO": order_no,
            "RVSE_CNCL_DVSN_CD": rvse_cncl_dvsn_cd,
            "ORD_QTY": str(quantity) if quantity > 0 else "",
            "OVRS_ORD_UNPR": ""
        }
        
        result = await self._make_request(
            "POST",
            endpoint,
            self.tr_ids["usa"]["cancel_order"],
            data=data
        )
        
        return result.get("output", {})
    
    # ============= 통합 메서드 (한국/미국 자동 구분) =============
    
    async def get_price(self,
                       symbol: str,
                       exchange: Optional[str] = None,
                       market: Optional[str] = None) -> Dict:
        """
        통합 현재가 조회 (한국/미국 자동 구분)
        Args:
            symbol: 종목코드 또는 티커 심볼
            exchange: 거래소 코드 (선택사항)
            market: 시장 구분 (KR/US, 선택사항)
        Returns:
            현재가 정보
        """
        if market:
            is_korea = market.upper() == "KR"
        elif exchange:
            is_korea = self._get_market_from_exchange(exchange) == "korea"
        else:
            is_korea = self._is_korean_stock_code(symbol)
        
        if is_korea:
            return await self.get_current_price(symbol)
        else:
            return await self.get_us_current_price(symbol, exchange or "NASD")
    
    async def get_chart(self,
                       symbol: str,
                       start_date: str = "",
                       end_date: str = "",
                       period: str = "D",
                       exchange: Optional[str] = None,
                       market: Optional[str] = None) -> Any:
        """
        통합 차트 데이터 조회 (한국/미국 자동 구분)
        Args:
            symbol: 종목코드 또는 티커 심볼
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            period: 기간 구분 (D/W/M/Y)
            exchange: 거래소 코드 (선택사항)
            market: 시장 구분 (KR/US, 선택사항)
        Returns:
            한국: List[Dict], 미국: Tuple[List[Dict], Dict]
        """
        if market:
            is_korea = market.upper() == "KR"
        elif exchange:
            is_korea = self._get_market_from_exchange(exchange) == "korea"
        else:
            is_korea = self._is_korean_stock_code(symbol)
        
        if is_korea:
            return await self.get_daily_chart(symbol, start_date, end_date, period)
        else:
            return await self.get_us_daily_chart(symbol, start_date, end_date, period, exchange or "NASD")
    
    async def place_unified_order(self,
                                 symbol: str,
                                 order_type: str,
                                 quantity: int,
                                 price: float = 0,
                                 exchange: Optional[str] = None,
                                 market: Optional[str] = None) -> Dict:
        """
        통합 주문 실행 (한국/미국 자동 구분)
        Args:
            symbol: 종목코드 또는 티커 심볼
            order_type: "buy" or "sell"
            quantity: 수량
            price: 가격 (시장가는 0)
            exchange: 거래소 코드 (선택사항)
            market: 시장 구분 (KR/US, 선택사항)
        Returns:
            주문 결과
        """
        if market:
            is_korea = market.upper() == "KR"
        elif exchange:
            is_korea = self._get_market_from_exchange(exchange) == "korea"
        else:
            is_korea = self._is_korean_stock_code(symbol)
        
        if is_korea:
            order_div = "00" if price > 0 else "01"
            return await self.place_order(symbol, order_type, quantity, int(price), order_div)
        else:
            order_div = "00"
            return await self.place_us_order(symbol, order_type, quantity, price, order_div, exchange or "NASD")