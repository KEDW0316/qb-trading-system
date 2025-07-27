"""
전략 엔진 모듈

이벤트 기반 전략 실행 엔진을 구현합니다.
시장 데이터 이벤트를 수신하여 활성화된 전략들을 실행하고,
거래 신호를 생성하여 다른 엔진들에게 전파합니다.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
import logging

from .base import BaseStrategy, MarketData, TradingSignal
from .loader import StrategyLoader
from ...utils.redis_manager import RedisManager
from ..event_bus import EnhancedEventBus, EventType, EventFilter
from ..event_bus.adapters import TradingSignalPublisher, EngineEventMixin

logger = logging.getLogger(__name__)


class StrategyEngine(EngineEventMixin):
    """
    전략 실행 엔진
    
    이벤트 기반 아키텍처로 동작하며, 시장 데이터를 수신하여
    활성화된 전략들을 실행하고 거래 신호를 생성합니다.
    """

    def __init__(self, redis_manager: RedisManager, event_bus: EnhancedEventBus):
        """
        전략 엔진 초기화
        
        Args:
            redis_manager: Redis 연결 관리자
            event_bus: 이벤트 버스
        """
        self.redis = redis_manager
        self.event_bus = event_bus
        self.strategy_loader = StrategyLoader()
        
        # Event Bus 초기화
        self.init_event_bus(event_bus, "StrategyEngine")
        
        # 전용 발행자 초기화
        self.signal_publisher = TradingSignalPublisher(event_bus, "StrategyEngine")
        
        # 활성 전략 관리
        self.active_strategies: Dict[str, BaseStrategy] = {}
        self.strategy_symbols: Dict[str, Set[str]] = {}  # 전략별 구독 심볼
        
        # 성과 추적
        self.signal_history: List[Dict[str, Any]] = []
        self.last_execution_time: Optional[datetime] = None
        
        # 엔진 상태
        self.is_running = False
        self.total_signals_generated = 0
        
        # 이벤트 구독 설정
        self._setup_event_subscriptions()
        
        logger.info("StrategyEngine initialized")

    def _setup_event_subscriptions(self):
        """이벤트 구독 설정"""
        try:
            # 시장 데이터 이벤트 구독
            self.event_bus.subscribe("market_data_received", self.on_market_data)
            
            # 전략 관리 이벤트 구독
            self.event_bus.subscribe("strategy_activate", self.on_strategy_activate)
            self.event_bus.subscribe("strategy_deactivate", self.on_strategy_deactivate)
            self.event_bus.subscribe("strategy_update_params", self.on_strategy_update_params)
            
            logger.info("Event subscriptions set up successfully")
            
        except Exception as e:
            logger.error(f"Error setting up event subscriptions: {e}")

    async def start(self):
        """전략 엔진 시작"""
        try:
            self.is_running = True
            
            # 전략 디렉토리 스캔
            await self._discover_strategies()
            
            logger.info("StrategyEngine started successfully")
            
        except Exception as e:
            logger.error(f"Error starting StrategyEngine: {e}")
            self.is_running = False

    async def stop(self):
        """전략 엔진 중지"""
        try:
            self.is_running = False
            
            # 모든 활성 전략 비활성화
            strategy_names = list(self.active_strategies.keys())
            for strategy_name in strategy_names:
                await self.deactivate_strategy(strategy_name)
            
            logger.info("StrategyEngine stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping StrategyEngine: {e}")

    async def _discover_strategies(self):
        """전략 발견 및 로드"""
        try:
            discovered_strategies = self.strategy_loader.discover_strategies()
            logger.info(f"Discovered {len(discovered_strategies)} strategies: {discovered_strategies}")
            
        except Exception as e:
            logger.error(f"Error discovering strategies: {e}")

    async def on_market_data(self, event_data: Dict[str, Any]):
        """
        시장 데이터 수신 이벤트 핸들러
        
        Args:
            event_data: 시장 데이터 이벤트
        """
        if not self.is_running:
            return
        
        try:
            # 이벤트 데이터에서 시장 데이터 추출
            symbol = event_data.get("symbol")
            timestamp_str = event_data.get("timestamp")
            
            if not symbol or not timestamp_str:
                logger.warning(f"Invalid market data event: missing symbol or timestamp")
                return
            
            # MarketData 객체 생성
            market_data = MarketData(
                symbol=symbol,
                timestamp=datetime.fromisoformat(timestamp_str),
                open=float(event_data.get("open", 0)),
                high=float(event_data.get("high", 0)),
                low=float(event_data.get("low", 0)),
                close=float(event_data.get("close", 0)),
                volume=int(event_data.get("volume", 0)),
                interval_type=event_data.get("interval_type", "1m")
            )
            
            # Redis에서 기술 지표 데이터 조회
            indicators = await self.fetch_indicators(symbol)
            market_data.indicators = indicators
            
            # 해당 심볼을 구독하는 활성 전략 실행
            await self._execute_strategies_for_symbol(market_data)
            
            self.last_execution_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Error processing market data event: {e}")

    async def fetch_indicators(self, symbol: str) -> Dict[str, float]:
        """
        Redis에서 기술 지표 데이터 조회
        
        Args:
            symbol: 심볼명
            
        Returns:
            Dict[str, float]: 기술 지표 데이터
        """
        try:
            # Redis에서 지표 데이터 조회
            redis_key = f"indicators:{symbol}"
            data = await self.redis.get_data(redis_key)
            
            if data:
                if isinstance(data, str):
                    indicators = json.loads(data)
                else:
                    indicators = data
                
                # 타입 변환 (문자열 -> 숫자)
                converted_indicators = {}
                for key, value in indicators.items():
                    try:
                        converted_indicators[key] = float(value)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert indicator {key}={value} to float")
                        converted_indicators[key] = value
                
                return converted_indicators
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching indicators for {symbol}: {e}")
            return {}

    async def _execute_strategies_for_symbol(self, market_data: MarketData):
        """
        특정 심볼에 대해 활성 전략들 실행
        
        Args:
            market_data: 시장 데이터
        """
        symbol = market_data.symbol
        executed_strategies = []
        
        for strategy_name, strategy in self.active_strategies.items():
            try:
                # 이 전략이 해당 심볼을 구독하는지 확인
                if (strategy_name not in self.strategy_symbols or 
                    symbol not in self.strategy_symbols[strategy_name]):
                    continue
                
                # 전략 실행
                signal = await strategy.process_market_data(market_data)
                
                if signal:
                    # 거래 신호 발행
                    await self.publish_trading_signal(strategy_name, signal)
                    executed_strategies.append(strategy_name)
                
            except Exception as e:
                logger.error(f"Error executing strategy {strategy_name} for {symbol}: {e}")
        
        if executed_strategies:
            logger.debug(f"Executed strategies for {symbol}: {executed_strategies}")

    async def publish_trading_signal(self, strategy_name: str, signal: TradingSignal):
        """
        거래 신호 이벤트 발행
        
        Args:
            strategy_name: 신호를 생성한 전략명
            signal: 거래 신호
        """
        try:
            # 신호 이벤트 데이터 구성
            signal_event = {
                "strategy": strategy_name,
                "symbol": signal.symbol,
                "action": signal.action,
                "confidence": signal.confidence,
                "price": signal.price,
                "quantity": signal.quantity,
                "reason": signal.reason,
                "metadata": signal.metadata or {},
                "timestamp": signal.timestamp.isoformat()
            }
            
            # 이벤트 발행
            await self.event_bus.publish("trading_signal", signal_event)
            
            # 신호 히스토리 기록
            self.signal_history.append({
                **signal_event,
                "generated_at": datetime.now().isoformat()
            })
            
            # 히스토리 크기 제한 (최근 1000개만 유지)
            if len(self.signal_history) > 1000:
                self.signal_history = self.signal_history[-1000:]
            
            self.total_signals_generated += 1
            
            logger.info(
                f"Published trading signal: {strategy_name} -> {signal.action} "
                f"{signal.symbol} (confidence: {signal.confidence})"
            )
            
        except Exception as e:
            logger.error(f"Error publishing trading signal: {e}")

    async def activate_strategy(self, strategy_name: str, params: Optional[Dict[str, Any]] = None, 
                              symbols: Optional[List[str]] = None) -> bool:
        """
        전략 활성화
        
        Args:
            strategy_name: 활성화할 전략명
            params: 전략 파라미터
            symbols: 구독할 심볼 목록
            
        Returns:
            bool: 활성화 성공 여부
        """
        try:
            if strategy_name in self.active_strategies:
                logger.warning(f"Strategy {strategy_name} is already active")
                return False
            
            # 전략 로드
            strategy = self.strategy_loader.load_strategy(strategy_name, params)
            if not strategy:
                logger.error(f"Failed to load strategy: {strategy_name}")
                return False
            
            # 전략 활성화
            strategy.enable()
            self.active_strategies[strategy_name] = strategy
            
            # 구독 심볼 설정
            if symbols:
                self.strategy_symbols[strategy_name] = set(symbols)
            else:
                # 기본적으로 모든 심볼 구독
                self.strategy_symbols[strategy_name] = set()
            
            logger.info(f"Strategy {strategy_name} activated with symbols: {symbols or 'ALL'}")
            
            # 활성화 이벤트 발행
            await self.event_bus.publish("strategy_activated", {
                "strategy_name": strategy_name,
                "symbols": list(self.strategy_symbols[strategy_name]),
                "timestamp": datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error activating strategy {strategy_name}: {e}")
            return False

    async def deactivate_strategy(self, strategy_name: str) -> bool:
        """
        전략 비활성화
        
        Args:
            strategy_name: 비활성화할 전략명
            
        Returns:
            bool: 비활성화 성공 여부
        """
        try:
            if strategy_name not in self.active_strategies:
                logger.warning(f"Strategy {strategy_name} is not active")
                return False
            
            # 전략 비활성화
            strategy = self.active_strategies[strategy_name]
            strategy.disable()
            
            # 활성 전략에서 제거
            del self.active_strategies[strategy_name]
            
            # 구독 심볼 제거
            if strategy_name in self.strategy_symbols:
                del self.strategy_symbols[strategy_name]
            
            # 전략 언로드
            self.strategy_loader.unload_strategy(strategy_name)
            
            logger.info(f"Strategy {strategy_name} deactivated")
            
            # 비활성화 이벤트 발행
            await self.event_bus.publish("strategy_deactivated", {
                "strategy_name": strategy_name,
                "timestamp": datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating strategy {strategy_name}: {e}")
            return False

    async def update_strategy_parameters(self, strategy_name: str, params: Dict[str, Any]) -> bool:
        """
        전략 파라미터 업데이트
        
        Args:
            strategy_name: 업데이트할 전략명
            params: 새로운 파라미터
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            if strategy_name not in self.active_strategies:
                logger.error(f"Strategy {strategy_name} is not active")
                return False
            
            strategy = self.active_strategies[strategy_name]
            success = strategy.set_parameters(params)
            
            if success:
                logger.info(f"Updated parameters for strategy {strategy_name}: {params}")
                
                # 파라미터 업데이트 이벤트 발행
                await self.event_bus.publish("strategy_parameters_updated", {
                    "strategy_name": strategy_name,
                    "parameters": params,
                    "timestamp": datetime.now().isoformat()
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating strategy parameters for {strategy_name}: {e}")
            return False

    async def update_strategy_symbols(self, strategy_name: str, symbols: List[str]) -> bool:
        """
        전략의 구독 심볼 업데이트
        
        Args:
            strategy_name: 전략명
            symbols: 새로운 심볼 목록
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            if strategy_name not in self.active_strategies:
                logger.error(f"Strategy {strategy_name} is not active")
                return False
            
            self.strategy_symbols[strategy_name] = set(symbols)
            
            logger.info(f"Updated symbols for strategy {strategy_name}: {symbols}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating strategy symbols for {strategy_name}: {e}")
            return False

    # 이벤트 핸들러들
    async def on_strategy_activate(self, event_data: Dict[str, Any]):
        """전략 활성화 이벤트 핸들러"""
        strategy_name = event_data.get("strategy_name")
        params = event_data.get("params")
        symbols = event_data.get("symbols")
        
        if strategy_name:
            await self.activate_strategy(strategy_name, params, symbols)

    async def on_strategy_deactivate(self, event_data: Dict[str, Any]):
        """전략 비활성화 이벤트 핸들러"""
        strategy_name = event_data.get("strategy_name")
        
        if strategy_name:
            await self.deactivate_strategy(strategy_name)

    async def on_strategy_update_params(self, event_data: Dict[str, Any]):
        """전략 파라미터 업데이트 이벤트 핸들러"""
        strategy_name = event_data.get("strategy_name")
        params = event_data.get("params")
        
        if strategy_name and params:
            await self.update_strategy_parameters(strategy_name, params)

    # 상태 조회 메서드들
    def get_active_strategies(self) -> List[str]:
        """활성 전략 목록 반환"""
        return list(self.active_strategies.keys())

    def get_available_strategies(self) -> List[str]:
        """사용 가능한 전략 목록 반환"""
        return self.strategy_loader.get_available_strategies()

    def get_strategy_status(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """특정 전략의 상태 정보 반환"""
        if strategy_name in self.active_strategies:
            strategy = self.active_strategies[strategy_name]
            status = strategy.get_status()
            status['symbols'] = list(self.strategy_symbols.get(strategy_name, set()))
            return status
        elif strategy_name in self.strategy_loader.available_strategies:
            return self.strategy_loader.get_strategy_info(strategy_name)
        else:
            return None

    def get_engine_status(self) -> Dict[str, Any]:
        """엔진 전체 상태 정보 반환"""
        return {
            'is_running': self.is_running,
            'active_strategies': len(self.active_strategies),
            'available_strategies': len(self.strategy_loader.available_strategies),
            'total_signals_generated': self.total_signals_generated,
            'last_execution_time': self.last_execution_time.isoformat() if self.last_execution_time else None,
            'recent_signals': self.signal_history[-10:],  # 최근 10개 신호
            'strategy_loader_status': self.strategy_loader.get_loader_status()
        }

    def get_signal_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """신호 히스토리 반환"""
        return self.signal_history[-limit:]

    async def reload_strategy(self, strategy_name: str) -> bool:
        """전략 리로드"""
        try:
            if strategy_name in self.active_strategies:
                # 현재 설정 보존
                current_params = self.active_strategies[strategy_name].get_parameters()
                current_symbols = list(self.strategy_symbols.get(strategy_name, set()))
                
                # 비활성화
                await self.deactivate_strategy(strategy_name)
                
                # 리로드
                reloaded_strategy = self.strategy_loader.reload_strategy(strategy_name, current_params)
                
                if reloaded_strategy:
                    # 다시 활성화
                    return await self.activate_strategy(strategy_name, current_params, current_symbols)
                
            return False
            
        except Exception as e:
            logger.error(f"Error reloading strategy {strategy_name}: {e}")
            return False

    def __str__(self) -> str:
        return f"StrategyEngine(running={self.is_running}, active={len(self.active_strategies)})"

    def __repr__(self) -> str:
        return f"<StrategyEngine running={self.is_running} active_strategies={len(self.active_strategies)}>"