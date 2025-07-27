"""
Event Handlers

각 엔진에서 사용할 수 있는 표준 이벤트 핸들러들
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .core import Event, EventType


class BaseEventHandler(ABC):
    """기본 이벤트 핸들러 추상 클래스"""
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.logger = logging.getLogger(f"{__name__}.{component_name}")
        self.processed_count = 0
        self.error_count = 0
        self.last_processed = None
    
    def __call__(self, event: Event):
        """이벤트 핸들러 호출"""
        try:
            self.handle_event(event)
            self.processed_count += 1
            self.last_processed = datetime.now()
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error handling event {event.event_type.value}: {e}")
            self.handle_error(event, e)
    
    @abstractmethod
    def handle_event(self, event: Event):
        """실제 이벤트 처리 로직"""
        pass
    
    def handle_error(self, event: Event, error: Exception):
        """에러 처리 (오버라이드 가능)"""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """핸들러 통계"""
        return {
            "component_name": self.component_name,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "last_processed": self.last_processed.isoformat() if self.last_processed else None
        }


class MarketDataEventHandler(BaseEventHandler):
    """시장 데이터 이벤트 핸들러"""
    
    def __init__(self, component_name: str, data_processor: Optional[Callable] = None):
        super().__init__(component_name)
        self.data_processor = data_processor
        self.symbols_processed = set()
        self.last_prices = {}
    
    def handle_event(self, event: Event):
        """시장 데이터 이벤트 처리"""
        if event.event_type == EventType.MARKET_DATA_RECEIVED:
            self._handle_market_data(event)
        elif event.event_type == EventType.CANDLE_UPDATED:
            self._handle_candle_update(event)
        elif event.event_type == EventType.INDICATORS_UPDATED:
            self._handle_indicators_update(event)
        else:
            self.logger.warning(f"Unhandled event type: {event.event_type.value}")
    
    def _handle_market_data(self, event: Event):
        """시장 데이터 처리"""
        data = event.data
        symbol = data.get('symbol')
        price = data.get('close') or data.get('price')
        
        if symbol and price:
            self.symbols_processed.add(symbol)
            self.last_prices[symbol] = price
            
            self.logger.debug(f"Market data processed: {symbol} = {price}")
            
            if self.data_processor:
                self.data_processor(symbol, data)
    
    def _handle_candle_update(self, event: Event):
        """캔들 업데이트 처리"""
        data = event.data
        symbol = data.get('symbol')
        timeframe = data.get('timeframe')
        
        self.logger.debug(f"Candle updated: {symbol} [{timeframe}]")
        
        if self.data_processor:
            self.data_processor(symbol, data)
    
    def _handle_indicators_update(self, event: Event):
        """기술적 지표 업데이트 처리"""
        data = event.data
        symbol = data.get('symbol')
        indicators = data.get('indicators', {})
        
        self.logger.debug(f"Indicators updated: {symbol} = {list(indicators.keys())}")
        
        if self.data_processor:
            self.data_processor(symbol, data)
    
    def get_stats(self) -> Dict[str, Any]:
        """확장된 통계"""
        stats = super().get_stats()
        stats.update({
            "symbols_processed": len(self.symbols_processed),
            "symbols": list(self.symbols_processed),
            "last_prices": self.last_prices
        })
        return stats


class TradingSignalEventHandler(BaseEventHandler):
    """거래 신호 이벤트 핸들러"""
    
    def __init__(self, component_name: str, signal_processor: Optional[Callable] = None):
        super().__init__(component_name)
        self.signal_processor = signal_processor
        self.signals_received = []
        self.strategies_seen = set()
    
    def handle_event(self, event: Event):
        """거래 신호 이벤트 처리"""
        if event.event_type == EventType.TRADING_SIGNAL:
            self._handle_trading_signal(event)
        elif event.event_type == EventType.STRATEGY_SIGNAL:
            self._handle_strategy_signal(event)
        else:
            self.logger.warning(f"Unhandled event type: {event.event_type.value}")
    
    def _handle_trading_signal(self, event: Event):
        """거래 신호 처리"""
        data = event.data
        symbol = data.get('symbol')
        action = data.get('action')
        strategy_name = data.get('strategy_name')
        
        # 신호 기록
        signal_record = {
            "timestamp": event.timestamp,
            "symbol": symbol,
            "action": action,
            "strategy": strategy_name,
            "correlation_id": event.correlation_id
        }
        self.signals_received.append(signal_record)
        
        # 최근 100개만 유지
        if len(self.signals_received) > 100:
            self.signals_received = self.signals_received[-100:]
        
        if strategy_name:
            self.strategies_seen.add(strategy_name)
        
        self.logger.info(
            f"Trading signal: {action} {symbol} from {strategy_name} "
            f"[{event.correlation_id}]"
        )
        
        if self.signal_processor:
            self.signal_processor(event.data)
    
    def _handle_strategy_signal(self, event: Event):
        """전략 신호 처리"""
        data = event.data
        strategy_name = data.get('strategy_name')
        
        if strategy_name:
            self.strategies_seen.add(strategy_name)
        
        self.logger.debug(f"Strategy signal from {strategy_name}")
        
        if self.signal_processor:
            self.signal_processor(event.data)
    
    def get_stats(self) -> Dict[str, Any]:
        """확장된 통계"""
        stats = super().get_stats()
        stats.update({
            "signals_received_count": len(self.signals_received),
            "strategies_seen": list(self.strategies_seen),
            "recent_signals": self.signals_received[-10:]  # 최근 10개
        })
        return stats


class RiskAlertEventHandler(BaseEventHandler):
    """리스크 경고 이벤트 핸들러"""
    
    def __init__(self, component_name: str, alert_processor: Optional[Callable] = None):
        super().__init__(component_name)
        self.alert_processor = alert_processor
        self.alerts_received = []
        self.critical_alerts_count = 0
        self.emergency_stops_count = 0
    
    def handle_event(self, event: Event):
        """리스크 이벤트 처리"""
        if event.event_type == EventType.RISK_ALERT:
            self._handle_risk_alert(event)
        elif event.event_type == EventType.EMERGENCY_STOP:
            self._handle_emergency_stop(event)
        elif event.event_type == EventType.STOP_LOSS_TRIGGERED:
            self._handle_stop_loss(event)
        elif event.event_type == EventType.POSITION_UPDATED:
            self._handle_position_update(event)
        else:
            self.logger.warning(f"Unhandled event type: {event.event_type.value}")
    
    def _handle_risk_alert(self, event: Event):
        """리스크 경고 처리"""
        data = event.data
        alert_type = data.get('alert_type')
        severity = data.get('severity')
        message = data.get('message')
        
        # 경고 기록
        alert_record = {
            "timestamp": event.timestamp,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "correlation_id": event.correlation_id
        }
        self.alerts_received.append(alert_record)
        
        # 최근 50개만 유지
        if len(self.alerts_received) > 50:
            self.alerts_received = self.alerts_received[-50:]
        
        if severity == "CRITICAL":
            self.critical_alerts_count += 1
        
        log_level = logging.CRITICAL if severity == "CRITICAL" else logging.WARNING
        self.logger.log(log_level, f"Risk Alert [{alert_type}]: {message}")
        
        if self.alert_processor:
            self.alert_processor(event.data)
    
    def _handle_emergency_stop(self, event: Event):
        """비상 정지 처리"""
        self.emergency_stops_count += 1
        reason = event.data.get('reason', 'Unknown')
        
        self.logger.critical(f"EMERGENCY STOP: {reason}")
        
        if self.alert_processor:
            self.alert_processor(event.data)
    
    def _handle_stop_loss(self, event: Event):
        """손절 트리거 처리"""
        data = event.data
        symbol = data.get('symbol')
        price = data.get('price')
        
        self.logger.warning(f"Stop loss triggered: {symbol} at {price}")
        
        if self.alert_processor:
            self.alert_processor(event.data)
    
    def _handle_position_update(self, event: Event):
        """포지션 업데이트 처리"""
        data = event.data
        symbol = data.get('symbol')
        
        self.logger.debug(f"Position updated: {symbol}")
        
        if self.alert_processor:
            self.alert_processor(event.data)
    
    def get_stats(self) -> Dict[str, Any]:
        """확장된 통계"""
        stats = super().get_stats()
        stats.update({
            "alerts_received_count": len(self.alerts_received),
            "critical_alerts_count": self.critical_alerts_count,
            "emergency_stops_count": self.emergency_stops_count,
            "recent_alerts": self.alerts_received[-5:]  # 최근 5개
        })
        return stats


class SystemEventHandler(BaseEventHandler):
    """시스템 이벤트 핸들러"""
    
    def __init__(self, component_name: str, system_processor: Optional[Callable] = None):
        super().__init__(component_name)
        self.system_processor = system_processor
        self.engine_statuses = {}
        self.error_events = []
        self.heartbeats = {}
    
    def handle_event(self, event: Event):
        """시스템 이벤트 처리"""
        if event.event_type == EventType.ENGINE_STARTED:
            self._handle_engine_started(event)
        elif event.event_type == EventType.ENGINE_STOPPED:
            self._handle_engine_stopped(event)
        elif event.event_type == EventType.SYSTEM_ERROR:
            self._handle_system_error(event)
        elif event.event_type == EventType.HEARTBEAT:
            self._handle_heartbeat(event)
        elif event.event_type == EventType.SYSTEM_STATUS:
            self._handle_system_status(event)
        else:
            self.logger.warning(f"Unhandled event type: {event.event_type.value}")
    
    def _handle_engine_started(self, event: Event):
        """엔진 시작 이벤트 처리"""
        component = event.data.get('component')
        if component:
            self.engine_statuses[component] = {
                "status": "STARTED",
                "timestamp": event.timestamp,
                "source": event.source
            }
        
        self.logger.info(f"Engine started: {component}")
        
        if self.system_processor:
            self.system_processor(event.data)
    
    def _handle_engine_stopped(self, event: Event):
        """엔진 중지 이벤트 처리"""
        component = event.data.get('component')
        if component:
            self.engine_statuses[component] = {
                "status": "STOPPED",
                "timestamp": event.timestamp,
                "source": event.source
            }
        
        self.logger.info(f"Engine stopped: {component}")
        
        if self.system_processor:
            self.system_processor(event.data)
    
    def _handle_system_error(self, event: Event):
        """시스템 에러 이벤트 처리"""
        error_record = {
            "timestamp": event.timestamp,
            "component": event.data.get('component'),
            "error_type": event.data.get('error_type'),
            "error_message": event.data.get('error_message'),
            "correlation_id": event.correlation_id
        }
        self.error_events.append(error_record)
        
        # 최근 20개만 유지
        if len(self.error_events) > 20:
            self.error_events = self.error_events[-20:]
        
        self.logger.error(
            f"System error in {error_record['component']}: "
            f"{error_record['error_message']}"
        )
        
        if self.system_processor:
            self.system_processor(event.data)
    
    def _handle_heartbeat(self, event: Event):
        """하트비트 이벤트 처리"""
        component = event.data.get('component')
        if component:
            self.heartbeats[component] = {
                "timestamp": event.timestamp,
                "status": event.data.get('status'),
                "metrics": event.data.get('metrics')
            }
        
        self.logger.debug(f"Heartbeat from {component}")
        
        if self.system_processor:
            self.system_processor(event.data)
    
    def _handle_system_status(self, event: Event):
        """시스템 상태 이벤트 처리"""
        component = event.data.get('component')
        status = event.data.get('status')
        
        if component:
            self.engine_statuses[component] = {
                "status": status,
                "timestamp": event.timestamp,
                "source": event.source,
                "details": event.data
            }
        
        self.logger.info(f"System status: {component} = {status}")
        
        if self.system_processor:
            self.system_processor(event.data)
    
    def get_stats(self) -> Dict[str, Any]:
        """확장된 통계"""
        stats = super().get_stats()
        stats.update({
            "engine_statuses": self.engine_statuses,
            "error_events_count": len(self.error_events),
            "recent_errors": self.error_events[-3:],  # 최근 3개
            "active_heartbeats": len(self.heartbeats),
            "heartbeat_components": list(self.heartbeats.keys())
        })
        return stats


class CompositeEventHandler(BaseEventHandler):
    """여러 핸들러를 조합하는 복합 핸들러"""
    
    def __init__(self, component_name: str):
        super().__init__(component_name)
        self.handlers: Dict[EventType, list] = {}
    
    def add_handler(self, event_type: EventType, handler: BaseEventHandler):
        """특정 이벤트 타입에 핸들러 추가"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    def handle_event(self, event: Event):
        """이벤트를 적절한 핸들러들에게 전달"""
        handlers = self.handlers.get(event.event_type, [])
        
        for handler in handlers:
            try:
                handler.handle_event(event)
            except Exception as e:
                self.logger.error(
                    f"Error in handler {handler.component_name} "
                    f"for event {event.event_type.value}: {e}"
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """모든 핸들러의 통계 수집"""
        stats = super().get_stats()
        handler_stats = {}
        
        for event_type, handlers in self.handlers.items():
            handler_stats[event_type.value] = [
                handler.get_stats() for handler in handlers
            ]
        
        stats["handlers"] = handler_stats
        return stats