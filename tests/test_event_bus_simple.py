"""
간단한 Event Bus 기능 테스트

Event Bus가 기본적으로 작동하는지 확인하는 단순한 테스트
"""

import pytest
import time
from unittest.mock import Mock, MagicMock

from qb.engines.event_bus import EnhancedEventBus, EventType, Event
from qb.engines.event_bus.adapters import MarketDataPublisher


class TestSimpleEventBus:
    """간단한 Event Bus 테스트"""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis Manager"""
        mock = Mock()
        mock.redis = MagicMock()
        mock.redis.ping.return_value = True
        
        # Mock pubsub
        mock_pubsub = MagicMock()
        mock.redis.pubsub.return_value = mock_pubsub
        
        # Mock publish (always succeeds)
        mock.redis.publish.return_value = 1
        
        return mock
    
    def test_event_bus_creation(self, mock_redis_manager):
        """Event Bus 생성 테스트"""
        bus = EnhancedEventBus(mock_redis_manager, max_workers=2)
        
        assert bus is not None
        assert bus.running is False
        assert bus.redis_manager == mock_redis_manager
    
    def test_event_creation(self, mock_redis_manager):
        """이벤트 생성 테스트"""
        bus = EnhancedEventBus(mock_redis_manager)
        
        event = bus.create_event(
            EventType.MARKET_DATA_RECEIVED,
            "TestSource",
            {"symbol": "AAPL", "price": 150.0}
        )
        
        assert event.event_type == EventType.MARKET_DATA_RECEIVED
        assert event.source == "TestSource"
        assert event.data["symbol"] == "AAPL"
        assert event.data["price"] == 150.0
    
    def test_event_publishing_without_subscribers(self, mock_redis_manager):
        """구독자 없이 이벤트 발행 테스트"""
        bus = EnhancedEventBus(mock_redis_manager)
        
        event = bus.create_event(
            EventType.MARKET_DATA_RECEIVED,
            "TestSource", 
            {"test": "data"}
        )
        
        # 시작하지 않고 발행 (Redis publish만 호출됨)
        result = bus.publish(event)
        
        # 발행 자체는 성공해야 함
        assert result is True
        
        # Redis publish가 호출되었는지 확인
        mock_redis_manager.redis.publish.assert_called_once()
    
    def test_metrics_functionality(self, mock_redis_manager):
        """메트릭 기능 테스트"""
        bus = EnhancedEventBus(mock_redis_manager)
        
        # 초기 메트릭
        initial_metrics = bus.get_metrics()
        assert initial_metrics["total"]["published"] == 0
        assert initial_metrics["total"]["received"] == 0
        
        # 이벤트 발행
        event = bus.create_event(EventType.MARKET_DATA_RECEIVED, "Test", {})
        bus.publish(event)
        
        # 메트릭 확인 (published 증가)
        metrics = bus.get_metrics()
        assert metrics["total"]["published"] == 1
        assert "performance" in metrics
        assert "by_type" in metrics
    
    def test_health_check(self, mock_redis_manager):
        """헬스 체크 테스트"""
        bus = EnhancedEventBus(mock_redis_manager)
        
        health = bus.health_check()
        
        assert "running" in health
        assert "redis_healthy" in health
        assert "metrics" in health
        assert health["running"] is False  # 시작하지 않음
        assert health["redis_healthy"] is True
    
    def test_subscription_stats(self, mock_redis_manager):
        """구독 통계 테스트"""
        bus = EnhancedEventBus(mock_redis_manager)
        
        stats = bus.get_subscription_stats()
        
        assert "total_subscriptions" in stats
        assert "channel_subscriptions" in stats
        assert stats["total_subscriptions"] == 0  # 구독자 없음
    
    def test_adapter_creation(self, mock_redis_manager):
        """어댑터 생성 테스트"""
        bus = EnhancedEventBus(mock_redis_manager)
        
        publisher = MarketDataPublisher(bus, "TestDataCollector")
        
        assert publisher.event_bus == bus
        assert publisher.component_name == "TestDataCollector"
    
    def test_adapter_publish_market_data(self, mock_redis_manager):
        """어댑터를 통한 시장 데이터 발행 테스트"""
        bus = EnhancedEventBus(mock_redis_manager)
        publisher = MarketDataPublisher(bus, "TestDataCollector")
        
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
        
        # Redis publish가 호출되었는지 확인
        mock_redis_manager.redis.publish.assert_called()
        
        # 메트릭 확인
        metrics = bus.get_metrics()
        assert metrics["total"]["published"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])