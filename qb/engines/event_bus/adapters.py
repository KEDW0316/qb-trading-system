"""
Event Bus Adapters

다른 엔진들이 Event Bus와 쉽게 연동할 수 있도록 하는 어댑터 클래스들
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional, List, Awaitable
from datetime import datetime

from .core import EnhancedEventBus, Event, EventType, EventPriority, EventFilter


class EventBusAdapter:
    """Event Bus 연동을 위한 기본 어댑터"""
    
    def __init__(self, event_bus: EnhancedEventBus, component_name: str):
        self.event_bus = event_bus
        self.component_name = component_name
        self.logger = logging.getLogger(f"{__name__}.{component_name}")
        self.subscriptions: List[str] = []
        
    def publish_event(self, 
                      event_type: EventType,
                      data: Dict[str, Any],
                      priority: EventPriority = EventPriority.NORMAL,
                      correlation_id: Optional[str] = None,
                      ttl: Optional[int] = None) -> bool:
        """이벤트 발행"""
        try:
            event = self.event_bus.create_event(
                event_type=event_type,
                source=self.component_name,
                data=data,
                priority=priority,
                correlation_id=correlation_id,
                ttl=ttl
            )
            
            return self.event_bus.publish(event)
            
        except Exception as e:
            self.logger.error(f"Failed to publish event {event_type.value}: {e}")
            return False
    
    def subscribe_event(self,
                        event_type: EventType,
                        callback: Callable[[Event], None],
                        event_filter: Optional[EventFilter] = None) -> str:
        """이벤트 구독"""
        try:
            subscription_id = self.event_bus.subscribe(
                event_type=event_type,
                callback=callback,
                event_filter=event_filter
            )
            
            self.subscriptions.append(subscription_id)
            self.logger.info(f"Subscribed to {event_type.value}")
            
            return subscription_id
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to {event_type.value}: {e}")
            raise
    
    def unsubscribe_all(self):
        """모든 구독 해제"""
        for subscription_id in self.subscriptions:
            try:
                self.event_bus.unsubscribe(subscription_id)
            except Exception as e:
                self.logger.error(f"Failed to unsubscribe {subscription_id}: {e}")
        
        self.subscriptions.clear()
        self.logger.info("All subscriptions removed")
    
    def publish_status_update(self, status: str, details: Optional[Dict[str, Any]] = None):
        """상태 업데이트 이벤트 발행"""
        data = {
            "component": self.component_name,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            data.update(details)
        
        self.publish_event(
            event_type=EventType.SYSTEM_STATUS,
            data=data,
            priority=EventPriority.NORMAL
        )
    
    def publish_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """에러 이벤트 발행"""
        data = {
            "component": self.component_name,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        }
        
        if context:
            data["context"] = context
        
        self.publish_event(
            event_type=EventType.SYSTEM_ERROR,
            data=data,
            priority=EventPriority.HIGH
        )
    
    def publish_heartbeat(self, metrics: Optional[Dict[str, Any]] = None):
        """하트비트 이벤트 발행"""
        data = {
            "component": self.component_name,
            "status": "alive",
            "timestamp": datetime.now().isoformat()
        }
        
        if metrics:
            data["metrics"] = metrics
        
        self.publish_event(
            event_type=EventType.HEARTBEAT,
            data=data,
            priority=EventPriority.LOW
        )


class AsyncEventBusAdapter:
    """비동기 Event Bus 어댑터"""
    
    def __init__(self, event_bus: EnhancedEventBus, component_name: str):
        self.event_bus = event_bus
        self.component_name = component_name
        self.logger = logging.getLogger(f"{__name__}.{component_name}")
        self.subscriptions: List[str] = []
        self._loop = None
    
    async def async_publish_event(self,
                                  event_type: EventType,
                                  data: Dict[str, Any],
                                  priority: EventPriority = EventPriority.NORMAL,
                                  correlation_id: Optional[str] = None,
                                  ttl: Optional[int] = None) -> bool:
        """비동기 이벤트 발행"""
        loop = asyncio.get_event_loop()
        
        return await loop.run_in_executor(
            None,
            lambda: EventBusAdapter(self.event_bus, self.component_name).publish_event(
                event_type, data, priority, correlation_id, ttl
            )
        )
    
    async def async_subscribe_event(self,
                                    event_type: EventType,
                                    async_callback: Callable[[Event], Awaitable[None]],
                                    event_filter: Optional[EventFilter] = None) -> str:
        """비동기 이벤트 구독"""
        
        def sync_wrapper(event: Event):
            """동기 콜백을 비동기로 래핑"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(async_callback(event))
            finally:
                loop.close()
        
        return self.event_bus.subscribe(
            event_type=event_type,
            callback=sync_wrapper,
            event_filter=event_filter
        )
    
    async def start_heartbeat(self, interval: int = 60):
        """주기적 하트비트 시작"""
        while True:
            try:
                await self.async_publish_event(
                    event_type=EventType.HEARTBEAT,
                    data={
                        "component": self.component_name,
                        "status": "alive",
                        "timestamp": datetime.now().isoformat()
                    },
                    priority=EventPriority.LOW
                )
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in heartbeat: {e}")
                await asyncio.sleep(5)


class EngineEventMixin:
    """엔진 클래스에 Event Bus 기능을 추가하는 Mixin"""
    
    def init_event_bus(self, event_bus: EnhancedEventBus, component_name: str):
        """Event Bus 초기화"""
        self.event_adapter = EventBusAdapter(event_bus, component_name)
        self.component_name = component_name
        
        # 기본 이벤트 구독
        self._subscribe_system_events()
    
    def _subscribe_system_events(self):
        """시스템 이벤트 구독 (오버라이드 가능)"""
        pass
    
    def publish_event(self, event_type: EventType, data: Dict[str, Any], **kwargs):
        """이벤트 발행 (편의 메서드)"""
        return self.event_adapter.publish_event(event_type, data, **kwargs)
    
    def publish_started_event(self):
        """시작 이벤트 발행"""
        self.publish_event(
            EventType.ENGINE_STARTED,
            {
                "component": self.component_name,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    def publish_stopped_event(self):
        """중지 이벤트 발행"""
        self.publish_event(
            EventType.ENGINE_STOPPED,
            {
                "component": self.component_name,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    def cleanup_event_bus(self):
        """Event Bus 정리"""
        if hasattr(self, 'event_adapter'):
            self.event_adapter.unsubscribe_all()


class MarketDataPublisher(EventBusAdapter):
    """시장 데이터 발행 전용 어댑터"""
    
    def publish_market_data(self, symbol: str, price_data: Dict[str, Any]):
        """시장 데이터 발행"""
        return self.publish_event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            data={
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                **price_data
            },
            priority=EventPriority.HIGH
        )
    
    def publish_candle_update(self, symbol: str, timeframe: str, candle_data: Dict[str, Any]):
        """캔들 데이터 업데이트 발행"""
        return self.publish_event(
            event_type=EventType.CANDLE_UPDATED,
            data={
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": datetime.now().isoformat(),
                **candle_data
            },
            priority=EventPriority.HIGH
        )
    
    def publish_indicators_update(self, symbol: str, indicators: Dict[str, float]):
        """기술적 지표 업데이트 발행"""
        return self.publish_event(
            event_type=EventType.INDICATORS_UPDATED,
            data={
                "symbol": symbol,
                "indicators": indicators,
                "timestamp": datetime.now().isoformat()
            },
            priority=EventPriority.NORMAL
        )


class TradingSignalPublisher(EventBusAdapter):
    """거래 신호 발행 전용 어댑터"""
    
    def publish_trading_signal(self, 
                               symbol: str,
                               action: str,
                               price: float,
                               quantity: int,
                               strategy_name: str,
                               confidence: float = 1.0,
                               metadata: Optional[Dict[str, Any]] = None):
        """거래 신호 발행"""
        data = {
            "symbol": symbol,
            "action": action,
            "price": price,
            "quantity": quantity,
            "strategy_name": strategy_name,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
        
        if metadata:
            data["metadata"] = metadata
        
        return self.publish_event(
            event_type=EventType.TRADING_SIGNAL,
            data=data,
            priority=EventPriority.HIGH
        )
    
    def publish_strategy_signal(self, 
                                strategy_name: str,
                                signal_data: Dict[str, Any]):
        """전략 신호 발행"""
        return self.publish_event(
            event_type=EventType.STRATEGY_SIGNAL,
            data={
                "strategy_name": strategy_name,
                "timestamp": datetime.now().isoformat(),
                **signal_data
            },
            priority=EventPriority.NORMAL
        )


class OrderEventPublisher(EventBusAdapter):
    """주문 이벤트 발행 전용 어댑터"""
    
    def publish_order_placed(self, order_data: Dict[str, Any]):
        """주문 등록 이벤트 발행"""
        return self.publish_event(
            event_type=EventType.ORDER_PLACED,
            data={
                "timestamp": datetime.now().isoformat(),
                **order_data
            },
            priority=EventPriority.HIGH
        )
    
    def publish_order_executed(self, execution_data: Dict[str, Any]):
        """주문 체결 이벤트 발행"""
        return self.publish_event(
            event_type=EventType.ORDER_EXECUTED,
            data={
                "timestamp": datetime.now().isoformat(),
                **execution_data
            },
            priority=EventPriority.HIGH
        )
    
    def publish_order_failed(self, order_id: str, reason: str, details: Optional[Dict[str, Any]] = None):
        """주문 실패 이벤트 발행"""
        data = {
            "order_id": order_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            data.update(details)
        
        return self.publish_event(
            event_type=EventType.ORDER_FAILED,
            data=data,
            priority=EventPriority.HIGH
        )


class RiskEventPublisher(EventBusAdapter):
    """리스크 이벤트 발행 전용 어댑터"""
    
    def publish_risk_alert(self, 
                           alert_type: str,
                           severity: str,
                           message: str,
                           details: Optional[Dict[str, Any]] = None):
        """리스크 경고 발행"""
        data = {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            data.update(details)
        
        priority = EventPriority.CRITICAL if severity == "CRITICAL" else EventPriority.HIGH
        
        return self.publish_event(
            event_type=EventType.RISK_ALERT,
            data=data,
            priority=priority
        )
    
    def publish_emergency_stop(self, reason: str, details: Optional[Dict[str, Any]] = None):
        """비상 정지 이벤트 발행"""
        data = {
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            data.update(details)
        
        return self.publish_event(
            event_type=EventType.EMERGENCY_STOP,
            data=data,
            priority=EventPriority.CRITICAL
        )
    
    def publish_position_updated(self, position_data: Dict[str, Any]):
        """포지션 업데이트 이벤트 발행"""
        return self.publish_event(
            event_type=EventType.POSITION_UPDATED,
            data={
                "timestamp": datetime.now().isoformat(),
                **position_data
            },
            priority=EventPriority.NORMAL
        )