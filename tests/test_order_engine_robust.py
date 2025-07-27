"""
견고한 주문 엔진 테스트

근본 원인을 해결하고 핵심 기능을 실용적 수준에서 검증합니다.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from qb.engines.order_engine.base import (
    Order, OrderSide, OrderType, Fill, Position, TimeInForce
)
from qb.engines.order_engine.order_queue import OrderQueue
from qb.engines.order_engine.position_manager import PositionManager
from qb.engines.order_engine.commission_calculator import KoreanStockCommissionCalculator
from qb.engines.order_engine.execution_manager import ExecutionTracker


class TestOrderQueuePriorityRobust:
    """우선순위 로직 견고한 테스트"""
    
    @pytest_asyncio.fixture
    async def setup_queue(self):
        """시간 제어가 가능한 테스트 환경"""
        mock_redis = AsyncMock()
        mock_redis.hash_get_all.return_value = {}
        
        queue = OrderQueue(mock_redis, config={
            "priority_timeout": 3600,  # 1시간으로 충분히 길게 설정
            "max_queue_size": 100
        })
        await queue.initialize()
        return queue
    
    @pytest.mark.asyncio
    async def test_market_vs_limit_priority(self, setup_queue):
        """시장가 vs 지정가 우선순위 테스트"""
        queue = setup_queue
        
        # 장중 시간으로 Mock 설정
        with patch('qb.engines.order_engine.order_queue.datetime') as mock_datetime:
            market_time = datetime(2024, 1, 15, 10, 0, 0)  # 오전 10시
            mock_datetime.now.return_value = market_time
            
            # 지정가 주문 먼저 생성 (낮은 우선순위)
            limit_order = Order(
                symbol="005930",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=75000.0,
                time_in_force=TimeInForce.DAY
            )
            limit_order.created_at = market_time
            
            # 시장가 주문 나중에 생성 (높은 우선순위)
            market_order = Order(
                symbol="005930",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=100,
                time_in_force=TimeInForce.DAY
            )
            market_order.created_at = market_time
            
            # 순서대로 추가
            await queue.add_order(limit_order)
            await queue.add_order(market_order)
            
            # 시장가 주문이 먼저 나와야 함
            first_order = await queue.get_next_order()
            assert first_order is not None, "주문이 만료되어서는 안됨"
            assert first_order.order_type == OrderType.MARKET, "시장가 주문이 우선순위가 높아야 함"
            assert first_order.order_id == market_order.order_id
    
    @pytest.mark.asyncio
    async def test_sell_vs_buy_priority(self, setup_queue):
        """매도 vs 매수 우선순위 테스트"""
        queue = setup_queue
        
        with patch('qb.engines.order_engine.order_queue.datetime') as mock_datetime:
            market_time = datetime(2024, 1, 15, 11, 0, 0)
            mock_datetime.now.return_value = market_time
            
            # 매수 주문 먼저 생성
            buy_order = Order(
                symbol="005930",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=75000.0
            )
            buy_order.created_at = market_time
            
            # 매도 주문 나중에 생성
            sell_order = Order(
                symbol="005930",
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=76000.0
            )
            sell_order.created_at = market_time
            
            await queue.add_order(buy_order)
            await queue.add_order(sell_order)
            
            # 매도 주문이 먼저 나와야 함
            first_order = await queue.get_next_order()
            assert first_order is not None
            assert first_order.side == OrderSide.SELL, "매도 주문이 우선순위가 높아야 함"


class TestCommissionCalculationAccuracy:
    """수수료 계산 정확성 테스트"""
    
    def test_korean_stock_buy_commission(self):
        """매수 수수료 정확성"""
        calculator = KoreanStockCommissionCalculator()
        
        # 실제 한국 주식 매수 수수료 계산
        order = Order(
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=75000.0
        )
        
        commission = calculator.calculate_commission(order, 75000.0, 100)
        
        # 거래대금: 7,500,000원
        # 위탁수수료: 1,125원 + 거래소수수료: 60원 + 청산수수료: 115.5원 = 1,300.5원
        expected_min = 1250  # 기본 수수료들
        expected_max = 1350  # 여유분
        
        assert expected_min <= commission <= expected_max, f"매수 수수료가 예상 범위를 벗어남: {commission}"
    
    def test_korean_stock_sell_commission(self):
        """매도 수수료 정확성 (세금 포함)"""
        calculator = KoreanStockCommissionCalculator()
        
        order = Order(
            symbol="005930",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=75000.0
        )
        
        commission = calculator.calculate_commission(order, 75000.0, 100)
        
        # 거래대금: 7,500,000원  
        # 위탁수수료: 1,125원 + 거래소수수료: 60원 + 청산수수료: 115.5원 = 1,300.5원
        # 증권거래세: 7,500,000 * 0.23% = 17,250원 
        # 농어촌특별세: 17,250 * 20% = 3,450원
        # 총합: 1,300.5 + 17,250 + 3,450 = 22,000.5원
        expected_min = 21900
        expected_max = 22100
        
        assert expected_min <= commission <= expected_max, f"매도 수수료가 예상 범위를 벗어남: {commission}"
        
        # 매도가 매수보다 훨씬 비싸야 함
        buy_commission = calculator.calculate_commission(
            Order(symbol="005930", side=OrderSide.BUY, order_type=OrderType.LIMIT, quantity=100, price=75000.0),
            75000.0, 100
        )
        assert commission > buy_commission * 15, "매도 수수료가 매수보다 충분히 높지 않음"


class TestPositionManagementLogic:
    """포지션 관리 로직 테스트"""
    
    @pytest_asyncio.fixture
    async def position_manager(self):
        """포지션 관리자 설정"""
        mock_redis = AsyncMock()
        mock_redis.scan_keys.return_value = []
        mock_redis.get_hash.return_value = {}
        mock_db = Mock()
        
        manager = PositionManager(mock_redis, mock_db)
        await manager.initialize()
        return manager
    
    @pytest.mark.asyncio
    async def test_average_price_calculation(self, position_manager):
        """평균 매입가 계산 정확성"""
        # 첫 번째 매수
        fill1 = Fill(
            order_id="order1",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=100,
            price=75000.0,
            commission=100.0
        )
        
        position = await position_manager.update_position("005930", fill1)
        assert position.quantity == 100
        assert position.average_price == 75000.0
        
        # 두 번째 매수 (다른 가격)
        fill2 = Fill(
            order_id="order2",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=200,
            price=76000.0,
            commission=200.0
        )
        
        position = await position_manager.update_position("005930", fill2)
        
        # 평균가 계산: (100*75000 + 200*76000) / 300 = 75666.67
        expected_avg = (100 * 75000 + 200 * 76000) / 300
        assert position.quantity == 300
        assert abs(position.average_price - expected_avg) < 0.01, f"평균가 계산 오류: {position.average_price} vs {expected_avg}"
    
    @pytest.mark.asyncio
    async def test_position_close_order_generation(self, position_manager):
        """포지션 청산 주문 생성"""
        # 포지션 생성
        fill = Fill(
            order_id="order1",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=150,
            price=75000.0,
            commission=150.0
        )
        
        await position_manager.update_position("005930", fill)
        
        # 청산 주문 생성
        close_order = await position_manager.close_position("005930")
        
        assert close_order is not None, "청산 주문이 생성되어야 함"
        assert close_order.side == OrderSide.SELL, "롱 포지션은 매도로 청산"
        assert close_order.quantity == 150, "전체 수량 청산"
        assert close_order.order_type == OrderType.MARKET, "시장가로 즉시 청산"


class TestExecutionTrackerLogic:
    """체결 추적 로직 테스트"""
    
    def test_partial_fill_tracking(self):
        """부분 체결 추적"""
        tracker = ExecutionTracker(
            order_id="test_order",
            symbol="005930",
            total_quantity=1000
        )
        
        # 첫 번째 부분 체결
        fill1 = Fill(
            order_id="test_order",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=300,
            price=75000.0,
            commission=450.0
        )
        
        tracker.add_fill(fill1)
        
        assert tracker.filled_quantity == 300
        assert tracker.remaining_quantity == 700
        assert tracker.fill_ratio == 0.3
        assert tracker.is_partially_filled
        assert not tracker.is_fully_filled
        
        # 두 번째 부분 체결 (다른 가격)
        fill2 = Fill(
            order_id="test_order",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=700,
            price=75200.0,
            commission=1050.0
        )
        
        tracker.add_fill(fill2)
        
        # 완전 체결 확인
        assert tracker.filled_quantity == 1000
        assert tracker.remaining_quantity == 0
        assert tracker.fill_ratio == 1.0
        assert not tracker.is_partially_filled
        assert tracker.is_fully_filled
        
        # 평균 체결가 확인: (300*75000 + 700*75200) / 1000 = 75140
        expected_avg = (300 * 75000 + 700 * 75200) / 1000
        assert abs(tracker.average_fill_price - expected_avg) < 0.01
        
        # 총 수수료 확인
        assert tracker.total_commission == 1500.0
    
    def test_overfill_prevention(self):
        """과도한 체결 방지"""
        tracker = ExecutionTracker(
            order_id="test_order",
            symbol="005930",
            total_quantity=100
        )
        
        # 정상 체결
        fill1 = Fill(
            order_id="test_order",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=80,
            price=75000.0,
            commission=120.0
        )
        
        tracker.add_fill(fill1)
        assert tracker.filled_quantity == 80
        
        # 과도한 체결 시도 (남은 20개보다 많은 30개)
        fill2 = Fill(
            order_id="test_order",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=30,
            price=75000.0,
            commission=45.0
        )
        
        with pytest.raises(ValueError, match="Fill quantity exceeds remaining"):
            tracker.add_fill(fill2)


@pytest.mark.asyncio
async def test_integration_order_to_position():
    """통합 테스트: 주문 → 체결 → 포지션 업데이트"""
    # 컴포넌트 설정
    mock_redis = AsyncMock()
    mock_redis.hash_get_all.return_value = {}
    mock_redis.scan_keys.return_value = []
    mock_db = Mock()
    
    queue = OrderQueue(mock_redis, config={"priority_timeout": 3600})
    await queue.initialize()
    
    position_manager = PositionManager(mock_redis, mock_db)
    await position_manager.initialize()
    
    calculator = KoreanStockCommissionCalculator()
    
    # 시나리오: 주문 생성 → 큐 처리 → 체결 → 포지션 업데이트
    with patch('qb.engines.order_engine.order_queue.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
        
        # 1. 주문 생성 및 큐 추가
        order = Order(
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=75000.0
        )
        order.created_at = datetime(2024, 1, 15, 10, 0, 0)
        
        result = await queue.add_order(order)
        assert result is True
        
        # 2. 큐에서 주문 처리
        next_order = await queue.get_next_order()
        assert next_order is not None
        assert next_order.order_id == order.order_id
        
        # 3. 수수료 계산
        commission = calculator.calculate_commission(order, 74900.0, 100)
        assert commission > 0
        
        # 4. 체결 생성 및 포지션 업데이트
        fill = Fill(
            order_id=order.order_id,
            symbol="005930",
            side=OrderSide.BUY,
            quantity=100,
            price=74900.0,
            commission=commission
        )
        
        position = await position_manager.update_position("005930", fill)
        
        # 5. 최종 검증
        assert position.symbol == "005930"
        assert position.quantity == 100
        assert position.average_price == 74900.0
        assert position.total_commission == commission
        assert position.is_long
        
        print("✅ 통합 시나리오 테스트 성공!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])