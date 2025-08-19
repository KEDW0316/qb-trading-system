"""
QuickBit Integration Tests

통합 테스트 - 시스템 전체 동작 검증
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from qb.engines.event_bus.engine import EventBusEngine
from qb.engines.data_collector.engine import DataCollectorEngine
from qb.engines.strategy_engine.engine import StrategyEngine
from qb.engines.order_engine.engine import OrderEngine
from qb.engines.risk_engine.engine import RiskEngine


class TestSystemIntegration:
    """시스템 통합 테스트"""
    
    @pytest.fixture
    async def event_bus(self):
        """이벤트 버스 픽스처"""
        bus = EventBusEngine()
        await bus.initialize()
        yield bus
        await bus.shutdown()
    
    @pytest.fixture
    async def engines(self, event_bus):
        """엔진 세트 픽스처"""
        return {
            'event_bus': event_bus,
            'data_collector': DataCollectorEngine(event_bus),
            'strategy': StrategyEngine(event_bus),
            'order': OrderEngine(event_bus),
            'risk': RiskEngine(event_bus)
        }
    
    @pytest.mark.asyncio
    async def test_engine_initialization(self, engines):
        """엔진 초기화 테스트"""
        # 모든 엔진 초기화
        for name, engine in engines.items():
            if name != 'event_bus':  # 이미 초기화됨
                await engine.initialize()
                assert engine.is_running
    
    @pytest.mark.asyncio
    async def test_event_flow(self, engines):
        """이벤트 플로우 테스트"""
        event_bus = engines['event_bus']
        
        # 이벤트 수신 확인용 핸들러
        received_events = []
        
        async def test_handler(event):
            received_events.append(event)
        
        # 핸들러 등록
        event_bus.subscribe('test_event', test_handler)
        
        # 이벤트 발행
        test_data = {'message': 'test'}
        await event_bus.publish('test_event', test_data)
        
        # 짧은 대기
        await asyncio.sleep(0.1)
        
        # 이벤트 수신 확인
        assert len(received_events) == 1
        assert received_events[0]['message'] == 'test'