"""
ABOUTME: US stock market REST API client implementation
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta

from src.api.base.client import BaseAPIClient
from src.api.markets.usa.constants import USA_TR_IDS, EXCHANGE_CODE_MAP
from src.api.models.enums import USExchange, OrderType, OrderDiv


class USStockClient(BaseAPIClient):
    """미국 주식 REST API 클라이언트"""
    
    def _get_tr_ids(self, env: str) -> Dict[str, str]:
        """환경별 TR_ID 매핑 반환"""
        return USA_TR_IDS.get(env, USA_TR_IDS["vps"])
    
    def _validate_us_symbol(self, symbol: str) -> bool:
        """
        미국 주식 심볼 유효성 검사
        
        Args:
            symbol: 티커 심볼
            
        Returns:
            유효 여부
        """
        if not self._validate_stock_code(symbol):
            return False
        # 1-5자리 대문자 알파벳
        return 1 <= len(symbol) <= 5 and symbol.isalpha() and symbol.isupper()
    
    def _get_exchange_code(self, exchange: str) -> str:
        """
        거래소 코드 변환 (API 형식으로)
        
        Args:
            exchange: 거래소 (NASD, NYSE, AMEX)
            
        Returns:
            API용 거래소 코드
        """
        return EXCHANGE_CODE_MAP.get(exchange, "NAS")
    
    async def get_current_price(self, 
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
        if not self._validate_us_symbol(symbol):
            self.logger.warning(f"Invalid US stock symbol: {symbol}, proceeding anyway...")
        
        endpoint = "/uapi/overseas-price/v1/quotations/price"
        
        params = {
            "AUTH": "",  
            "EXCD": self._get_exchange_code(exchange),
            "SYMB": symbol.upper()
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["current_price"],
            params=params
        )
        
        return result.get("output", {})
    
    async def get_daily_chart(self,
                             symbol: str,
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None,
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
        if not self._validate_us_symbol(symbol):
            self.logger.warning(f"Invalid US stock symbol: {symbol}, proceeding anyway...")
        
        endpoint = "/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"
        
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
            "FID_COND_MRKT_DIV_CODE": "N",
            "FID_INPUT_ISCD": symbol.upper(),
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["daily_chart"],
            params=params
        )
        
        chart_data = result.get("output2", [])
        summary = result.get("output1", {})
        
        return chart_data, summary
    
    async def get_account_balance(self) -> Tuple[List[Dict], Dict]:
        """
        미국 주식 계좌 잔고 조회
        
        Returns:
            (보유종목 리스트, 계좌 요약 정보)
        """
        endpoint = "/uapi/overseas-stock/v1/trading/inquire-balance"
        
        account_parts = self.auth_manager.credentials.account_no.split('-')
        
        params = {
            "CANO": account_parts[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "OVRS_EXCG_CD": "NASD",
            "TR_CRCY_CD": "USD",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
        }
        
        result = await self._make_request(
            "GET",
            endpoint,
            self.tr_ids["account_balance"],
            params=params
        )
        
        stocks = result.get("output1", [])
        summary = result.get("output2", {})
        
        return stocks, summary
    
    async def place_order(self,
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
            order_div: 주문구분 (00: 지정가, 32: LOO, 34: LOC)
            exchange: 거래소 (NASD, NYSE, AMEX)
            
        Returns:
            주문 결과
        """
        if not self._validate_us_symbol(symbol):
            self.logger.warning(f"Invalid US stock symbol: {symbol}, proceeding anyway...")
        
        if order_type not in ["buy", "sell"]:
            raise ValueError(f"Invalid order type: {order_type}")
        
        endpoint = "/uapi/overseas-stock/v1/trading/order"
        
        # TR_ID 선택
        tr_id = self.tr_ids["place_buy_order"] if order_type == "buy" else self.tr_ids["place_sell_order"]
        
        account_parts = self.auth_manager.credentials.account_no.split('-')
        
        data = {
            "CANO": account_parts[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "OVRS_EXCG_CD": exchange,
            "PDNO": symbol.upper(),
            "ORD_QTY": str(quantity),
            "OVRS_ORD_UNPR": str(price) if price > 0 else "0",
            "CTAC_TLNO": "",
            "MGCO_APTM_ODNO": "",
            "SLL_TYPE": "00" if order_type == "sell" else "",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": order_div
        }
        
        self.logger.info(f"Placing {order_type} order for {symbol}: {quantity} shares at ${price}")
        
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
                            symbol: str = "",
                            order_status: str = "00") -> List[Dict]:
        """
        미국 주식 주문 내역 조회
        
        Args:
            start_date: 조회 시작일 (YYYYMMDD)
            end_date: 조회 종료일 (YYYYMMDD)
            symbol: 티커 심볼 (빈 문자열이면 전체)
            order_status: 체결구분 (00: 전체, 01: 체결, 02: 미체결)
            
        Returns:
            주문 내역 리스트
        """
        endpoint = "/uapi/overseas-stock/v1/trading/inquire-ccnl"
        
        # 날짜 기본값 설정
        if not end_date:
            end_date = self._format_date()
        else:
            end_date = self._format_date(end_date)
        
        if not start_date:
            # 기본 1주일 전
            start = datetime.now() - timedelta(days=7)
            start_date = self._format_date(start)
        else:
            start_date = self._format_date(start_date)
        
        account_parts = self.auth_manager.credentials.account_no.split('-')
        
        params = {
            "CANO": account_parts[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "PDNO": symbol.upper() if symbol else "%",  # 전체 종목
            "ORD_STRT_DT": start_date,
            "ORD_END_DT": end_date,
            "SLL_BUY_DVSN": "00",  # 00: 전체, 01: 매도, 02: 매수
            "CCLD_NCCS_DVSN": order_status,
            "OVRS_EXCG_CD": "",  # 전체 거래소
            "SORT_SQN": "DS",  # 정렬 순서
            "ORD_DT": "",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": ""
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
        
        # 취소(02) 또는 정정(01) 구분
        rvse_cncl_dvsn_cd = "02" if quantity == 0 else "01"
        
        account_parts = self.auth_manager.credentials.account_no.split('-')
        
        data = {
            "CANO": account_parts[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "OVRS_EXCG_CD": exchange,
            "ORGN_ODNO": order_no,
            "RVSE_CNCL_DVSN_CD": rvse_cncl_dvsn_cd,
            "ORD_QTY": str(quantity) if quantity > 0 else "",
            "OVRS_ORD_UNPR": ""
        }
        
        self.logger.info(f"{'Canceling' if quantity == 0 else 'Modifying'} order {order_no}")
        
        result = await self._make_request(
            "POST",
            endpoint,
            self.tr_ids["cancel_order"],
            data=data
        )
        
        return result.get("output", {})