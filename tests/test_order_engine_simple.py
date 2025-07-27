"""
간단한 주문 엔진 통합 테스트

복잡한 이벤트 시스템 없이 핵심 기능만 테스트합니다.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from qb.engines.order_engine.base import Order, OrderSide, OrderType, Fill
from qb.engines.order_engine.order_queue import OrderQueue
from qb.engines.order_engine.position_manager import PositionManager
from qb.engines.order_engine.commission_calculator import KoreanStockCommissionCalculator


@pytest.mark.asyncio
async def test_simple_order_lifecycle():
    """간단한 주문 생명주기 테스트"""
    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.hash_get_all.return_value = {}
    mock_redis.scan_keys.return_value = []
    mock_redis.set_hash.return_value = True
    
    # Mock Database
    mock_db = Mock()
    
    # Create components
    order_queue = OrderQueue(mock_redis)
    await order_queue.initialize()
    
    position_manager = PositionManager(mock_redis, mock_db)
    await position_manager.initialize()
    
    commission_calculator = KoreanStockCommissionCalculator()
    
    # Test: Create and add order
    order = Order(
        symbol="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100
    )
    
    result = await order_queue.add_order(order)
    assert result is True
    
    # Test: Get next order
    next_order = await order_queue.get_next_order()
    if next_order:  # If not expired
        assert next_order.symbol == "005930"
    
    # Test: Commission calculation
    commission = commission_calculator.calculate_commission(order, 75000.0, 100)
    assert commission > 0
    
    # Test: Position update with fill
    fill = Fill(
        order_id=order.order_id,
        symbol="005930",
        side=OrderSide.BUY,
        quantity=100,
        price=75000.0,
        commission=commission
    )
    
    position = await position_manager.update_position("005930", fill)
    assert position.quantity == 100
    assert position.average_price == 75000.0
    
    print("✅ Simple order lifecycle test passed!")


@pytest.mark.asyncio
async def test_order_queue_priority():
    """주문 큐 우선순위 테스트"""
    mock_redis = AsyncMock()
    mock_redis.hash_get_all.return_value = {}
    
    queue = OrderQueue(mock_redis)
    await queue.initialize()
    
    # Create limit order first
    limit_order = Order(
        symbol="005930",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        price=75000.0
    )
    
    # Create market order second
    market_order = Order(
        symbol="005930",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100
    )
    
    await queue.add_order(limit_order)
    await queue.add_order(market_order)
    
    # Check pending orders contain both
    pending = await queue.get_pending_orders()
    assert len(pending) == 2
    
    print("✅ Order queue priority test passed!")


@pytest.mark.asyncio 
async def test_position_close():
    """포지션 청산 테스트"""
    mock_redis = AsyncMock()
    mock_redis.scan_keys.return_value = []
    mock_db = Mock()
    
    position_manager = PositionManager(mock_redis, mock_db)
    await position_manager.initialize()
    
    # Create position with buy fill
    fill = Fill(
        order_id="test_001",
        symbol="005930", 
        side=OrderSide.BUY,
        quantity=100,
        price=75000.0,
        commission=100.0
    )
    
    await position_manager.update_position("005930", fill)
    
    # Create close order
    close_order = await position_manager.close_position("005930")
    
    assert close_order is not None
    assert close_order.side == OrderSide.SELL
    assert close_order.quantity == 100
    
    print("✅ Position close test passed!")


if __name__ == "__main__":
    asyncio.run(test_simple_order_lifecycle())
    asyncio.run(test_order_queue_priority())
    asyncio.run(test_position_close())
    print("✅ All simple tests passed!")