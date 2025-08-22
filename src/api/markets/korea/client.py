"""
ABOUTME: Korean stock market REST API client implementation
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta

from src.api.base.client import BaseAPIClient
from src.api.markets.korea.constants import KOREA_TR_IDS
from src.api.models.enums import KoreaExchange, OrderType, OrderDiv


class KoreaStockClient(BaseAPIClient):
    """한국 주식 REST API 클라이언트"""
    
    def _get_tr_ids(self, env: str) -> Dict[str, str]:
        """환경별 TR_ID 매핑 반환"""
        return KOREA_TR_IDS.get(env, KOREA_TR_IDS["vps"])
    
    def _validate_korea_stock_code(self, code: str) -> bool:
        """
        한국 주식 코드 유효성 검사 (6자리 숫자)
        
        Args:
            code: 종목 코드
            
        Returns:
            유효 여부
        """
        if not self._validate_stock_code(code):
            return False
        return len(code) == 6 and code.isdigit()
    
    async def get_current_price(self, 
                               code: str,
                               exchange: str = "UN") -> Dict:
        """
        한국 주식 현재가 조회
        
        Args:
            code: 종목코드 (예: "005930")
            exchange: 거래소 코드 (UN: 유가증권, UQ: 코스닥)
            
        Returns:
            현재가 정보
        """
        if not self._validate_korea_stock_code(code):
            raise ValueError(f"Invalid Korean stock code: {code}")
        
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-price"
        
        params = {
            "FID_COND_MRKT_DIV_CODE": exchange,
            "FID_INPUT_ISCD": code
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["current_price"],
            params=params
        )
        
        return result.get("output", {})
    
    async def get_daily_chart(self,
                             code: str,
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None,
                             period: str = "D",
                             exchange: str = "UN") -> List[Dict]:
        """
        일봉/주봉/월봉 차트 데이터 조회
        
        Args:
            code: 종목코드
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            period: 기간 구분 (D: 일, W: 주, M: 월)
            exchange: 거래소 코드
            
        Returns:
            차트 데이터 리스트
        """
        if not self._validate_korea_stock_code(code):
            raise ValueError(f"Invalid Korean stock code: {code}")
        
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        
        # 날짜 기본값 설정
        if not end_date:
            end_date = self._format_date()
        else:
            end_date = self._format_date(end_date)
        
        if not start_date:
            # 기본 3개월 전
            start = datetime.now() - timedelta(days=90)
            start_date = self._format_date(start)
        else:
            start_date = self._format_date(start_date)
        
        params = {
            "FID_COND_MRKT_DIV_CODE": exchange,
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0"  # 수정주가 사용 안함
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["daily_chart"],
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
        
        account_parts = self.auth_manager.credentials.account_no.split('-')
        
        params = {
            "CANO": account_parts[0],
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
            self.tr_ids["account_balance"],
            params=params
        )
        
        stocks = result.get("output1", [])
        summary = result.get("output2", [{}])[0] if result.get("output2") else {}
        
        return stocks, summary
    
    async def place_order(self,
                         code: str,
                         order_type: str,
                         quantity: int,
                         price: int = 0,
                         order_div: str = "00",
                         exchange: str = "SOR") -> Dict:
        """
        주문 실행
        
        Args:
            code: 종목코드
            order_type: 주문유형 ("buy" or "sell")
            quantity: 수량
            price: 가격 (시장가는 0)
            order_div: 주문구분 (00: 지정가, 01: 시장가, 03: 조건부지정가)
            exchange: 거래소 (KRX: 정규장, NXT: 야간거래, SOR: 스마트라우팅)
            
        Returns:
            주문 결과
        """
        if not self._validate_korea_stock_code(code):
            raise ValueError(f"Invalid Korean stock code: {code}")
        
        if order_type not in ["buy", "sell"]:
            raise ValueError(f"Invalid order type: {order_type}")
        
        endpoint = "/uapi/domestic-stock/v1/trading/order-cash"
        
        # TR_ID 선택
        tr_id = self.tr_ids["place_buy_order"] if order_type == "buy" else self.tr_ids["place_sell_order"]
        
        account_parts = self.auth_manager.credentials.account_no.split('-')
        
        data = {
            "CANO": account_parts[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "PDNO": code,
            "ORD_DVSN": order_div,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price) if order_div == "00" else "0",
            "EXCG_ID_DVSN_CD": exchange,
            "SLL_TYPE": "",
            "CNDT_PRIC": ""
        }
        
        self.logger.info(f"Placing {order_type} order for {code}: {quantity} shares at {price} KRW")
        
        result = await self._make_request(
            "POST",
            endpoint,
            tr_id,
            data=data
        )
        
        return result.get("output", {})
    
    async def get_order_list(self,
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None,
                            stock_code: str = "",
                            order_status: str = "00") -> List[Dict]:
        """
        주문 내역 조회
        
        Args:
            start_date: 조회 시작일 (YYYYMMDD)
            end_date: 조회 종료일 (YYYYMMDD)
            stock_code: 종목코드 (빈 문자열이면 전체)
            order_status: 체결구분 (00: 전체, 01: 체결, 02: 미체결)
            
        Returns:
            주문 내역 리스트
        """
        endpoint = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
        
        # 날짜 기본값 설정 (오늘)
        if not end_date:
            end_date = self._format_date()
        else:
            end_date = self._format_date(end_date)
        
        if not start_date:
            start_date = end_date
        else:
            start_date = self._format_date(start_date)
        
        account_parts = self.auth_manager.credentials.account_no.split('-')
        
        params = {
            "CANO": account_parts[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "INQR_STRT_DT": start_date,
            "INQR_END_DT": end_date,
            "SLL_BUY_DVSN_CD": "00",   # 00: 전체, 01: 매도, 02: 매수
            "PDNO": stock_code,
            "CCLD_DVSN": order_status,
            "INQR_DVSN": "00",         # 00: 역순, 01: 정순
            "INQR_DVSN_3": "00",       # 00: 전체
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["order_list"],
            params=params
        )
        
        return result.get("output", [])
    
    async def cancel_order(self,
                          order_no: str,
                          quantity: int = 0,
                          cancel_all: bool = True) -> Dict:
        """
        주문 취소
        
        Args:
            order_no: 주문번호
            quantity: 취소수량 (0이면 전량 취소)
            cancel_all: 전량 취소 여부
            
        Returns:
            취소 결과
        """
        endpoint = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
        
        account_parts = self.auth_manager.credentials.account_no.split('-')
        
        data = {
            "CANO": account_parts[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "KRX_FWDG_ORD_ORGNO": "",
            "ORGN_ODNO": order_no,
            "ORD_DVSN": "00",
            "RVSE_CNCL_DVSN_CD": "02",  # 취소
            "ORD_QTY": str(quantity) if quantity > 0 else "0",
            "ORD_UNPR": "0",
            "QTY_ALL_ORD_YN": "Y" if cancel_all else "N"
        }
        
        self.logger.info(f"Canceling order {order_no}")
        
        result = await self._make_request(
            "POST",
            endpoint,
            self.tr_ids["cancel_order"],
            data=data
        )
        
        return result.get("output", {})