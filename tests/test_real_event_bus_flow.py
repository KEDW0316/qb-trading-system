"""
실제 거래 시스템 Event Bus 플로우 테스트

이 테스트는 실제 거래 시나리오에서 Event Bus가 
어떻게 작동하는지 검증합니다.
"""

import pytest
import time
import logging
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, MagicMock

# QB 시스템 imports
from qb.engines.event_bus import EventType, Event, EnhancedEventBus
from qb.engines.event_bus.adapters import (
    MarketDataPublisher, TradingSignalPublisher,
    OrderEventPublisher, RiskEventPublisher
)
from qb.utils.redis_manager import RedisManager
from qb.engines.strategy_engine.engine import StrategyEngine
from qb.engines.risk_engine.engine import RiskEngine
from qb.engines.order_engine.engine import OrderEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestRealEventBusFlow:
    """실제 거래 플로우 테스트"""
    
    @pytest.fixture
    def redis_manager(self):
        """실제 Redis Manager (또는 Mock)"""
        mock = Mock()
        mock.redis = MagicMock()
        mock.redis.ping.return_value = True
        mock.redis.pubsub.return_value = MagicMock()
        return mock
    
    @pytest.fixture
    def event_bus(self, redis_manager):
        """실제 Event Bus 인스턴스"""
        bus = EnhancedEventBus(redis_manager)
        bus.start()
        yield bus
        bus.stop()
    
    def test_real_trading_scenario(self, event_bus, redis_manager):
        """
        실제 거래 시나리오 테스트
        
        1. 시장 데이터 수신 → 2. 전략 신호 생성 → 3. 리스크 체크 → 4. 주문 실행
        """
        # 테스트용 이벤트 수집
        collected_events = {
            'market_data': [],
            'trading_signals': [],
            'risk_checks': [],
            'orders': []
        }
        
        # 1. 이벤트 핸들러 등록
        def on_market_data(event: Event):
            collected_events['market_data'].append(event)
            logger.info(f"Market data received: {event.data['symbol']} @ {event.data['price']}")
        
        def on_trading_signal(event: Event):
            collected_events['trading_signals'].append(event)
            logger.info(f"Trading signal: {event.data['action']} {event.data['symbol']}")
        
        def on_risk_check(event: Event):
            collected_events['risk_checks'].append(event)
            logger.info(f"Risk check: {event.event_type.value}")
        
        def on_order(event: Event):
            collected_events['orders'].append(event)
            logger.info(f"Order event: {event.event_type.value}")
        
        # 이벤트 구독
        event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, on_market_data)
        event_bus.subscribe(EventType.TRADING_SIGNAL, on_trading_signal)
        event_bus.subscribe(EventType.RISK_ALERT, on_risk_check)
        event_bus.subscribe(EventType.ORDER_PLACED, on_order)
        event_bus.subscribe(EventType.ORDER_EXECUTED, on_order)
        
        # 2. 컴포넌트별 Publisher 생성
        data_publisher = MarketDataPublisher(event_bus, "DataCollector")
        strategy_publisher = TradingSignalPublisher(event_bus, "StrategyEngine")
        risk_publisher = RiskEventPublisher(event_bus, "RiskEngine")
        order_publisher = OrderEventPublisher(event_bus, "OrderEngine")
        
        # 3. 실제 거래 플로우 시뮬레이션
        
        # Step 1: 시장 데이터 수신
        data_publisher.publish_market_data(
            symbol="005930",  # 삼성전자
            price_data={
                "open": 75000,
                "high": 75500,
                "low": 74800,
                "close": 75200,
                "volume": 12345678,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        # 이벤트 처리 대기
        time.sleep(0.1)
        
        # Step 2: 전략이 시장 데이터를 받고 거래 신호 생성
        if collected_events['market_data']:
            market_data = collected_events['market_data'][0].data
            
            # 간단한 전략 로직 (예: 가격이 75000 이상이면 매수)
            if market_data['close'] >= 75000:
                strategy_publisher.publish_trading_signal(
                    symbol="005930",
                    action="BUY",
                    price=market_data['close'],
                    quantity=10,
                    strategy_name="SimpleMovingAverage",
                    confidence=0.85,
                    metadata={
                        "reason": "Price breakout above 75000",
                        "indicators": {"sma_20": 74500, "rsi": 65}
                    }
                )
        
        time.sleep(0.1)
        
        # Step 3: 리스크 엔진이 거래 신호를 받고 체크
        if collected_events['trading_signals']:
            signal = collected_events['trading_signals'][0].data
            
            # 리스크 체크 (예: 포지션 크기 체크)
            position_value = signal['price'] * signal['quantity']
            portfolio_value = 10_000_000  # 1천만원
            
            if position_value > portfolio_value * 0.2:  # 20% 이상
                risk_publisher.publish_risk_alert(
                    alert_type="POSITION_SIZE_LIMIT",
                    severity="WARNING",
                    message=f"Position size {position_value:,.0f} exceeds 20% of portfolio",
                    details={
                        "symbol": signal['symbol'],
                        "position_value": position_value,
                        "portfolio_value": portfolio_value,
                        "ratio": position_value / portfolio_value
                    }
                )
            else:
                # 리스크 체크 통과 - 주문 실행
                order_publisher.publish_order_placed({
                    "order_id": "ORD20250127001",
                    "symbol": signal['symbol'],
                    "action": signal['action'],
                    "quantity": signal['quantity'],
                    "price": signal['price'],
                    "order_type": "LIMIT",
                    "timestamp": datetime.now().isoformat()
                })
        
        time.sleep(0.1)
        
        # Step 4: 주문 체결 시뮬레이션
        if collected_events['orders']:
            order = collected_events['orders'][0].data
            
            # 주문 체결 이벤트
            order_publisher.publish_order_executed({
                "order_id": order['order_id'],
                "symbol": order['symbol'],
                "action": order['action'],
                "quantity": order['quantity'],
                "executed_price": order['price'],
                "commission": 250,  # 수수료
                "timestamp": datetime.now().isoformat()
            })
        
        time.sleep(0.1)
        
        # 검증
        assert len(collected_events['market_data']) >= 1
        assert len(collected_events['trading_signals']) >= 1
        assert len(collected_events['orders']) >= 2  # placed + executed
        
        # 이벤트 체인 검증
        market_event = collected_events['market_data'][0]
        signal_event = collected_events['trading_signals'][0]
        
        assert market_event.data['symbol'] == signal_event.data['symbol']
        assert signal_event.data['price'] == market_event.data['close']
        
        logger.info(f"Total events processed: {sum(len(v) for v in collected_events.values())}")
    
    def test_risk_management_flow(self, event_bus):
        """리스크 관리 플로우 테스트"""
        
        risk_events = []
        emergency_stops = []
        
        def on_risk_alert(event: Event):
            risk_events.append(event)
            severity = event.data.get('severity', 'UNKNOWN')
            logger.warning(f"RISK ALERT [{severity}]: {event.data['message']}")
        
        def on_emergency_stop(event: Event):
            emergency_stops.append(event)
            logger.critical(f"EMERGENCY STOP: {event.data['reason']}")
        
        event_bus.subscribe(EventType.RISK_ALERT, on_risk_alert)
        event_bus.subscribe(EventType.EMERGENCY_STOP, on_emergency_stop)
        
        risk_publisher = RiskEventPublisher(event_bus, "RiskEngine")
        
        # 시나리오 1: 일일 손실 한도 접근
        risk_publisher.publish_risk_alert(
            alert_type="DAILY_LOSS_LIMIT",
            severity="WARNING",
            message="Daily loss approaching limit",
            details={
                "current_loss": -450_000,
                "limit": -500_000,
                "ratio": 0.9
            }
        )
        
        time.sleep(0.1)
        
        # 시나리오 2: 일일 손실 한도 초과 - 비상 정지
        risk_publisher.publish_risk_alert(
            alert_type="DAILY_LOSS_LIMIT",
            severity="CRITICAL",
            message="Daily loss limit exceeded",
            details={
                "current_loss": -520_000,
                "limit": -500_000,
                "ratio": 1.04
            }
        )
        
        # 비상 정지 발동
        risk_publisher.publish_emergency_stop(
            reason="Daily loss limit exceeded: -520,000 KRW",
            details={
                "triggered_by": "DAILY_LOSS_LIMIT",
                "current_loss": -520_000,
                "limit": -500_000,
                "action": "STOP_ALL_TRADING"
            }
        )
        
        time.sleep(0.1)
        
        # 검증
        assert len(risk_events) >= 2
        assert len(emergency_stops) >= 1
        
        # 심각도 확인
        warning_events = [e for e in risk_events if e.data['severity'] == 'WARNING']
        critical_events = [e for e in risk_events if e.data['severity'] == 'CRITICAL']
        
        assert len(warning_events) >= 1
        assert len(critical_events) >= 1
        
        # 비상 정지 이유 확인
        assert "Daily loss limit exceeded" in emergency_stops[0].data['reason']
    
    def test_position_update_flow(self, event_bus):
        """포지션 업데이트 플로우 테스트"""
        
        position_updates = []
        
        def on_position_update(event: Event):
            position_updates.append(event)
            pos = event.data
            logger.info(
                f"Position updated: {pos['symbol']} "
                f"qty={pos['quantity']} @ {pos['average_price']} "
                f"P&L={pos.get('unrealized_pnl', 0):,.0f}"
            )
        
        event_bus.subscribe(EventType.POSITION_UPDATED, on_position_update)
        
        risk_publisher = RiskEventPublisher(event_bus, "RiskEngine")
        order_publisher = OrderEventPublisher(event_bus, "OrderEngine")
        
        # Step 1: 초기 포지션 생성 (매수 체결)
        order_publisher.publish_order_executed({
            "order_id": "ORD001",
            "symbol": "005930",
            "action": "BUY",
            "quantity": 10,
            "executed_price": 75000,
            "commission": 250,
            "timestamp": datetime.now().isoformat()
        })
        
        # 포지션 업데이트
        risk_publisher.publish_position_updated({
            "symbol": "005930",
            "quantity": 10,
            "average_price": 75000,
            "current_price": 75000,
            "market_value": 750000,
            "unrealized_pnl": 0,
            "realized_pnl": 0,
            "timestamp": datetime.now().isoformat()
        })
        
        time.sleep(0.1)
        
        # Step 2: 가격 변동으로 포지션 업데이트
        new_price = 76000  # 1000원 상승
        risk_publisher.publish_position_updated({
            "symbol": "005930",
            "quantity": 10,
            "average_price": 75000,
            "current_price": new_price,
            "market_value": new_price * 10,
            "unrealized_pnl": (new_price - 75000) * 10,
            "realized_pnl": 0,
            "timestamp": datetime.now().isoformat()
        })
        
        time.sleep(0.1)
        
        # Step 3: 부분 매도
        order_publisher.publish_order_executed({
            "order_id": "ORD002",
            "symbol": "005930",
            "action": "SELL",
            "quantity": 5,
            "executed_price": 76000,
            "commission": 125,
            "timestamp": datetime.now().isoformat()
        })
        
        # 포지션 업데이트 (남은 수량)
        risk_publisher.publish_position_updated({
            "symbol": "005930",
            "quantity": 5,  # 10 - 5
            "average_price": 75000,
            "current_price": 76000,
            "market_value": 76000 * 5,
            "unrealized_pnl": (76000 - 75000) * 5,
            "realized_pnl": (76000 - 75000) * 5 - 125,  # 매도 수익
            "timestamp": datetime.now().isoformat()
        })
        
        time.sleep(0.1)
        
        # 검증
        assert len(position_updates) >= 3
        
        # 포지션 변화 추적
        initial_pos = position_updates[0].data
        price_change_pos = position_updates[1].data
        after_sell_pos = position_updates[2].data
        
        assert initial_pos['quantity'] == 10
        assert initial_pos['unrealized_pnl'] == 0
        
        assert price_change_pos['unrealized_pnl'] == 10000  # 10주 * 1000원
        
        assert after_sell_pos['quantity'] == 5
        assert after_sell_pos['realized_pnl'] > 0  # 수익 실현
    
    def test_multi_strategy_coordination(self, event_bus):
        """멀티 전략 조정 테스트"""
        
        strategy_signals = []
        conflicting_signals = []
        
        def on_strategy_signal(event: Event):
            strategy_signals.append(event)
            logger.info(
                f"Strategy signal from {event.data['strategy_name']}: "
                f"{event.data.get('action', 'UNKNOWN')}"
            )
            
            # 충돌 감지
            recent_signals = strategy_signals[-5:]  # 최근 5개
            symbols = {}
            for sig in recent_signals:
                sym = sig.data.get('symbol')
                action = sig.data.get('action')
                if sym and action:
                    if sym in symbols and symbols[sym] != action:
                        conflicting_signals.append((sym, symbols[sym], action))
                    symbols[sym] = action
        
        event_bus.subscribe(EventType.STRATEGY_SIGNAL, on_strategy_signal)
        
        strategy1_pub = TradingSignalPublisher(event_bus, "MomentumStrategy")
        strategy2_pub = TradingSignalPublisher(event_bus, "MeanReversionStrategy")
        
        # 동일 종목에 대해 서로 다른 신호 발생
        symbol = "005930"
        
        # 전략 1: 모멘텀 - 매수 신호
        strategy1_pub.publish_strategy_signal(
            strategy_name="MomentumStrategy",
            signal_data={
                "symbol": symbol,
                "action": "BUY",
                "confidence": 0.8,
                "reason": "Strong upward momentum"
            }
        )
        
        time.sleep(0.05)
        
        # 전략 2: 평균회귀 - 매도 신호 (충돌!)
        strategy2_pub.publish_strategy_signal(
            strategy_name="MeanReversionStrategy", 
            signal_data={
                "symbol": symbol,
                "action": "SELL",
                "confidence": 0.7,
                "reason": "Price extended from mean"
            }
        )
        
        time.sleep(0.1)
        
        # 검증
        assert len(strategy_signals) >= 2
        assert len(conflicting_signals) >= 1  # 충돌 감지됨
        
        # 충돌 내용 확인
        conflict = conflicting_signals[0]
        assert conflict[0] == symbol  # 동일 종목
        assert conflict[1] != conflict[2]  # 다른 액션
        
        logger.warning(f"Strategy conflict detected: {conflict}")
    
    def test_event_bus_health_monitoring(self, event_bus):
        """Event Bus 헬스 모니터링 테스트"""
        
        # 초기 헬스 체크
        health = event_bus.health_check()
        
        assert health['running'] is True
        assert 'metrics' in health
        
        # 이벤트 수신자 등록 (중요!)
        received_events = []
        
        def event_handler(event):
            received_events.append(event)
        
        event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, event_handler)
        
        # 부하 테스트
        publisher = MarketDataPublisher(event_bus, "LoadTester")
        
        start_time = time.time()
        event_count = 100
        
        for i in range(event_count):
            publisher.publish_market_data(
                f"TEST{i:03d}",
                {"price": 1000 + i, "volume": 1000 * i}
            )
        
        # 처리 대기
        time.sleep(0.5)
        
        # 메트릭 확인
        metrics = event_bus.get_metrics()
        
        elapsed_time = time.time() - start_time
        events_per_second = event_count / elapsed_time
        
        logger.info(f"Performance: {events_per_second:.1f} events/second")
        logger.info(f"Received events: {len(received_events)}")
        logger.info(f"Metrics: {metrics}")
        
        assert metrics['total']['published'] >= event_count
        assert len(received_events) > 0  # 실제로 이벤트가 수신되었는지 확인
        assert metrics['total']['received'] > 0  # 메트릭에서도 확인
        assert metrics['performance']['success_rate'] > 0
    
    def test_graceful_shutdown(self, redis_manager):
        """우아한 종료 테스트"""
        
        event_bus = EnhancedEventBus(redis_manager)
        event_bus.start()
        
        shutdown_events = []
        
        def on_engine_stopped(event: Event):
            shutdown_events.append(event)
            logger.info(f"Engine stopped: {event.data['component']}")
        
        event_bus.subscribe(EventType.ENGINE_STOPPED, on_engine_stopped)
        
        # 여러 Publisher 생성
        publishers = [
            MarketDataPublisher(event_bus, "DataCollector"),
            TradingSignalPublisher(event_bus, "StrategyEngine"),
            RiskEventPublisher(event_bus, "RiskEngine"),
            OrderEventPublisher(event_bus, "OrderEngine")
        ]
        
        # 각 컴포넌트 종료 알림
        for pub in publishers:
            pub.publish_event(
                EventType.ENGINE_STOPPED,
                {"component": pub.component_name}
            )
        
        time.sleep(0.2)
        
        # Event Bus 종료
        event_bus.stop()
        
        # 검증
        assert len(shutdown_events) >= len(publishers)
        
        components = [e.data['component'] for e in shutdown_events]
        assert "DataCollector" in components
        assert "StrategyEngine" in components
        assert "RiskEngine" in components
        assert "OrderEngine" in components


if __name__ == "__main__":
    # 직접 실행 시
    pytest.main([__file__, "-v", "-s"])