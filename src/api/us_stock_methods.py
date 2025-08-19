"""
미국 주식 관련 메서드 확장
KISHttpClient 클래스에 추가할 미국 주식 메서드들
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class USStockMethods:
    """미국 주식 API 메서드 모음"""
    
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
            "AUTH": "",  # 빈 문자열 (선택사항)
            "EXCD": exchange[:3] if exchange == "NASD" else exchange,  # NAS or NYSE or AMEX
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
            # 3개월 전 날짜
            start = datetime.now() - timedelta(days=90)
            start_date = start.strftime("%Y%m%d")
        
        # 거래소별 심볼 코드 설정
        if exchange in ["NASD", "NYSE", "AMEX"]:
            # 미국 주식은 그대로 사용
            fid_input_iscd = symbol
            fid_cond_mrkt_div_code = "N"  # 해외지수 (미국주식도 N 사용)
        else:
            fid_input_iscd = symbol
            fid_cond_mrkt_div_code = "N"
        
        params = {
            "FID_COND_MRKT_DIV_CODE": fid_cond_mrkt_div_code,
            "FID_INPUT_ISCD": fid_input_iscd,
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
        
        # output1: 요약 정보, output2: 차트 데이터 리스트
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
            "OVRS_EXCG_CD": "NASD",  # 기본값 나스닥
            "TR_CRCY_CD": "USD",      # 통화코드
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
            order_div: 주문구분 (00: 지정가, 32: LOO, 34: LOC 등)
            exchange: 거래소 (NASD, NYSE, AMEX)
        Returns:
            주문 결과
        """
        endpoint = "/uapi/overseas-stock/v1/trading/order"
        
        # TR_ID 선택
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
    
    async def get_us_order_list(self, 
                               start_date: str = "",
                               end_date: str = "") -> List[Dict]:
        """
        미국 주식 주문 내역 조회
        Args:
            start_date: 조회 시작일 (YYYYMMDD)
            end_date: 조회 종료일 (YYYYMMDD)
        Returns:
            주문 내역 리스트
        """
        endpoint = "/uapi/overseas-stock/v1/trading/inquire-ccnl"
        
        # 날짜 기본값 설정
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            # 1주일 전
            start = datetime.now() - timedelta(days=7)
            start_date = start.strftime("%Y%m%d")
        
        params = {
            "CANO": self.auth_manager.credentials.account_no.split('-')[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "PDNO": "%",  # 전체 종목
            "ORD_STRT_DT": start_date,
            "ORD_END_DT": end_date,
            "SLL_BUY_DVSN": "00",  # 00: 전체, 01: 매도, 02: 매수
            "CCLD_NCCS_DVSN": "00",  # 00: 전체, 01: 체결, 02: 미체결
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
            self.tr_ids["usa"]["order_list"],
            params=params
        )
        
        return result.get("output", [])
    
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
        
        # 취소(02) 또는 정정(01) 구분
        rvse_cncl_dvsn_cd = "02" if quantity == 0 else "01"
        
        data = {
            "CANO": self.auth_manager.credentials.account_no.split('-')[0],
            "ACNT_PRDT_CD": self.auth_manager.credentials.account_prod_cd,
            "OVRS_EXCG_CD": exchange,
            "ORGN_ODNO": order_no,
            "RVSE_CNCL_DVSN_CD": rvse_cncl_dvsn_cd,
            "ORD_QTY": str(quantity) if quantity > 0 else "",
            "OVRS_ORD_UNPR": ""  # 정정 시 가격 (선택사항)
        }
        
        result = await self._make_request(
            "POST",
            endpoint,
            self.tr_ids["usa"]["cancel_order"],
            data=data
        )
        
        return result.get("output", {})