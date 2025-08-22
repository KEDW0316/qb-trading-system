"""
ABOUTME: Unified API client providing seamless access to multiple stock markets
"""

from typing import Dict, List, Tuple, Optional, Union, Any
from datetime import datetime

from src.auth.kis_auth import KISAuthManager
from src.utils.rate_limiter import RateLimiter
from src.api.markets.korea.client import KoreaStockClient
from src.api.markets.usa.client import USStockClient
from src.api.models.enums import Market, OrderType


class UnifiedClient:
    """통합 API 클라이언트 - 한국/미국 시장 자동 라우팅"""
    
    def __init__(self, auth_manager: KISAuthManager, rate_limiter: RateLimiter):
        """
        초기화
        
        Args:
            auth_manager: 인증 관리자
            rate_limiter: Rate Limit 관리자
        """
        self.auth_manager = auth_manager
        self.rate_limiter = rate_limiter
        
        # 시장별 클라이언트 초기화
        self.korea = KoreaStockClient(auth_manager, rate_limiter)
        self.usa = USStockClient(auth_manager, rate_limiter)
        
        # 로거 설정
        import logging
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _detect_market(self, code: str) -> str:
        """
        종목 코드로 시장 자동 감지
        
        Args:
            code: 종목 코드 또는 심볼
            
        Returns:
            시장 구분 ("KR" or "US")
        """
        # 6자리 숫자면 한국 주식
        if len(code) == 6 and code.isdigit():
            return Market.KOREA.value
        # 그 외는 미국 주식으로 간주
        else:
            return Market.USA.value
    
    def _parse_market(self, market: Optional[str] = None, exchange: Optional[str] = None, code: Optional[str] = None) -> str:
        """
        시장 구분 파싱
        
        Args:
            market: 명시적 시장 구분
            exchange: 거래소 코드
            code: 종목 코드
            
        Returns:
            시장 구분
        """
        if market:
            # 명시적으로 지정된 경우
            return market.upper()
        elif exchange:
            # 거래소로 판단
            kr_exchanges = ["UN", "UQ", "UK", "KRX", "NXT", "SOR"]
            us_exchanges = ["NASD", "NYSE", "AMEX"]
            
            if exchange in kr_exchanges:
                return Market.KOREA.value
            elif exchange in us_exchanges:
                return Market.USA.value
        
        # 종목 코드로 자동 감지
        if code:
            return self._detect_market(code)
        
        # 기본값
        return Market.KOREA.value
    
    async def get_price(self,
                       code: str,
                       market: Optional[str] = None,
                       exchange: Optional[str] = None,
                       **kwargs) -> Dict:
        """
        통합 현재가 조회 (시장 자동 감지)
        
        Args:
            code: 종목코드 또는 티커 심볼
            market: 시장 구분 (KR/US, 선택사항)
            exchange: 거래소 코드 (선택사항)
            **kwargs: 추가 파라미터
            
        Returns:
            현재가 정보
        """
        market_type = self._parse_market(market, exchange, code)
        
        if market_type == Market.KOREA.value:
            return await self.korea.get_current_price(code, exchange or "UN")
        else:
            return await self.usa.get_current_price(code, exchange or "NASD")
    
    async def get_chart(self,
                       code: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       period: str = "D",
                       market: Optional[str] = None,
                       exchange: Optional[str] = None,
                       **kwargs) -> Union[List[Dict], Tuple[List[Dict], Dict]]:
        """
        통합 차트 데이터 조회 (시장 자동 감지)
        
        Args:
            code: 종목코드 또는 티커 심볼
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            period: 기간 구분 (D/W/M/Y)
            market: 시장 구분 (KR/US, 선택사항)
            exchange: 거래소 코드 (선택사항)
            **kwargs: 추가 파라미터
            
        Returns:
            한국: List[Dict], 미국: Tuple[List[Dict], Dict]
        """
        market_type = self._parse_market(market, exchange, code)
        
        if market_type == Market.KOREA.value:
            return await self.korea.get_daily_chart(
                code, start_date, end_date, period, exchange or "UN"
            )
        else:
            return await self.usa.get_daily_chart(
                code, start_date, end_date, period, exchange or "NASD"
            )
    
    async def place_order(self,
                         code: str,
                         order_type: str,
                         quantity: int,
                         price: Union[int, float] = 0,
                         market: Optional[str] = None,
                         exchange: Optional[str] = None,
                         order_div: Optional[str] = None,
                         **kwargs) -> Dict:
        """
        통합 주문 실행 (시장 자동 감지)
        
        Args:
            code: 종목코드 또는 티커 심볼
            order_type: "buy" or "sell"
            quantity: 수량
            price: 가격 (시장가는 0)
            market: 시장 구분 (KR/US, 선택사항)
            exchange: 거래소 코드 (선택사항)
            order_div: 주문구분 (선택사항)
            **kwargs: 추가 파라미터
            
        Returns:
            주문 결과
        """
        market_type = self._parse_market(market, exchange, code)
        
        if market_type == Market.KOREA.value:
            # 한국 주식
            if order_div is None:
                order_div = "00" if price > 0 else "01"  # 지정가/시장가
            
            return await self.korea.place_order(
                code, order_type, quantity, int(price), 
                order_div, exchange or "SOR"
            )
        else:
            # 미국 주식
            if order_div is None:
                order_div = "00"  # 지정가 (미국은 시장가 제한적)
            
            return await self.usa.place_order(
                code, order_type, quantity, float(price), 
                order_div, exchange or "NASD"
            )
    
    async def get_balance(self,
                         market: str = "all") -> Dict[str, Any]:
        """
        통합 계좌 잔고 조회
        
        Args:
            market: 시장 구분 (KR/US/all)
            
        Returns:
            잔고 정보 딕셔너리
        """
        result = {}
        
        if market.upper() in ["KR", "ALL"]:
            try:
                kr_stocks, kr_summary = await self.korea.get_account_balance()
                result["korea"] = {
                    "stocks": kr_stocks,
                    "summary": kr_summary
                }
            except Exception as e:
                self.logger.error(f"Failed to get Korean balance: {e}")
                result["korea"] = {"error": str(e)}
        
        if market.upper() in ["US", "ALL"]:
            try:
                us_stocks, us_summary = await self.usa.get_account_balance()
                result["usa"] = {
                    "stocks": us_stocks,
                    "summary": us_summary
                }
            except Exception as e:
                self.logger.error(f"Failed to get US balance: {e}")
                result["usa"] = {"error": str(e)}
        
        return result
    
    async def get_orders(self,
                        market: str = "all",
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        **kwargs) -> Dict[str, List[Dict]]:
        """
        통합 주문 내역 조회
        
        Args:
            market: 시장 구분 (KR/US/all)
            start_date: 시작일
            end_date: 종료일
            **kwargs: 추가 파라미터
            
        Returns:
            주문 내역 딕셔너리
        """
        result = {}
        
        if market.upper() in ["KR", "ALL"]:
            try:
                kr_orders = await self.korea.get_order_list(start_date, end_date)
                result["korea"] = kr_orders
            except Exception as e:
                self.logger.error(f"Failed to get Korean orders: {e}")
                result["korea"] = []
        
        if market.upper() in ["US", "ALL"]:
            try:
                us_orders = await self.usa.get_order_list(start_date, end_date)
                result["usa"] = us_orders
            except Exception as e:
                self.logger.error(f"Failed to get US orders: {e}")
                result["usa"] = []
        
        return result
    
    async def cancel_order(self,
                          order_no: str,
                          market: str,
                          quantity: int = 0,
                          exchange: Optional[str] = None,
                          **kwargs) -> Dict:
        """
        통합 주문 취소
        
        Args:
            order_no: 주문번호
            market: 시장 구분 (KR/US)
            quantity: 취소수량 (0이면 전량)
            exchange: 거래소 코드 (미국 주식용)
            **kwargs: 추가 파라미터
            
        Returns:
            취소 결과
        """
        if market.upper() == "KR":
            return await self.korea.cancel_order(order_no, quantity)
        elif market.upper() == "US":
            return await self.usa.cancel_order(order_no, quantity, exchange or "NASD")
        else:
            raise ValueError(f"Invalid market: {market}")
    
    async def close(self):
        """리소스 정리"""
        await self.korea.close()
        await self.usa.close()
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.close()