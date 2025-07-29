import redis
import json
import logging
import threading
import time
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor

class EventType(Enum):
    """시스템 이벤트 타입 정의"""
    # 시장 데이터 관련
    MARKET_DATA_RECEIVED = "market_data_received"
    CANDLE_UPDATED = "candle_updated"
    ORDERBOOK_UPDATED = "orderbook_updated"
    TRADE_EXECUTED = "trade_executed"
    
    # 기술적 분석 관련
    INDICATORS_UPDATED = "indicators_updated"
    SIGNAL_GENERATED = "signal_generated"
    
    # 전략 관련
    STRATEGY_SIGNAL = "strategy_signal"
    TRADING_SIGNAL = "trading_signal"
    
    # 주문 관련
    ORDER_PLACED = "order_placed"
    ORDER_EXECUTED = "order_executed"
    ORDER_FAILED = "order_failed"
    ORDER_CANCELLED = "order_cancelled"
    
    # 리스크 관리 관련
    RISK_ALERT = "risk_alert"
    EMERGENCY_STOP = "emergency_stop"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"
    
    # 시스템 관련
    SYSTEM_STATUS = "system_status"
    ERROR_OCCURRED = "error_occurred"
    HEARTBEAT = "heartbeat"

@dataclass
class Event:
    """이벤트 메시지 구조"""
    event_type: EventType
    source: str  # 이벤트 발생 소스 (예: 'DataCollector', 'TechnicalAnalyzer')
    timestamp: datetime
    data: Dict[str, Any]
    correlation_id: Optional[str] = None  # 이벤트 추적용 ID
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'event_type': self.event_type.value,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'data': self.data,
            'correlation_id': self.correlation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """딕셔너리에서 Event 객체 생성"""
        return cls(
            event_type=EventType(data['event_type']),
            source=data['source'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            data=data['data'],
            correlation_id=data.get('correlation_id')
        )

class EventBus:
    """Redis Pub/Sub 기반 이벤트 버스"""
    
    def __init__(self, redis_manager, max_workers: int = 10):
        self.redis_manager = redis_manager
        self.logger = logging.getLogger(__name__)
        self.pubsub = self.redis_manager.redis.pubsub()
        self.subscribers: Dict[str, List[Callable]] = {}
        self.running = False
        self.listener_thread = None
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        
        # 이벤트 통계
        self.event_stats = {
            'published': 0,
            'received': 0,
            'processed': 0,
            'failed': 0
        }
        
    def start(self):
        """이벤트 버스 시작"""
        if self.running:
            self.logger.warning("EventBus is already running")
            return
            
        self.running = True
        self.listener_thread = threading.Thread(target=self._listen_events)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        self.logger.info("EventBus started")
        
    def stop(self):
        """이벤트 버스 중지"""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=5)
        self.executor.shutdown(wait=True)
        self.pubsub.close()
        self.logger.info("EventBus stopped")
        
    def publish(self, event: Event) -> bool:
        """이벤트 발행"""
        try:
            channel = f"event:{event.event_type.value}"
            message = json.dumps(event.to_dict())
            self.redis_manager.redis.publish(channel, message)
            self.event_stats['published'] += 1
            self.logger.info(f"📡 Published event: {event.event_type.value} to channel: {channel} (symbol: {event.data.get('symbol', 'N/A')})")
            return True
        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")
            self.event_stats['failed'] += 1
            return False
            
    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> bool:
        """이벤트 구독"""
        try:
            # EventType enum 또는 문자열 처리
            if isinstance(event_type, EventType):
                channel = f"event:{event_type.value}"
            else:
                # 문자열인 경우 직접 사용
                channel = f"event:{event_type}"
            
            with self._lock:
                if channel not in self.subscribers:
                    self.subscribers[channel] = []
                    self.pubsub.subscribe(channel)
                    
                self.subscribers[channel].append(callback)
            
            event_name = event_type.value if isinstance(event_type, EventType) else event_type
            self.logger.info(f"Subscribed to event: {event_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to subscribe to event: {e}")
            return False
            
    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> bool:
        """이벤트 구독 해제"""
        try:
            # EventType enum 또는 문자열 처리
            if isinstance(event_type, EventType):
                channel = f"event:{event_type.value}"
            else:
                # 문자열인 경우 직접 사용
                channel = f"event:{event_type}"
            
            with self._lock:
                if channel in self.subscribers and callback in self.subscribers[channel]:
                    self.subscribers[channel].remove(callback)
                    
                    # 더 이상 구독자가 없으면 채널 구독 해제
                    if not self.subscribers[channel]:
                        self.pubsub.unsubscribe(channel)
                        del self.subscribers[channel]
            
            event_name = event_type.value if isinstance(event_type, EventType) else event_type
            self.logger.info(f"Unsubscribed from event: {event_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe from event: {e}")
            return False
            
    def _listen_events(self):
        """이벤트 리스닝 (백그라운드 스레드)"""
        self.logger.info("Event listener started")
        
        while self.running:
            try:
                message = self.pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    self.event_stats['received'] += 1
                    self.logger.info(f"📥 Received message on channel: {message['channel']}")
                    self._handle_message(message)
            except Exception as e:
                self.logger.error(f"Error in event listener: {e}")
                time.sleep(1)  # 에러 발생 시 잠시 대기
                
        self.logger.info("Event listener stopped")
        
    def _handle_message(self, message: Dict[str, Any]):
        """메시지 처리"""
        try:
            channel = message['channel'].decode('utf-8') if isinstance(message['channel'], bytes) else message['channel']
            data = message['data'].decode('utf-8') if isinstance(message['data'], bytes) else message['data']
            
            # 이벤트 파싱
            event_data = json.loads(data)
            event = Event.from_dict(event_data)
            
            # 해당 채널의 모든 구독자에게 전달
            callbacks = self.subscribers.get(channel, [])
            for callback in callbacks:
                # 비동기적으로 콜백 실행
                self.executor.submit(self._execute_callback, callback, event)
                
        except Exception as e:
            self.logger.error(f"Failed to handle message: {e}")
            self.event_stats['failed'] += 1
            
    def _execute_callback(self, callback: Callable[[Event], None], event: Event):
        """콜백 실행"""
        try:
            import asyncio
            import inspect
            
            # async 함수인지 확인
            if inspect.iscoroutinefunction(callback):
                # 새로운 이벤트 루프에서 실행
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(callback(event))
                finally:
                    loop.close()
            else:
                # 동기 함수는 그대로 실행
                callback(event)
                
            self.event_stats['processed'] += 1
        except Exception as e:
            self.logger.error(f"Error executing callback for event {event.event_type.value}: {e}")
            self.event_stats['failed'] += 1
            
    def get_stats(self) -> Dict[str, int]:
        """이벤트 처리 통계 반환"""
        return self.event_stats.copy()
        
    def broadcast_heartbeat(self, source: str, interval: int = 60):
        """하트비트 브로드캐스트 (별도 스레드)"""
        def send_heartbeat():
            while self.running:
                heartbeat_event = Event(
                    event_type=EventType.HEARTBEAT,
                    source=source,
                    timestamp=datetime.now(),
                    data={'status': 'alive', 'stats': self.get_stats()}
                )
                self.publish(heartbeat_event)
                time.sleep(interval)
                
        heartbeat_thread = threading.Thread(target=send_heartbeat)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()
        
    def create_event(self, event_type: EventType, source: str, 
                    data: Dict[str, Any], correlation_id: Optional[str] = None) -> Event:
        """이벤트 생성 헬퍼 메서드"""
        return Event(
            event_type=event_type,
            source=source,
            timestamp=datetime.now(),
            data=data,
            correlation_id=correlation_id
        )