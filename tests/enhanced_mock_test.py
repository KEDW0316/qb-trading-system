#!/usr/bin/env python3
"""
Enhanced Mock Test - 전체 거래 파이프라인 검증

목적: 장 마감 시간에도 데이터 수집부터 주문 직전까지의 
      전체 시스템 동작을 검증
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
import json

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.utils.redis_manager import RedisManager
from qb.utils.event_bus import EventBus, EventType
from qb.engines.data_collector.data_collector import DataCollector, CollectionConfig
from qb.engines.strategy_engine.engine import StrategyEngine
from qb.engines.risk_engine.engine import RiskEngine
from qb.engines.order_engine.engine import OrderEngine
from qb.database.connection import DatabaseManager
from mock_kis_adapter import MockKISDataAdapter

# Mock 브로커 클라이언트 추가
class MockBrokerClient:
    """실제 주문을 보내지 않고 검증만 하는 Mock 브로커"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.placed_orders = []
        
    async def place_order(self, order):
        """주문 검증만 하고 기록"""
        self.logger.info(f"🎯 [MOCK ORDER] {order.side} {order.quantity}주 @ {order.price}")
        self.placed_orders.append({
            'timestamp': datetime.now().isoformat(),
            'symbol': order.symbol,
            'side': order.side,
            'quantity': order.quantity,
            'price': order.price,
            'order_type': order.order_type
        })
        
        # 실제로는 주문하지 않고 성공 응답
        return {
            'order_id': f'MOCK_{len(self.placed_orders)}',
            'status': 'ACCEPTED',
            'message': 'Mock order accepted (not sent to market)'
        }
    
    async def cancel_order(self, order_id):
        self.logger.info(f"🚫 [MOCK CANCEL] Order {order_id}")
        return {'status': 'CANCELLED'}
    
    async def get_order_status(self, order_id):
        return {'status': 'MOCK', 'filled_quantity': 0}


class EnhancedMockTester:
    """전체 파이프라인 테스터"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 전체 시스템 컴포넌트
        self.redis_manager = None
        self.event_bus = None
        self.db_manager = None
        self.data_collector = None
        self.strategy_engine = None
        self.risk_engine = None
        self.order_engine = None
        self.mock_broker = None
        
        # 이벤트 추적
        self.event_tracker = {
            'market_data': 0,
            'indicators_updated': 0,
            'trading_signals': 0,
            'risk_checks': 0,
            'order_attempts': 0,
            'orders_placed': 0,
            'errors': []
        }
        
    async def initialize(self):
        """전체 시스템 초기화"""
        self.logger.info("🚀 Initializing Full Pipeline Test System...")
        
        try:
            # 1. 인프라 초기화
            self.redis_manager = RedisManager()
            self.db_manager = DatabaseManager()
            self.event_bus = EventBus(self.redis_manager)
            self.event_bus.start()  # EventBus 시작
            
            # 2. Mock 데이터 어댑터
            mock_config = {
                'tick_interval': 1.0,  # 1초마다 데이터
                'mode': 'mock'
            }
            self.mock_adapter = MockKISDataAdapter(mock_config)
            
            # 3. 데이터 수집기
            collection_config = CollectionConfig(
                symbols=["005930"],  # 삼성전자만 테스트
                adapters=["mock"]
            )
            self.data_collector = DataCollector(
                self.redis_manager, 
                self.event_bus, 
                collection_config
            )
            self.data_collector.adapters['mock'] = self.mock_adapter
            
            # 4. 전략 엔진
            self.strategy_engine = StrategyEngine(
                self.redis_manager, 
                self.event_bus
            )
            
            # 5. 리스크 엔진
            self.risk_engine = RiskEngine(
                self.db_manager,
                self.redis_manager,
                self.event_bus,
                config={
                    'enable_risk_monitoring': True,
                    'monitoring_interval': 5,
                    'max_position_size_ratio': 0.1,
                    'max_daily_loss': 100000,
                    'default_stop_loss_pct': 3.0,
                    'min_cash_reserve_ratio': 0.2,
                    'max_orders_per_day': 10,
                    'max_consecutive_losses': 5,
                    'max_total_exposure_ratio': 0.8
                }
            )
            
            # 6. Mock 브로커로 주문 엔진 설정
            self.mock_broker = MockBrokerClient()
            
            # OrderQueue와 필요한 컴포넌트들
            from qb.engines.order_engine.order_queue import OrderQueue
            from qb.engines.order_engine.position_manager import PositionManager
            from qb.engines.order_engine.commission_calculator import KoreanStockCommissionCalculator
            
            self.order_engine = OrderEngine(
                broker_client=self.mock_broker,
                order_queue=OrderQueue(self.redis_manager),
                position_manager=PositionManager(self.redis_manager, self.db_manager),
                commission_calculator=KoreanStockCommissionCalculator(),
                event_bus=self.event_bus,
                redis_manager=self.redis_manager
            )
            
            # 7. 이벤트 구독
            await self._setup_event_tracking()
            
            self.logger.info("✅ System initialization complete!")
            
        except Exception as e:
            self.logger.error(f"❌ Initialization failed: {e}")
            raise
    
    async def _setup_event_tracking(self):
        """모든 이벤트 추적 설정"""
        
        # 데이터 수신
        self.event_bus.subscribe(
            EventType.MARKET_DATA_RECEIVED,
            lambda e: self._track_event('market_data', e)
        )
        
        # 지표 업데이트
        self.event_bus.subscribe(
            EventType.INDICATORS_UPDATED,
            lambda e: self._track_event('indicators_updated', e)
        )
        
        # 거래 신호
        self.event_bus.subscribe(
            EventType.TRADING_SIGNAL,
            lambda e: self._track_event('trading_signals', e)
        )
        
        # 리스크 체크
        self.event_bus.subscribe(
            EventType.RISK_ALERT,
            lambda e: self._track_event('risk_checks', e)
        )
        
        # 주문 시도
        self.event_bus.subscribe(
            EventType.ORDER_PLACED,
            lambda e: self._track_event('order_attempts', e)
        )
        
        # 주문 실행
        self.event_bus.subscribe(
            EventType.ORDER_EXECUTED,
            lambda e: self._track_event('orders_placed', e)
        )
        
        self.logger.info("📬 Event tracking setup complete")
    
    def _track_event(self, event_type: str, event):
        """이벤트 추적 및 로깅 (동기 버전)"""
        self.event_tracker[event_type] += 1
        
        # 중요 이벤트는 상세 로깅
        if event_type == 'trading_signals':
            data = event.data if hasattr(event, 'data') else event
            action = data.get('action', 'UNKNOWN') if isinstance(data, dict) else 'SIGNAL'
            symbol = data.get('symbol', 'UNKNOWN') if isinstance(data, dict) else 'N/A'
            price = data.get('price', 0) if isinstance(data, dict) else 0
            confidence = data.get('confidence', 0) if isinstance(data, dict) else 0
            
            self.logger.info(
                f"📈 [SIGNAL] {action} {symbol} @ {price} (confidence: {confidence:.2f})"
            )
        elif event_type == 'order_attempts':
            data = event.data if hasattr(event, 'data') else event
            side = data.get('side', 'UNKNOWN') if isinstance(data, dict) else 'ORDER'
            quantity = data.get('quantity', 0) if isinstance(data, dict) else 0
            price = data.get('price', 0) if isinstance(data, dict) else 0
            
            self.logger.info(
                f"📋 [ORDER ATTEMPT] {side} {quantity}주 @ {price}"
            )
        elif event_type == 'market_data':
            self.logger.info(f"📊 [MARKET DATA] Event tracked: #{self.event_tracker[event_type]}")
    
    async def run_pipeline_test(self, duration: int = 30):
        """전체 파이프라인 테스트 실행"""
        self.logger.info(f"🎬 Starting Full Pipeline Test for {duration} seconds...")
        
        try:
            # 1. Mock 어댑터 연결
            await self.mock_adapter.connect()
            
            # 2. 모든 엔진 시작
            await self.data_collector.start()
            await self.strategy_engine.start()
            await self.risk_engine.start()
            await self.order_engine.start()
            
            # 3. 전략 활성화 (낮은 임계값으로 신호 생성 유도)
            await self.strategy_engine.activate_strategy(
                "MovingAverage1M5MStrategy",
                symbols=["005930"],
                params={
                    "ma_period": 3,  # 짧은 기간으로 신호 빈도 증가
                    "confidence_threshold": 0.5  # 낮은 임계값
                }
            )
            
            # 4. 테스트 실행
            self.logger.info("⏰ Pipeline test running...")
            
            for i in range(duration):
                await asyncio.sleep(1)
                
                # 10초마다 상태 출력
                if (i + 1) % 10 == 0:
                    await self._print_pipeline_status()
            
            # 5. 최종 결과
            await self._print_final_results()
            
        except Exception as e:
            self.logger.error(f"❌ Pipeline test failed: {e}")
            self.event_tracker['errors'].append(str(e))
            raise
        finally:
            await self.cleanup()
    
    async def _print_pipeline_status(self):
        """파이프라인 상태 출력"""
        self.logger.info("=" * 60)
        self.logger.info("📊 Pipeline Status")
        self.logger.info(f"  1️⃣ Market Data: {self.event_tracker['market_data']}")
        self.logger.info(f"  2️⃣ Indicators: {self.event_tracker['indicators_updated']}")
        self.logger.info(f"  3️⃣ Signals: {self.event_tracker['trading_signals']}")
        self.logger.info(f"  4️⃣ Risk Checks: {self.event_tracker['risk_checks']}")
        self.logger.info(f"  5️⃣ Order Attempts: {self.event_tracker['order_attempts']}")
        self.logger.info(f"  6️⃣ Orders Placed: {self.event_tracker['orders_placed']}")
        
        # Mock 브로커의 주문 확인
        if self.mock_broker.placed_orders:
            self.logger.info(f"  📋 Mock Orders: {len(self.mock_broker.placed_orders)}")
            for order in self.mock_broker.placed_orders[-3:]:  # 최근 3개만
                self.logger.info(
                    f"     - {order['side']} {order['quantity']}주 @ {order['price']}"
                )
        
        self.logger.info("=" * 60)
    
    async def _print_final_results(self):
        """최종 테스트 결과"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("🎉 PIPELINE TEST COMPLETE")
        self.logger.info("=" * 60)
        
        # 파이프라인 검증
        pipeline_complete = (
            self.event_tracker['market_data'] > 0 and
            self.event_tracker['trading_signals'] > 0 and
            self.event_tracker['order_attempts'] > 0
        )
        
        if pipeline_complete:
            self.logger.info("✅ Full Pipeline Verified!")
            self.logger.info("   Data → Event → Signal → Risk → Order")
        else:
            self.logger.info("❌ Pipeline Incomplete!")
            if self.event_tracker['market_data'] == 0:
                self.logger.info("   ⚠️ No market data received")
            if self.event_tracker['trading_signals'] == 0:
                self.logger.info("   ⚠️ No trading signals generated")
            if self.event_tracker['order_attempts'] == 0:
                self.logger.info("   ⚠️ No order attempts made")
        
        # 상세 통계
        self.logger.info("\n📊 Detailed Statistics:")
        for event_type, count in self.event_tracker.items():
            if event_type != 'errors':
                self.logger.info(f"   {event_type}: {count}")
        
        # 에러 확인
        if self.event_tracker['errors']:
            self.logger.info("\n⚠️ Errors:")
            for error in self.event_tracker['errors']:
                self.logger.info(f"   - {error}")
        
        # Mock 주문 요약
        if self.mock_broker.placed_orders:
            self.logger.info(f"\n📋 Total Mock Orders: {len(self.mock_broker.placed_orders)}")
            with open('mock_orders.json', 'w') as f:
                json.dump(self.mock_broker.placed_orders, f, indent=2)
            self.logger.info("   Saved to mock_orders.json")
        
        self.logger.info("=" * 60)
    
    async def cleanup(self):
        """리소스 정리"""
        self.logger.info("🧹 Cleaning up...")
        
        if self.data_collector:
            await self.data_collector.stop()
        if self.strategy_engine:
            await self.strategy_engine.stop()
        if self.risk_engine:
            await self.risk_engine.stop()
        if self.order_engine:
            await self.order_engine.stop()
        if self.event_bus:
            self.event_bus.stop()
        
        self.logger.info("✅ Cleanup complete")


async def main():
    """메인 실행 함수"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("🚀 Enhanced Mock Test - Full Pipeline Verification")
    
    tester = EnhancedMockTester()
    
    try:
        await tester.initialize()
        await tester.run_pipeline_test(duration=300)  # 5분 테스트
        
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())