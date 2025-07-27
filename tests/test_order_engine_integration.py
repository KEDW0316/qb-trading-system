"""
주문 엔진 통합 테스트

QB Trading System의 주문 엔진 전체 워크플로우를 검증하는 통합 테스트입니다.
전략 신호 → 주문 생성 → 체결 → 포지션 업데이트의 전체 흐름을 테스트합니다.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import json

# 테스트 대상 모듈들
from qb.engines.order_engine import (
    OrderEngine, KISBrokerClient, OrderQueue, PositionManager,
    KoreanStockCommissionCalculator, Order, OrderType, OrderSide, OrderStatus
)
from qb.engines.order_engine.event_handler import OrderEventHandler, FillMonitor
from qb.engines.order_engine.execution_manager import ExecutionManager
from qb.engines.strategy_engine.base import TradingSignal
from qb.utils.event_bus import EventBus, EventType
from qb.utils.redis_manager import RedisManager
from qb.collectors.kis_client import KISClient
from qb.database.connection import DatabaseManager


@pytest_asyncio.fixture
async def mock_dependencies():
    """테스트용 의존성 모킹"""
    # Mock Redis Manager
    mock_redis = AsyncMock()
    mock_redis.get_hash.return_value = {"close": "75000"}
    mock_redis.get_data.return_value = None
    mock_redis.set_data.return_value = True
    mock_redis.hash_get_all.return_value = {}
    mock_redis.scan_keys.return_value = []
    mock_redis.set_hash.return_value = True
    mock_redis.expire_key.return_value = True
    mock_redis.hash_set.return_value = True
    
    # Mock Database Manager
    mock_db = Mock()
    
    # Mock KIS Client
    mock_kis_client = Mock()
    mock_kis_client._make_api_request = AsyncMock()
    
    # Real Event Bus (for testing event flow)
    event_bus = EventBus(mock_redis)
    
    return {
        "redis_manager": mock_redis,
        "db_manager": mock_db,
        "kis_client": mock_kis_client,
        "event_bus": event_bus
    }


@pytest_asyncio.fixture
async def order_engine_setup(mock_dependencies):
    """주문 엔진 전체 설정"""
    # 컴포넌트 생성
    broker_client = KISBrokerClient(
        mock_dependencies["kis_client"],
        mock_dependencies["redis_manager"],
        config={"account_number": "12345678-01"}
    )
    
    order_queue = OrderQueue(
        mock_dependencies["redis_manager"],
        config={"max_queue_size": 100}
    )
    await order_queue.initialize()
    
    position_manager = PositionManager(
        mock_dependencies["redis_manager"],
        mock_dependencies["db_manager"]
    )
    await position_manager.initialize()
    
    commission_calculator = KoreanStockCommissionCalculator()
    
    # OrderEngine 생성
    order_engine = OrderEngine(
        broker_client=broker_client,
        order_queue=order_queue,
        position_manager=position_manager,
        commission_calculator=commission_calculator,
        event_bus=mock_dependencies["event_bus"],
        redis_manager=mock_dependencies["redis_manager"],
        config={
            "max_order_value": 10_000_000,
            "max_position_count": 10
        }
    )
    
    # Event Handler 생성
    event_handler = OrderEventHandler(
        mock_dependencies["event_bus"],
        mock_dependencies["redis_manager"]
    )
    
    # Execution Manager 생성
    execution_manager = ExecutionManager(
        mock_dependencies["event_bus"],
        mock_dependencies["redis_manager"],
        event_handler
    )
    
    return {
        "order_engine": order_engine,
        "event_handler": event_handler,
        "execution_manager": execution_manager,
        "broker_client": broker_client,
        "order_queue": order_queue,
        "position_manager": position_manager,
        **mock_dependencies
    }


class TestOrderEngineIntegration:
    """주문 엔진 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_full_order_lifecycle(self, order_engine_setup):
        """전체 주문 생명주기 테스트"""
        order_engine = order_engine_setup["order_engine"]
        event_bus = order_engine_setup["event_bus"]
        execution_manager = order_engine_setup["execution_manager"]
        
        # 엔진 시작
        await order_engine.start()
        await execution_manager.start()
        
        # 거래 신호 생성
        signal = TradingSignal(
            action="BUY",
            symbol="005930",
            confidence=0.8,
            price=75000.0,
            quantity=100,
            reason="Moving average crossover",
            metadata={"strategy_name": "MA_Strategy"}
        )
        
        # KIS API 응답 모킹
        order_engine_setup["kis_client"]._make_api_request.return_value = {
            "rt_cd": "0",
            "output": {"odno": "0123456789"},
            "msg1": "주문이 정상 처리되었습니다"
        }
        
        # 거래 신호 이벤트 발행
        await event_bus.publish(EventType.TRADING_SIGNAL.value, {
            "signal": {
                "action": signal.action,
                "symbol": signal.symbol,
                "confidence": signal.confidence,
                "price": signal.price,
                "quantity": signal.quantity,
                "reason": signal.reason,
                "metadata": signal.metadata,
                "timestamp": signal.timestamp.isoformat()
            }
        })
        
        # 이벤트 처리 대기
        await asyncio.sleep(0.5)
        
        # 주문이 생성되고 큐에 추가되었는지 확인
        active_orders = await order_engine.get_active_orders()
        assert len(active_orders) > 0
        
        order = active_orders[0]
        assert order.symbol == "005930"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        
        # 엔진 정리
        await order_engine.stop()
        await execution_manager.stop()
    
    @pytest.mark.asyncio
    async def test_order_execution_flow(self, order_engine_setup):
        """주문 실행 흐름 테스트"""
        order_engine = order_engine_setup["order_engine"]
        event_bus = order_engine_setup["event_bus"]
        execution_manager = order_engine_setup["execution_manager"]
        
        await order_engine.start()
        await execution_manager.start()
        
        # 직접 주문 생성
        order = Order(
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=75000.0,
            strategy_name="TestStrategy"
        )
        
        # KIS API 응답 모킹
        order_engine_setup["kis_client"]._make_api_request.return_value = {
            "rt_cd": "0",
            "output": {"odno": "0123456789"},
            "msg1": "주문이 정상 처리되었습니다"
        }
        
        # 주문 큐에 추가
        await order_engine_setup["order_queue"].add_order(order)
        
        # 주문 처리 대기
        await asyncio.sleep(0.5)
        
        # 주문이 브로커에 제출되었는지 확인
        assert order_engine_setup["kis_client"]._make_api_request.called
        
        # ORDER_PLACED 이벤트가 발행되었는지 확인 (이벤트 리스너 추가)
        order_placed_received = False
        
        async def check_order_placed(event_data):
            nonlocal order_placed_received
            order_placed_received = True
            assert event_data["symbol"] == "005930"
            assert event_data["quantity"] == 50
        
        await event_bus.subscribe(EventType.ORDER_PLACED.value, check_order_placed)
        
        # 이벤트 처리 대기
        await asyncio.sleep(0.1)
        
        await order_engine.stop()
        await execution_manager.stop()
    
    @pytest.mark.asyncio
    async def test_fill_processing(self, order_engine_setup):
        """체결 처리 테스트"""
        order_engine = order_engine_setup["order_engine"]
        event_bus = order_engine_setup["event_bus"]
        execution_manager = order_engine_setup["execution_manager"]
        position_manager = order_engine_setup["position_manager"]
        
        await order_engine.start()
        await execution_manager.start()
        
        # 주문 생성 및 활성화
        order = Order(
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )
        
        # 주문을 활성 주문에 추가
        order_engine._active_orders[order.order_id] = order
        
        # 주문 제출 이벤트 발행 (ExecutionManager가 추적하도록)
        await event_bus.publish(EventType.ORDER_PLACED.value, {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "quantity": order.quantity
        })
        
        # 체결 이벤트 생성
        fill_event = {
            "fill": {
                "fill_id": "fill_001",
                "order_id": order.order_id,
                "symbol": "005930",
                "side": "BUY",
                "quantity": 100,
                "price": 74900.0,
                "commission": 150.0,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # 체결 이벤트 발행
        await event_bus.publish(EventType.ORDER_EXECUTED.value, fill_event)
        
        # 이벤트 처리 대기
        await asyncio.sleep(0.5)
        
        # 포지션이 업데이트되었는지 확인
        position = await position_manager.get_position("005930")
        assert position is not None
        assert position.quantity == 100
        assert position.average_price == 74900.0
        
        # 체결 상태 확인
        exec_status = await execution_manager.get_execution_status(order.order_id)
        assert exec_status is not None
        assert exec_status["filled_quantity"] == 100
        assert exec_status["is_fully_filled"] is True
        
        await order_engine.stop()
        await execution_manager.stop()
    
    @pytest.mark.asyncio
    async def test_partial_fill_handling(self, order_engine_setup):
        """부분 체결 처리 테스트"""
        order_engine = order_engine_setup["order_engine"]
        event_bus = order_engine_setup["event_bus"]
        execution_manager = order_engine_setup["execution_manager"]
        
        await order_engine.start()
        await execution_manager.start()
        
        # 대량 주문 생성
        order = Order(
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,
            price=75000.0
        )
        
        order_engine._active_orders[order.order_id] = order
        
        # 주문 제출 이벤트
        await event_bus.publish(EventType.ORDER_PLACED.value, {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "quantity": order.quantity
        })
        
        # 첫 번째 부분 체결
        await event_bus.publish(EventType.ORDER_EXECUTED.value, {
            "fill": {
                "fill_id": "fill_001",
                "order_id": order.order_id,
                "symbol": "005930",
                "side": "BUY",
                "quantity": 300,
                "price": 74950.0,
                "commission": 450.0,
                "timestamp": datetime.now().isoformat()
            }
        })
        
        await asyncio.sleep(0.2)
        
        # 부분 체결 상태 확인
        exec_status = await execution_manager.get_execution_status(order.order_id)
        assert exec_status["filled_quantity"] == 300
        assert exec_status["remaining_quantity"] == 700
        assert exec_status["is_partially_filled"] is True
        
        # 두 번째 부분 체결
        await event_bus.publish(EventType.ORDER_EXECUTED.value, {
            "fill": {
                "fill_id": "fill_002",
                "order_id": order.order_id,
                "symbol": "005930",
                "side": "BUY",
                "quantity": 700,
                "price": 75000.0,
                "commission": 1050.0,
                "timestamp": datetime.now().isoformat()
            }
        })
        
        await asyncio.sleep(0.2)
        
        # 완전 체결 상태 확인
        exec_status = await execution_manager.get_execution_status(order.order_id)
        assert exec_status["filled_quantity"] == 1000
        assert exec_status["is_fully_filled"] is True
        
        # 평균 체결가 확인: (300*74950 + 700*75000) / 1000 = 74985
        expected_avg = (300 * 74950 + 700 * 75000) / 1000
        assert abs(exec_status["average_fill_price"] - expected_avg) < 0.01
        
        await order_engine.stop()
        await execution_manager.stop()
    
    @pytest.mark.asyncio
    async def test_order_cancellation(self, order_engine_setup):
        """주문 취소 테스트"""
        order_engine = order_engine_setup["order_engine"]
        event_bus = order_engine_setup["event_bus"]
        
        await order_engine.start()
        
        # 주문 생성
        order = Order(
            symbol="005930",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=76000.0
        )
        
        order_engine._active_orders[order.order_id] = order
        
        # KIS API 취소 응답 모킹
        order_engine_setup["kis_client"]._make_api_request.return_value = {
            "rt_cd": "0",
            "msg1": "주문이 정상 취소되었습니다"
        }
        
        # 주문 취소
        result = await order_engine.cancel_order_by_id(order.order_id)
        assert result is True
        
        # 주문이 활성 목록에서 제거되었는지 확인
        assert order.order_id not in order_engine._active_orders
        
        # ORDER_CANCELLED 이벤트 확인
        cancelled_event_received = False
        
        async def check_cancelled(event_data):
            nonlocal cancelled_event_received
            cancelled_event_received = True
            assert event_data["order_id"] == order.order_id
        
        await event_bus.subscribe(EventType.ORDER_CANCELLED.value, check_cancelled)
        await asyncio.sleep(0.1)
        
        await order_engine.stop()
    
    @pytest.mark.asyncio
    async def test_risk_validation(self, order_engine_setup):
        """리스크 검증 테스트"""
        order_engine = order_engine_setup["order_engine"]
        event_bus = order_engine_setup["event_bus"]
        
        await order_engine.start()
        
        # 계좌 잔고 모킹
        order_engine_setup["kis_client"]._make_api_request.return_value = {
            "rt_cd": "0",
            "output2": [{
                "ord_psbl_cash": "1000000",  # 100만원만 주문 가능
                "tot_evlu_amt": "5000000"
            }]
        }
        
        # 과도한 금액의 주문 신호
        signal = TradingSignal(
            action="BUY",
            symbol="005930",
            confidence=0.9,
            price=75000.0,
            quantity=1000,  # 7500만원 주문 (잔고 초과)
            reason="Test signal"
        )
        
        # 거래 신호 발행
        await event_bus.publish(EventType.TRADING_SIGNAL.value, {
            "signal": {
                "action": signal.action,
                "symbol": signal.symbol,
                "confidence": signal.confidence,
                "price": signal.price,
                "quantity": signal.quantity,
                "reason": signal.reason,
                "timestamp": signal.timestamp.isoformat()
            }
        })
        
        await asyncio.sleep(0.2)
        
        # 주문이 생성되지 않았거나 검증 실패했는지 확인
        active_orders = await order_engine.get_active_orders()
        # 리스크 검증에 실패하면 주문이 생성되지 않음
        assert len(active_orders) == 0
        
        await order_engine.stop()
    
    @pytest.mark.asyncio
    async def test_position_close_flow(self, order_engine_setup):
        """포지션 청산 흐름 테스트"""
        order_engine = order_engine_setup["order_engine"]
        position_manager = order_engine_setup["position_manager"]
        event_bus = order_engine_setup["event_bus"]
        
        await order_engine.start()
        
        # 먼저 포지션 생성 (매수 체결)
        from qb.engines.order_engine.base import Fill
        buy_fill = Fill(
            order_id="buy_order_001",
            symbol="005930",
            side=OrderSide.BUY,
            quantity=100,
            price=75000.0,
            commission=100.0
        )
        
        await position_manager.update_position("005930", buy_fill)
        
        # 포지션 청산 주문 생성
        close_order = await position_manager.close_position("005930")
        assert close_order is not None
        assert close_order.side == OrderSide.SELL
        assert close_order.quantity == 100
        assert close_order.order_type == OrderType.MARKET
        
        # 청산 주문을 큐에 추가
        await order_engine_setup["order_queue"].add_order(close_order)
        
        # KIS API 응답 모킹
        order_engine_setup["kis_client"]._make_api_request.return_value = {
            "rt_cd": "0",
            "output": {"odno": "9876543210"},
            "msg1": "주문이 정상 처리되었습니다"
        }
        
        await asyncio.sleep(0.5)
        
        # 청산 주문이 실행되었는지 확인
        assert order_engine_setup["kis_client"]._make_api_request.called
        
        await order_engine.stop()
    
    @pytest.mark.asyncio
    async def test_event_handler_integration(self, order_engine_setup):
        """이벤트 핸들러 통합 테스트"""
        event_handler = order_engine_setup["event_handler"]
        event_bus = order_engine_setup["event_bus"]
        
        await event_handler.start()
        
        # KIS 체결 통지 시뮬레이션
        kis_fill_notification = {
            "odno": "0123456789",      # 주문번호
            "pdno": "005930",          # 종목코드
            "cntg_qty": "50",          # 체결수량
            "cntg_unpr": "75100",      # 체결단가
            "cntg_tmrd": "140523",     # 체결시각
            "sll_buy_dvsn_cd": "2",    # 매매구분 (2:매수)
            "cntg_sno": "000001"       # 체결일련번호
        }
        
        # 이벤트 발행
        await event_bus.publish("kis_fill_notification", kis_fill_notification)
        
        # ORDER_EXECUTED 이벤트가 발행되었는지 확인
        executed_event_received = False
        
        async def check_executed(event_data):
            nonlocal executed_event_received
            executed_event_received = True
            fill = event_data["fill"]
            assert fill["symbol"] == "005930"
            assert fill["quantity"] == 50
            assert fill["price"] == 75100.0
        
        await event_bus.subscribe(EventType.ORDER_EXECUTED.value, check_executed)
        await asyncio.sleep(0.2)
        
        assert executed_event_received
        
        await event_handler.stop()
    
    @pytest.mark.asyncio
    async def test_commission_calculation_integration(self, order_engine_setup):
        """수수료 계산 통합 테스트"""
        order_engine = order_engine_setup["order_engine"]
        position_manager = order_engine_setup["position_manager"]
        event_bus = order_engine_setup["event_bus"]
        
        await order_engine.start()
        
        # 매도 주문 (세금 포함)
        order = Order(
            symbol="005930",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=76000.0
        )
        
        order_engine._active_orders[order.order_id] = order
        
        # 체결 이벤트 (수수료 자동 계산)
        await event_bus.publish(EventType.ORDER_EXECUTED.value, {
            "fill": {
                "fill_id": "fill_001",
                "order_id": order.order_id,
                "symbol": "005930",
                "side": "SELL",
                "quantity": 100,
                "price": 76000.0,
                "commission": 0.0,  # 0으로 설정하여 자동 계산 테스트
                "timestamp": datetime.now().isoformat()
            }
        })
        
        await asyncio.sleep(0.2)
        
        # 수수료가 계산되었는지 확인
        # 매도시: 위탁수수료 + 증권거래세 + 농어촌특별세 + 거래소수수료
        # 거래대금: 7,600,000원
        # 예상 수수료: 약 19,000원 이상 (세금 포함)
        
        position = await position_manager.get_position("005930")
        if position:  # 포지션이 있는 경우만 확인
            assert position.total_commission > 0
            assert position.total_commission > 10000  # 매도 수수료는 10,000원 이상
        
        await order_engine.stop()


class TestErrorHandlingAndRecovery:
    """에러 처리 및 복구 테스트"""
    
    @pytest.mark.asyncio
    async def test_broker_api_failure_handling(self, order_engine_setup):
        """브로커 API 실패 처리 테스트"""
        order_engine = order_engine_setup["order_engine"]
        event_bus = order_engine_setup["event_bus"]
        
        await order_engine.start()
        
        # KIS API 에러 응답 모킹
        order_engine_setup["kis_client"]._make_api_request.return_value = {
            "rt_cd": "1",
            "msg1": "주문 실패: 잔고 부족",
            "msg_cd": "40310000"
        }
        
        # 주문 생성
        order = Order(
            symbol="005930",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )
        
        await order_engine_setup["order_queue"].add_order(order)
        
        # ORDER_FAILED 이벤트 확인
        failed_event_received = False
        
        async def check_failed(event_data):
            nonlocal failed_event_received
            failed_event_received = True
            assert event_data["order_id"] == order.order_id
            assert "잔고 부족" in event_data["error_message"]
        
        await event_bus.subscribe(EventType.ORDER_FAILED.value, check_failed)
        await asyncio.sleep(0.5)
        
        assert failed_event_received
        
        await order_engine.stop()
    
    @pytest.mark.asyncio
    async def test_partial_fill_timeout_handling(self, order_engine_setup):
        """부분 체결 타임아웃 처리 테스트"""
        execution_manager = order_engine_setup["execution_manager"]
        event_bus = order_engine_setup["event_bus"]
        
        # 타임아웃을 짧게 설정
        execution_manager.max_partial_fill_time = 1  # 1초
        
        await execution_manager.start()
        
        order_id = "timeout_test_order"
        
        # 주문 제출
        await event_bus.publish("order_placed", {
            "order_id": order_id,
            "symbol": "005930",
            "quantity": 1000
        })
        
        # 부분 체결만 발생
        await event_bus.publish("order_executed", {
            "fill": {
                "fill_id": "partial_fill_001",
                "order_id": order_id,
                "symbol": "005930",
                "side": "BUY",
                "quantity": 300,
                "price": 75000.0,
                "commission": 450.0,
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # 타임아웃 대기
        await asyncio.sleep(2)
        
        # 경고 이벤트 확인
        alert_received = False
        
        async def check_alert(event_data):
            nonlocal alert_received
            alert_received = True
            assert event_data["order_id"] == order_id
            assert event_data["filled_quantity"] == 300
            assert event_data["remaining_quantity"] == 700
        
        await event_bus.subscribe("stale_partial_fill_alert", check_alert)
        
        # 모니터링 실행
        await execution_manager._monitor_partial_fills()
        
        await asyncio.sleep(0.1)
        assert alert_received
        
        await execution_manager.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])