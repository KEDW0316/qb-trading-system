"""
오프라인 시스템 통합 테스트

실제 API 연결 없이 시스템 통합을 테스트
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from qb.engines.event_bus.engine import EventBusEngine
from qb.engines.data_collector.engine import DataCollectorEngine
from qb.engines.strategy_engine.engine import StrategyEngine
from qb.engines.order_engine.engine import OrderEngine
from qb.engines.risk_engine.engine import RiskEngine


class TestOfflineSystemIntegration:
    """오프라인 시스템 통합 테스트"""
    
    @pytest.fixture
    async def mock_kis_client(self):
        """Mock KIS 클라이언트"""
        client = AsyncMock()
        client.is_connected = True
        client.get_balance = AsyncMock(return_value={'cash': 1000000})
        client.get_positions = AsyncMock(return_value=[])
        client.place_order = AsyncMock(return_value={'order_id': 'TEST001'})
        return client
    
    @pytest.fixture
    async def system(self, mock_kis_client):
        """테스트용 시스템 설정"""
        event_bus = EventBusEngine()
        await event_bus.initialize()
        
        # 엔진들 생성
        engines = {
            'event_bus': event_bus,
            'data_collector': DataCollectorEngine(event_bus),
            'strategy': StrategyEngine(event_bus),
            'order': OrderEngine(event_bus),
            'risk': RiskEngine(event_bus)
        }
        
        # Mock 클라이언트 주입
        engines['data_collector'].kis_client = mock_kis_client
        engines['order'].kis_client = mock_kis_client
        
        yield engines
        
        # 정리
        await event_bus.shutdown()
    
    @pytest.mark.asyncio
    async def test_full_trading_cycle(self, system):
        """전체 트레이딩 사이클 테스트"""
        event_bus = system['event_bus']
        
        # 1. 시장 데이터 수신 시뮬레이션
        market_data = {
            'symbol': '005930',
            'price': 70000,
            'volume': 1000000,
            'timestamp': datetime.now()
        }
        
        await event_bus.publish('market_data', market_data)
        await asyncio.sleep(0.1)
        
        # 2. 전략 신호 생성 시뮬레이션
        signal = {
            'symbol': '005930',
            'action': 'BUY',
            'quantity': 10,
            'price': 70000,
            'strategy_id': 'test_strategy'
        }
        
        await event_bus.publish('strategy_signal', signal)
        await asyncio.sleep(0.1)
        
        # 3. 리스크 체크 시뮬레이션
        risk_check = {
            'signal': signal,
            'approved': True,
            'reason': 'Risk check passed'
        }
        
        await event_bus.publish('risk_check', risk_check)
        await asyncio.sleep(0.1)
        
        # 4. 주문 실행 확인
        # Mock 클라이언트의 place_order가 호출되었는지 확인
        assert system['order'].kis_client.place_order.called
    
    @pytest.mark.asyncio
    async def test_risk_rejection(self, system):
        """리스크 체크 거부 테스트"""
        event_bus = system['event_bus']
        
        # 고위험 신호 생성
        high_risk_signal = {
            'symbol': '005930',
            'action': 'BUY',
            'quantity': 10000,  # 과도한 수량
            'price': 70000,
            'strategy_id': 'test_strategy'
        }
        
        await event_bus.publish('strategy_signal', high_risk_signal)
        
        # 리스크 체크 거부
        risk_rejection = {
            'signal': high_risk_signal,
            'approved': False,
            'reason': 'Position size exceeds limit'
        }
        
        await event_bus.publish('risk_check', risk_rejection)
        await asyncio.sleep(0.1)
        
        # 주문이 실행되지 않았는지 확인
        assert not system['order'].kis_client.place_order.called