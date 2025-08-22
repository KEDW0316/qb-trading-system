"""
ABOUTME: Unified WebSocket client for seamless real-time data from multiple markets
"""

from typing import Dict, List, Union, Optional, Callable, Any
import asyncio

from src.auth.kis_auth import KISAuthManager
from src.api.markets.korea.websocket import KoreaWebSocketClient
from src.api.markets.usa.websocket import USWebSocketClient
from src.api.models.enums import Market


class UnifiedWebSocket:
    """통합 WebSocket 클라이언트 - 한국/미국 시장 실시간 데이터"""
    
    def __init__(self, auth_manager: KISAuthManager, max_retries: int = 3):
        """
        초기화
        
        Args:
            auth_manager: 인증 관리자
            max_retries: 최대 재시도 횟수
        """
        self.auth_manager = auth_manager
        self.max_retries = max_retries
        
        # 시장별 WebSocket 클라이언트
        self.korea = KoreaWebSocketClient(auth_manager, max_retries)
        self.usa = USWebSocketClient(auth_manager, max_retries)
        
        # 통합 콜백 함수
        self.unified_callbacks: Dict[str, Optional[Callable]] = {
            "on_quote": None,
            "on_tick": None,
            "on_order": None,
            "on_error": None,
            "on_connect": None,
            "on_disconnect": None
        }
        
        # 로거 설정
        import logging
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 콜백 설정
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """시장별 콜백을 통합 콜백으로 연결"""
        
        async def korea_quote_callback(data):
            """한국 호가 콜백 래퍼"""
            if self.unified_callbacks.get("on_quote"):
                # 시장 정보 추가
                await self.unified_callbacks["on_quote"](data, market="KR")
        
        async def usa_quote_callback(data):
            """미국 호가 콜백 래퍼"""
            if self.unified_callbacks.get("on_quote"):
                # 시장 정보 추가
                await self.unified_callbacks["on_quote"](data, market="US")
        
        async def korea_tick_callback(data):
            """한국 체결 콜백 래퍼"""
            if self.unified_callbacks.get("on_tick"):
                # 시장 정보 추가
                await self.unified_callbacks["on_tick"](data, market="KR")
        
        async def usa_tick_callback(data):
            """미국 체결 콜백 래퍼"""
            if self.unified_callbacks.get("on_tick"):
                # 시장 정보 추가
                await self.unified_callbacks["on_tick"](data, market="US")
        
        async def unified_error_callback(error, message=None, market=None):
            """통합 에러 콜백"""
            if self.unified_callbacks.get("on_error"):
                await self.unified_callbacks["on_error"](error, message, market)
        
        # 한국 시장 콜백 설정
        self.korea.set_callbacks(
            on_quote=korea_quote_callback,
            on_tick=korea_tick_callback,
            on_error=lambda e, m: unified_error_callback(e, m, "KR")
        )
        
        # 미국 시장 콜백 설정
        self.usa.set_callbacks(
            on_quote=usa_quote_callback,
            on_tick=usa_tick_callback,
            on_error=lambda e, m: unified_error_callback(e, m, "US")
        )
    
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
            return market.upper()
        elif exchange:
            kr_exchanges = ["UN", "UQ", "UK", "KRX", "NXT", "SOR"]
            us_exchanges = ["NASD", "NYSE", "AMEX"]
            
            if exchange in kr_exchanges:
                return Market.KOREA.value
            elif exchange in us_exchanges:
                return Market.USA.value
        
        if code:
            return self._detect_market(code)
        
        return Market.KOREA.value
    
    async def connect(self, markets: Union[str, List[str]] = "all") -> Dict[str, bool]:
        """
        WebSocket 연결
        
        Args:
            markets: 연결할 시장 ("all", "KR", "US", ["KR", "US"])
            
        Returns:
            시장별 연결 결과
        """
        if isinstance(markets, str):
            if markets.upper() == "ALL":
                markets = ["KR", "US"]
            else:
                markets = [markets.upper()]
        
        results = {}
        
        # 병렬 연결
        tasks = []
        if "KR" in markets:
            tasks.append(("KR", self.korea.connect()))
        if "US" in markets:
            tasks.append(("US", self.usa.connect()))
        
        if tasks:
            for market, task in tasks:
                try:
                    result = await task
                    results[market] = result
                    if result:
                        self.logger.info(f"{market} WebSocket connected successfully")
                    else:
                        self.logger.error(f"{market} WebSocket connection failed")
                except Exception as e:
                    self.logger.error(f"{market} WebSocket connection error: {e}")
                    results[market] = False
        
        return results
    
    async def disconnect(self, markets: Union[str, List[str]] = "all"):
        """
        WebSocket 연결 해제
        
        Args:
            markets: 해제할 시장 ("all", "KR", "US", ["KR", "US"])
        """
        if isinstance(markets, str):
            if markets.upper() == "ALL":
                markets = ["KR", "US"]
            else:
                markets = [markets.upper()]
        
        # 병렬 해제
        tasks = []
        if "KR" in markets:
            tasks.append(self.korea.disconnect())
        if "US" in markets:
            tasks.append(self.usa.disconnect())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def subscribe_quote(self,
                             codes: Union[str, List[str]],
                             market: Optional[str] = None,
                             exchange: Optional[str] = None,
                             **kwargs) -> Dict[str, bool]:
        """
        통합 실시간 호가 구독
        
        Args:
            codes: 종목코드 또는 심볼 (단일 또는 리스트)
            market: 시장 구분 (KR/US/auto)
            exchange: 거래소 코드
            **kwargs: 추가 파라미터
            
        Returns:
            구독 결과
        """
        if isinstance(codes, str):
            codes = [codes]
        
        results = {}
        
        # 시장별로 그룹화
        kr_codes = []
        us_codes = []
        
        for code in codes:
            market_type = self._parse_market(market, exchange, code)
            if market_type == Market.KOREA.value:
                kr_codes.append(code)
            else:
                us_codes.append(code)
        
        # 병렬 구독
        tasks = []
        if kr_codes:
            tasks.append(("KR", self.korea.subscribe_quote(kr_codes, exchange or "UN")))
        if us_codes:
            tasks.append(("US", self.usa.subscribe_quote(us_codes, exchange or "NASD", **kwargs)))
        
        for market_type, task in tasks:
            try:
                result = await task
                results[market_type] = result
            except Exception as e:
                self.logger.error(f"Quote subscription failed for {market_type}: {e}")
                results[market_type] = False
        
        return results
    
    async def subscribe_tick(self,
                            codes: Union[str, List[str]],
                            market: Optional[str] = None,
                            exchange: Optional[str] = None,
                            **kwargs) -> Dict[str, bool]:
        """
        통합 실시간 체결 구독
        
        Args:
            codes: 종목코드 또는 심볼 (단일 또는 리스트)
            market: 시장 구분 (KR/US/auto)
            exchange: 거래소 코드
            **kwargs: 추가 파라미터 (delayed 등)
            
        Returns:
            구독 결과
        """
        if isinstance(codes, str):
            codes = [codes]
        
        results = {}
        
        # 시장별로 그룹화
        kr_codes = []
        us_codes = []
        
        for code in codes:
            market_type = self._parse_market(market, exchange, code)
            if market_type == Market.KOREA.value:
                kr_codes.append(code)
            else:
                us_codes.append(code)
        
        # 병렬 구독
        tasks = []
        if kr_codes:
            tasks.append(("KR", self.korea.subscribe_tick(kr_codes, exchange or "UN")))
        if us_codes:
            tasks.append(("US", self.usa.subscribe_tick(us_codes, exchange or "NASD", **kwargs)))
        
        for market_type, task in tasks:
            try:
                result = await task
                results[market_type] = result
            except Exception as e:
                self.logger.error(f"Tick subscription failed for {market_type}: {e}")
                results[market_type] = False
        
        return results
    
    async def subscribe_realtime(self,
                                codes: Union[str, List[str]],
                                data_type: str = "both",
                                market: Optional[str] = None,
                                exchange: Optional[str] = None,
                                **kwargs) -> Dict[str, Dict[str, bool]]:
        """
        통합 실시간 데이터 구독 (호가 + 체결)
        
        Args:
            codes: 종목코드 또는 심볼
            data_type: "quote", "tick", "both"
            market: 시장 구분
            exchange: 거래소 코드
            **kwargs: 추가 파라미터
            
        Returns:
            구독 결과
        """
        results = {}
        
        if data_type in ["quote", "both"]:
            quote_results = await self.subscribe_quote(codes, market, exchange, **kwargs)
            results["quote"] = quote_results
        
        if data_type in ["tick", "both"]:
            tick_results = await self.subscribe_tick(codes, market, exchange, **kwargs)
            results["tick"] = tick_results
        
        return results
    
    async def unsubscribe(self,
                         codes: Union[str, List[str]],
                         data_type: str = "all",
                         market: Optional[str] = None,
                         exchange: Optional[str] = None) -> Dict[str, bool]:
        """
        통합 구독 해제
        
        Args:
            codes: 종목코드 또는 심볼
            data_type: "quote", "tick", "all"
            market: 시장 구분
            exchange: 거래소 코드
            
        Returns:
            해제 결과
        """
        if isinstance(codes, str):
            codes = [codes]
        
        results = {}
        
        # 시장별로 그룹화
        kr_codes = []
        us_codes = []
        
        for code in codes:
            market_type = self._parse_market(market, exchange, code)
            if market_type == Market.KOREA.value:
                kr_codes.append(code)
            else:
                us_codes.append(code)
        
        # 병렬 해제
        tasks = []
        if kr_codes:
            for code in kr_codes:
                tasks.append(("KR", self.korea.unsubscribe(code, data_type, exchange or "UN")))
        if us_codes:
            for code in us_codes:
                tasks.append(("US", self.usa.unsubscribe(code, data_type, exchange or "NASD")))
        
        for market_type, task in tasks:
            try:
                result = await task
                results[f"{market_type}"] = result
            except Exception as e:
                self.logger.error(f"Unsubscribe failed for {market_type}: {e}")
                results[f"{market_type}"] = False
        
        return results
    
    def set_callbacks(self, **callbacks):
        """
        통합 콜백 함수 설정
        
        Args:
            **callbacks: 콜백 함수들
                - on_quote: 호가 데이터 콜백 (data, market)
                - on_tick: 체결 데이터 콜백 (data, market)
                - on_error: 에러 콜백 (error, message, market)
                - on_connect: 연결 콜백
                - on_disconnect: 연결 해제 콜백
        """
        for name, callback in callbacks.items():
            if name in self.unified_callbacks:
                self.unified_callbacks[name] = callback
            else:
                self.logger.warning(f"Unknown callback: {name}")
    
    def get_subscriptions(self) -> Dict[str, Dict[str, Dict]]:
        """모든 구독 정보 반환"""
        return {
            "korea": self.korea.get_subscriptions(),
            "usa": self.usa.get_subscriptions()
        }
    
    def get_connection_status(self) -> Dict[str, Dict]:
        """모든 연결 상태 반환"""
        return {
            "korea": self.korea.get_connection_status(),
            "usa": self.usa.get_connection_status()
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.disconnect()