"""
Event Bus 통합 테스트

새로운 EnhancedEventBus와 모든 엔진들의 연동을 테스트합니다.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

from qb.engines.event_bus import (
    EnhancedEventBus, Event, EventType, EventPriority, EventFilter
)
from qb.engines.event_bus.adapters import (
    EventBusAdapter, MarketDataPublisher, TradingSignalPublisher, 
    OrderEventPublisher, RiskEventPublisher
)
from qb.engines.event_bus.handlers import (
    MarketDataEventHandler, TradingSignalEventHandler, 
    RiskAlertEventHandler, SystemEventHandler
)
from qb.utils.redis_manager import RedisManager


class TestEventBusIntegration:
    """Event Bus 통합 테스트 클래스"""
    
    @pytest.fixture
    def redis_manager(self):
        """Redis Manager Mock"""
        mock_redis = Mock()
        mock_redis.redis.ping.return_value = True
        mock_redis.redis.publish.return_value = 1
        mock_redis.redis.pubsub.return_value = Mock()
        return mock_redis
    
    @pytest.fixture
    def event_bus(self, redis_manager):
        """Enhanced Event Bus 인스턴스"""
        return EnhancedEventBus(
            redis_manager=redis_manager,
            max_workers=5,
            batch_size=10
        )
    
    @pytest.fixture
    def started_event_bus(self, event_bus):
        """시작된 Event Bus"""
        event_bus.start()
        yield event_bus
        event_bus.stop()
    
    def test_enhanced_event_creation(self, event_bus):
        """향상된 이벤트 생성 테스트"""
        event = event_bus.create_event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source="DataCollector",
            data={"symbol": "AAPL", "price": 150.0},
            priority=EventPriority.HIGH,
            ttl=60
        )
        
        assert event.event_type == EventType.MARKET_DATA_RECEIVED
        assert event.source == "DataCollector"
        assert event.data["symbol"] == "AAPL"
        assert event.data["price"] == 150.0
        # correlation_id는 선택사항
    
    def test_event_filter(self):
        """이벤트 필터 테스트"""
        # 시장 데이터만 허용하는 필터
        filter_market = EventFilter(
            event_types={EventType.MARKET_DATA_RECEIVED}
        )
        
        # 테스트 이벤트들
        market_event = Event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source="Test",
            timestamp=datetime.now(),
            data={}
        )
        
        trading_event = Event(
            event_type=EventType.TRADING_SIGNAL,
            source="Test",
            timestamp=datetime.now(),
            data={}
        )
        
        assert filter_market.matches(market_event)
        assert not filter_market.matches(trading_event)
    
    def test_market_data_publisher(self, started_event_bus):
        """시장 데이터 발행자 테스트"""
        publisher = MarketDataPublisher(started_event_bus, "TestDataCollector")
        
        # 시장 데이터 발행
        result = publisher.publish_market_data(
            symbol="AAPL",
            price_data={
                "open": 149.0,
                "high": 151.0,
                "low": 148.5,
                "close": 150.0,
                "volume": 1000000
            }
        )
        
        assert result is True
        
        # 지표 업데이트 발행
        result = publisher.publish_indicators_update(
            symbol="AAPL",
            indicators={
                "sma_20": 148.5,
                "rsi": 65.5,
                "macd": 2.1
            }
        )
        
        assert result is True
    
    def test_trading_signal_publisher(self, started_event_bus):
        """거래 신호 발행자 테스트"""
        publisher = TradingSignalPublisher(started_event_bus, "TestStrategy")
        
        result = publisher.publish_trading_signal(
            symbol="AAPL",
            action="BUY",
            price=150.0,
            quantity=100,
            strategy_name="MovingAverageStrategy",
            confidence=0.85,
            metadata={"reason": "Golden cross detected"}
        )
        
        assert result is True
    
    def test_risk_event_publisher(self, started_event_bus):
        """리스크 이벤트 발행자 테스트"""
        publisher = RiskEventPublisher(started_event_bus, "TestRiskEngine")
        
        # 리스크 경고 발행
        result = publisher.publish_risk_alert(
            alert_type="POSITION_LIMIT",
            severity="WARNING",
            message="Position size approaching limit",
            details={"current_ratio": 0.08, "limit_ratio": 0.10}
        )
        
        assert result is True
        
        # 비상 정지 발행
        result = publisher.publish_emergency_stop(
            reason="Daily loss limit exceeded",
            details={"daily_loss": -50000, "limit": -45000}
        )
        
        assert result is True
    
    def test_event_handlers(self, started_event_bus):
        """이벤트 핸들러 테스트"""
        processed_events = []
        
        def data_processor(symbol, data):
            processed_events.append(("market_data", symbol, data))
        
        def signal_processor(data):
            processed_events.append(("trading_signal", data))
        
        def alert_processor(data):
            processed_events.append(("risk_alert", data))
        
        # 핸들러 생성
        market_handler = MarketDataEventHandler("TestHandler", data_processor)
        signal_handler = TradingSignalEventHandler("TestHandler", signal_processor)
        risk_handler = RiskAlertEventHandler("TestHandler", alert_processor)
        
        # 구독
        started_event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, market_handler)
        started_event_bus.subscribe(EventType.TRADING_SIGNAL, signal_handler)
        started_event_bus.subscribe(EventType.RISK_ALERT, risk_handler)
        
        # 이벤트 발행
        market_event = started_event_bus.create_event(
            EventType.MARKET_DATA_RECEIVED,
            "TestSource",
            {"symbol": "AAPL", "price": 150.0}
        )
        started_event_bus.publish(market_event)
        
        signal_event = started_event_bus.create_event(
            EventType.TRADING_SIGNAL,
            "TestSource",
            {"symbol": "AAPL", "action": "BUY", "strategy_name": "Test"}
        )
        started_event_bus.publish(signal_event)
        
        risk_event = started_event_bus.create_event(
            EventType.RISK_ALERT,
            "TestSource",
            {"alert_type": "TEST", "severity": "LOW", "message": "Test alert"}
        )
        started_event_bus.publish(risk_event)
        
        # 처리 대기
        time.sleep(0.5)
        
        # 통계 확인
        assert market_handler.processed_count > 0
        assert signal_handler.processed_count > 0
        assert risk_handler.processed_count > 0
    
    def test_system_event_handler(self, started_event_bus):
        """시스템 이벤트 핸들러 테스트"""
        system_handler = SystemEventHandler("TestSystemHandler")
        
        # 시스템 이벤트 구독
        started_event_bus.subscribe(EventType.ENGINE_STARTED, system_handler)
        started_event_bus.subscribe(EventType.SYSTEM_ERROR, system_handler)
        started_event_bus.subscribe(EventType.HEARTBEAT, system_handler)
        
        # 엔진 시작 이벤트
        started_event = started_event_bus.create_event(
            EventType.ENGINE_STARTED,
            "TestEngine",
            {"component": "TestComponent"}
        )
        started_event_bus.publish(started_event)
        
        # 시스템 에러 이벤트
        error_event = started_event_bus.create_event(
            EventType.SYSTEM_ERROR,
            "TestEngine",
            {
                "component": "TestComponent",
                "error_type": "ConnectionError",
                "error_message": "Failed to connect to database"
            }
        )
        started_event_bus.publish(error_event)
        
        # 하트비트 이벤트
        heartbeat_event = started_event_bus.create_event(
            EventType.HEARTBEAT,
            "TestEngine",
            {"component": "TestComponent", "status": "alive"}
        )
        started_event_bus.publish(heartbeat_event)
        
        # 처리 대기
        time.sleep(0.5)
        
        # 통계 확인
        stats = system_handler.get_stats()
        assert stats["processed_count"] >= 3
        assert "TestComponent" in stats["engine_statuses"]
        assert len(stats["error_events"]) >= 1
    
    def test_circuit_breaker(self, started_event_bus):
        """서킷 브레이커 테스트"""
        error_count = 0
        
        def failing_handler(event):
            nonlocal error_count
            error_count += 1
            raise Exception(f"Handler error {error_count}")
        
        # 서킷 브레이커 활성화된 이벤트 버스 생성
        cb_event_bus = EnhancedEventBus(
            redis_manager=started_event_bus.redis_manager,
            enable_circuit_breaker=True
        )
        cb_event_bus.start()
        
        try:
            # 실패하는 핸들러 구독
            cb_event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, failing_handler)
            
            # 여러 이벤트 발행 (서킷 브레이커 트리거)
            for i in range(10):
                event = cb_event_bus.create_event(
                    EventType.MARKET_DATA_RECEIVED,
                    "TestSource",
                    {"test_data": i}
                )
                cb_event_bus.publish(event)
            
            # 처리 대기
            time.sleep(1.0)
            
            # 메트릭 확인
            metrics = cb_event_bus.get_metrics()
            assert metrics["total"]["failed"] > 0
            
        finally:
            cb_event_bus.stop()
    
    def test_event_bus_metrics(self, started_event_bus):
        """이벤트 버스 메트릭 테스트"""
        # 여러 이벤트 발행
        for i in range(5):
            event = started_event_bus.create_event(
                EventType.MARKET_DATA_RECEIVED,
                "TestSource",
                {"test_id": i}
            )
            started_event_bus.publish(event)
        
        # 메트릭 확인
        metrics = started_event_bus.get_metrics()
        
        assert "total" in metrics
        assert "performance" in metrics
        assert "by_type" in metrics
        
        assert metrics["total"]["published"] >= 5
        assert "success_rate" in metrics["performance"]
        assert EventType.MARKET_DATA_RECEIVED.value in metrics["by_type"]
    
    def test_subscription_management(self, started_event_bus):
        """구독 관리 테스트"""
        processed_count = 0
        
        def test_handler(event):
            nonlocal processed_count
            processed_count += 1
        
        # 구독 추가
        sub_id = started_event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, test_handler)
        
        # 이벤트 발행
        event = started_event_bus.create_event(
            EventType.MARKET_DATA_RECEIVED,
            "TestSource",
            {"test": "data"}
        )
        started_event_bus.publish(event)
        
        # 처리 대기
        time.sleep(0.2)
        assert processed_count == 1
        
        # 구독 해제
        started_event_bus.unsubscribe(sub_id)
        
        # 다시 이벤트 발행
        started_event_bus.publish(event)
        time.sleep(0.2)
        
        # 처리되지 않아야 함
        assert processed_count == 1
        
        # 구독 통계 확인
        stats = started_event_bus.get_subscription_stats()
        assert stats["total_subscriptions"] >= 0
    
    def test_health_check(self, started_event_bus):
        """헬스 체크 테스트"""
        health = started_event_bus.health_check()
        
        assert "running" in health
        assert "redis_healthy" in health
        assert "metrics" in health
        
        assert health["running"] is True
    
    def test_batch_processing(self, redis_manager):
        """배치 처리 테스트"""
        processed_events = []
        
        def batch_handler(event):
            processed_events.append(event.data["batch_id"])
        
        # 배치 크기 2로 설정
        batch_event_bus = EnhancedEventBus(
            redis_manager=redis_manager,
            batch_size=2,
            batch_timeout=0.1
        )
        batch_event_bus.start()
        
        try:
            batch_event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, batch_handler)
            
            # 3개 이벤트 발행 (배치 크기 2 + 타임아웃 1)
            for i in range(3):
                event = batch_event_bus.create_event(
                    EventType.MARKET_DATA_RECEIVED,
                    "TestSource",
                    {"batch_id": i}
                )
                batch_event_bus.publish(event)
                
                if i == 1:  # 배치 크기 도달 후 잠시 대기
                    time.sleep(0.05)
            
            # 타임아웃 대기
            time.sleep(0.2)
            
            # 모든 이벤트가 처리되었는지 확인
            assert len(processed_events) == 3
            assert set(processed_events) == {0, 1, 2}
            
        finally:
            batch_event_bus.stop()


@pytest.mark.integration
class TestEngineEventBusIntegration:
    """엔진별 Event Bus 연동 통합 테스트"""
    
    @pytest.fixture
    def mock_engines(self):
        """Mock 엔진들"""
        return {
            "strategy": Mock(),
            "risk": Mock(), 
            "order": Mock(),
            "data_collector": Mock()
        }
    
    def test_end_to_end_trading_flow(self, started_event_bus, mock_engines):
        """전체 거래 플로우 통합 테스트"""
        events_received = []
        
        def capture_event(event_type):
            def handler(event):
                events_received.append((event_type, event.data))
            return handler
        
        # 각 이벤트 타입별 핸들러 등록
        started_event_bus.subscribe(
            EventType.MARKET_DATA_RECEIVED, 
            capture_event("market_data")
        )
        started_event_bus.subscribe(
            EventType.TRADING_SIGNAL, 
            capture_event("trading_signal")
        )
        started_event_bus.subscribe(
            EventType.RISK_ALERT, 
            capture_event("risk_alert")
        )
        started_event_bus.subscribe(
            EventType.ORDER_PLACED, 
            capture_event("order_placed")
        )
        
        # 1. 시장 데이터 수신
        market_data_pub = MarketDataPublisher(started_event_bus, "DataCollector")
        market_data_pub.publish_market_data(
            "AAPL", 
            {"open": 149.0, "close": 150.0, "volume": 1000000}
        )
        
        # 2. 거래 신호 생성
        signal_pub = TradingSignalPublisher(started_event_bus, "StrategyEngine")
        signal_pub.publish_trading_signal(
            symbol="AAPL",
            action="BUY",
            price=150.0,
            quantity=100,
            strategy_name="TestStrategy"
        )
        
        # 3. 리스크 체크 (경고)
        risk_pub = RiskEventPublisher(started_event_bus, "RiskEngine")
        risk_pub.publish_risk_alert(
            alert_type="POSITION_SIZE",
            severity="WARNING",
            message="Position size check"
        )
        
        # 4. 주문 실행
        order_pub = OrderEventPublisher(started_event_bus, "OrderEngine")
        order_pub.publish_order_placed({
            "order_id": "order_123",
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 100,
            "price": 150.0
        })
        
        # 처리 대기
        time.sleep(0.5)
        
        # 이벤트 플로우 검증
        event_types = [event[0] for event in events_received]
        assert "market_data" in event_types
        assert "trading_signal" in event_types
        assert "risk_alert" in event_types
        assert "order_placed" in event_types
        
        # 각 이벤트 데이터 검증
        market_events = [e[1] for e in events_received if e[0] == "market_data"]
        assert len(market_events) > 0
        assert market_events[0]["symbol"] == "AAPL"
        
        signal_events = [e[1] for e in events_received if e[0] == "trading_signal"]
        assert len(signal_events) > 0
        assert signal_events[0]["action"] == "BUY"
    
    def test_error_propagation(self, started_event_bus):
        """에러 전파 테스트"""
        system_errors = []
        
        def error_handler(event):
            system_errors.append(event.data)
        
        started_event_bus.subscribe(EventType.SYSTEM_ERROR, error_handler)
        
        # 에러 이벤트 발행
        adapter = EventBusAdapter(started_event_bus, "TestComponent")
        adapter.publish_error(
            ValueError("Test error"),
            context={"operation": "test_operation"}
        )
        
        time.sleep(0.2)
        
        assert len(system_errors) > 0
        assert system_errors[0]["error_type"] == "ValueError"
        assert system_errors[0]["error_message"] == "Test error"