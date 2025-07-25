import pytest
import time
import threading
from datetime import datetime
from unittest.mock import Mock, patch
import sys
import os

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qb.utils.redis_manager import RedisManager
from qb.utils.event_bus import EventBus, Event, EventType

class TestEventBus:
    """EventBus 테스트"""
    
    @pytest.fixture
    def redis_manager(self):
        """Redis Manager 픽스처"""
        # 테스트용 Redis 연결 (실제 테스트 환경에서는 Mock 사용 권장)
        return RedisManager(host='localhost', port=6379, db=15)  # 테스트용 DB
        
    @pytest.fixture
    def event_bus(self, redis_manager):
        """EventBus 픽스처"""
        bus = EventBus(redis_manager)
        bus.start()
        yield bus
        bus.stop()
        
    def test_event_creation(self):
        """이벤트 생성 테스트"""
        event = Event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source='TestSource',
            timestamp=datetime.now(),
            data={'symbol': 'AAPL', 'price': 150.0},
            correlation_id='test-123'
        )
        
        assert event.event_type == EventType.MARKET_DATA_RECEIVED
        assert event.source == 'TestSource'
        assert event.data['symbol'] == 'AAPL'
        assert event.correlation_id == 'test-123'
        
    def test_event_serialization(self):
        """이벤트 직렬화/역직렬화 테스트"""
        original = Event(
            event_type=EventType.TRADING_SIGNAL,
            source='StrategyEngine',
            timestamp=datetime.now(),
            data={'action': 'BUY', 'symbol': 'GOOGL', 'quantity': 10}
        )
        
        # 직렬화
        dict_data = original.to_dict()
        assert dict_data['event_type'] == 'trading_signal'
        assert dict_data['source'] == 'StrategyEngine'
        
        # 역직렬화
        restored = Event.from_dict(dict_data)
        assert restored.event_type == original.event_type
        assert restored.source == original.source
        assert restored.data == original.data
        
    def test_publish_subscribe(self, event_bus):
        """발행/구독 기본 테스트"""
        received_events = []
        
        def callback(event: Event):
            received_events.append(event)
            
        # 구독
        event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, callback)
        
        # 이벤트 발행
        test_event = Event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source='TestPublisher',
            timestamp=datetime.now(),
            data={'test': 'data'}
        )
        
        event_bus.publish(test_event)
        
        # 이벤트 처리 대기
        time.sleep(0.5)
        
        # 검증
        assert len(received_events) == 1
        assert received_events[0].source == 'TestPublisher'
        assert received_events[0].data == {'test': 'data'}
        
    def test_multiple_subscribers(self, event_bus):
        """다중 구독자 테스트"""
        results = {'sub1': [], 'sub2': []}
        
        def subscriber1(event: Event):
            results['sub1'].append(event)
            
        def subscriber2(event: Event):
            results['sub2'].append(event)
            
        # 두 구독자 등록
        event_bus.subscribe(EventType.INDICATORS_UPDATED, subscriber1)
        event_bus.subscribe(EventType.INDICATORS_UPDATED, subscriber2)
        
        # 이벤트 발행
        test_event = Event(
            event_type=EventType.INDICATORS_UPDATED,
            source='TechnicalAnalyzer',
            timestamp=datetime.now(),
            data={'rsi': 65.5}
        )
        
        event_bus.publish(test_event)
        time.sleep(0.5)
        
        # 두 구독자 모두 이벤트를 받아야 함
        assert len(results['sub1']) == 1
        assert len(results['sub2']) == 1
        
    def test_unsubscribe(self, event_bus):
        """구독 해제 테스트"""
        received_events = []
        
        def callback(event: Event):
            received_events.append(event)
            
        # 구독
        event_bus.subscribe(EventType.ORDER_EXECUTED, callback)
        
        # 첫 번째 이벤트
        event1 = Event(
            event_type=EventType.ORDER_EXECUTED,
            source='OrderEngine',
            timestamp=datetime.now(),
            data={'order_id': '123'}
        )
        event_bus.publish(event1)
        time.sleep(0.5)
        
        # 구독 해제
        event_bus.unsubscribe(EventType.ORDER_EXECUTED, callback)
        
        # 두 번째 이벤트
        event2 = Event(
            event_type=EventType.ORDER_EXECUTED,
            source='OrderEngine',
            timestamp=datetime.now(),
            data={'order_id': '456'}
        )
        event_bus.publish(event2)
        time.sleep(0.5)
        
        # 첫 번째 이벤트만 받아야 함
        assert len(received_events) == 1
        assert received_events[0].data['order_id'] == '123'
        
    def test_error_handling(self, event_bus):
        """에러 처리 테스트"""
        def failing_callback(event: Event):
            raise Exception("Test error")
            
        # 에러가 발생하는 콜백 등록
        event_bus.subscribe(EventType.ERROR_OCCURRED, failing_callback)
        
        # 이벤트 발행
        test_event = Event(
            event_type=EventType.ERROR_OCCURRED,
            source='TestSource',
            timestamp=datetime.now(),
            data={'error': 'test'}
        )
        
        # 에러가 발생해도 시스템이 멈추지 않아야 함
        event_bus.publish(test_event)
        time.sleep(0.5)
        
        # 통계 확인
        stats = event_bus.get_stats()
        assert stats['failed'] > 0
        
    def test_concurrent_publishing(self, event_bus):
        """동시 발행 테스트"""
        received_events = []
        lock = threading.Lock()
        
        def callback(event: Event):
            with lock:
                received_events.append(event)
                
        event_bus.subscribe(EventType.SYSTEM_STATUS, callback)
        
        # 여러 스레드에서 동시에 이벤트 발행
        def publish_events(thread_id):
            for i in range(10):
                event = Event(
                    event_type=EventType.SYSTEM_STATUS,
                    source=f'Thread-{thread_id}',
                    timestamp=datetime.now(),
                    data={'count': i}
                )
                event_bus.publish(event)
                
        threads = []
        for i in range(5):
            t = threading.Thread(target=publish_events, args=(i,))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        time.sleep(1)  # 모든 이벤트 처리 대기
        
        # 50개의 이벤트가 모두 수신되어야 함
        assert len(received_events) == 50
        
    def test_event_stats(self, event_bus):
        """이벤트 통계 테스트"""
        def callback(event: Event):
            pass
            
        event_bus.subscribe(EventType.HEARTBEAT, callback)
        
        # 여러 이벤트 발행
        for i in range(5):
            event = Event(
                event_type=EventType.HEARTBEAT,
                source='TestSource',
                timestamp=datetime.now(),
                data={'count': i}
            )
            event_bus.publish(event)
            
        time.sleep(0.5)
        
        stats = event_bus.get_stats()
        assert stats['published'] >= 5
        assert stats['received'] >= 5
        assert stats['processed'] >= 5
        
    def test_create_event_helper(self, event_bus):
        """이벤트 생성 헬퍼 메서드 테스트"""
        event = event_bus.create_event(
            event_type=EventType.RISK_ALERT,
            source='RiskEngine',
            data={'level': 'HIGH', 'message': 'Position size exceeded'},
            correlation_id='risk-001'
        )
        
        assert event.event_type == EventType.RISK_ALERT
        assert event.source == 'RiskEngine'
        assert event.data['level'] == 'HIGH'
        assert event.correlation_id == 'risk-001'
        
    @pytest.mark.skip(reason="하트비트 테스트는 시간이 오래 걸림")
    def test_heartbeat_broadcast(self, event_bus):
        """하트비트 브로드캐스트 테스트"""
        received_heartbeats = []
        
        def callback(event: Event):
            received_heartbeats.append(event)
            
        event_bus.subscribe(EventType.HEARTBEAT, callback)
        
        # 하트비트 시작 (1초 간격)
        event_bus.broadcast_heartbeat('TestService', interval=1)
        
        # 3초 대기
        time.sleep(3.5)
        
        # 최소 3개의 하트비트를 받아야 함
        assert len(received_heartbeats) >= 3
        
        # 하트비트 데이터 확인
        for hb in received_heartbeats:
            assert hb.source == 'TestService'
            assert hb.data['status'] == 'alive'
            assert 'stats' in hb.data

if __name__ == '__main__':
    pytest.main([__file__, '-v'])