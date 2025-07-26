import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from qb.utils.event_bus import EventBus, EventType, Event
from qb.utils.redis_manager import RedisManager
from .indicators import IndicatorCalculator
from .cache_manager import IndicatorCacheManager


class TechnicalAnalyzer:
    """이벤트 기반 기술적 분석 엔진
    
    market_data_received 이벤트를 구독하고 기술적 지표를 계산한 후
    indicators_updated 이벤트를 발행합니다.
    """
    
    def __init__(self, redis_manager: RedisManager, event_bus: EventBus):
        self.redis_manager = redis_manager
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        self.running = False
        
        # IndicatorCalculator 초기화
        self.indicator_calculator = IndicatorCalculator()
        
        # 캐시 매니저 초기화
        self.cache_manager = IndicatorCacheManager(redis_manager)
        
    async def start(self):
        """기술적 분석 엔진 시작"""
        if self.running:
            self.logger.warning("TechnicalAnalyzer is already running")
            return
            
        self.running = True
        
        # market_data_received 이벤트 구독
        self.event_bus.subscribe(
            EventType.MARKET_DATA_RECEIVED, 
            self.process_market_data
        )
        
        self.logger.info("TechnicalAnalyzer started")
        
    async def stop(self):
        """기술적 분석 엔진 중지"""
        self.running = False
        
        # 이벤트 구독 해제
        self.event_bus.unsubscribe(
            EventType.MARKET_DATA_RECEIVED, 
            self.process_market_data
        )
        
        self.logger.info("TechnicalAnalyzer stopped")
        
    async def process_market_data(self, event: Event):
        """시장 데이터 수신 시 지표 계산 및 이벤트 발행"""
        try:
            data = event.data
            symbol = data.get('symbol')
            timeframe = data.get('timeframe', '1m')
            
            if not symbol:
                self.logger.error("No symbol in market data event")
                return
                
            # Redis에서 캔들 데이터 조회
            candles = await self.get_candles_from_redis(symbol, timeframe)
            
            if not candles or len(candles) < 20:  # 최소 20개 캔들 필요
                self.logger.debug(f"Not enough candles for {symbol}: {len(candles) if candles else 0}")
                return
                
            # 지표 계산
            indicators = await self.calculate_indicators(symbol, candles, timeframe)
            
            # Redis에 지표 캐싱
            await self.cache_indicators(symbol, indicators)
            
            # indicators_updated 이벤트 발행
            indicators_event = self.event_bus.create_event(
                event_type=EventType.INDICATORS_UPDATED,
                source='TechnicalAnalyzer',
                data={
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'indicators': indicators,
                    'timestamp': datetime.now().isoformat()
                },
                correlation_id=event.correlation_id
            )
            
            self.event_bus.publish(indicators_event)
            
            self.logger.debug(f"Indicators updated for {symbol}: {list(indicators.keys())}")
            
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}", exc_info=True)
            
    async def get_candles_from_redis(self, symbol: str, timeframe: str) -> List[Dict[str, Any]]:
        """Redis에서 캔들 데이터 조회"""
        try:
            key = f"candles:{symbol}:{timeframe}"
            
            # Redis에서 최근 200개 캔들 조회
            candle_strings = self.redis_manager.redis.lrange(key, 0, 199)
            
            candles = []
            for candle_str in candle_strings:
                if isinstance(candle_str, bytes):
                    candle_str = candle_str.decode('utf-8')
                candle = json.loads(candle_str)
                candles.append(candle)
                
            return candles
            
        except Exception as e:
            self.logger.error(f"Error getting candles from Redis: {e}")
            return []
            
    async def calculate_indicators(self, symbol: str, candles: List[Dict[str, Any]], timeframe: str = '1m') -> Dict[str, float]:
        """기술적 지표 계산 (캐싱 포함)"""
        try:
            # timeframe은 파라미터로 받아온 값 사용
            
            # 캐시에서 먼저 확인
            cached_indicators = self.cache_manager.get_all_cached_indicators(symbol, timeframe)
            if cached_indicators:
                self.logger.debug(f"Using cached indicators for {symbol}")
                return cached_indicators
            
            # 캐시에 없으면 계산
            self.logger.debug(f"Calculating indicators for {symbol}")
            indicators = self.indicator_calculator.calculate_all_indicators(candles)
            
            # 계산 시간 추가
            indicators['calculated_at'] = datetime.now().isoformat()
            
            # 캐시에 저장
            self.cache_manager.cache_all_indicators(symbol, indicators, timeframe)
            
            return indicators
            
        except Exception as e:
            self.logger.error(f"Error calculating indicators for {symbol}: {e}")
            return {}
            
    async def cache_indicators(self, symbol: str, indicators: Dict[str, Any]):
        """Redis에 지표 캐싱"""
        try:
            key = f"indicators:{symbol}"
            
            # 각 지표를 Redis Hash에 저장
            for indicator_name, value in indicators.items():
                self.redis_manager.redis.hset(key, indicator_name, str(value))
                
            # 1시간 TTL 설정
            self.redis_manager.redis.expire(key, 3600)
            
            self.logger.debug(f"Cached {len(indicators)} indicators for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error caching indicators: {e}")
            
    async def get_cached_indicators(self, symbol: str) -> Optional[Dict[str, Any]]:
        """캐시된 지표 조회"""
        try:
            key = f"indicators:{symbol}"
            indicators_raw = self.redis_manager.redis.hgetall(key)
            
            if not indicators_raw:
                return None
                
            # bytes를 string으로 변환하고 값 파싱
            indicators = {}
            for k, v in indicators_raw.items():
                if isinstance(k, bytes):
                    k = k.decode('utf-8')
                if isinstance(v, bytes):
                    v = v.decode('utf-8')
                    
                # 숫자로 변환 시도
                try:
                    indicators[k] = float(v)
                except ValueError:
                    indicators[k] = v
                    
            return indicators
            
        except Exception as e:
            self.logger.error(f"Error getting cached indicators: {e}")
            return None