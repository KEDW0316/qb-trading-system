#!/usr/bin/env python3
"""
Mock KIS 데이터 플로우 테스트

전체 시스템을 실제 KIS 연결 없이 테스트하는 스크립트
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.utils.redis_manager import RedisManager
from qb.utils.event_bus import EventBus, EventType
from qb.engines.data_collector.data_collector import DataCollector, CollectionConfig
from qb.engines.strategy_engine.engine import StrategyEngine
from mock_kis_adapter import MockKISDataAdapter


class MockSystemTester:
    """Mock 시스템 테스터"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 컴포넌트들
        self.redis_manager = None
        self.event_bus = None
        self.data_collector = None
        self.strategy_engine = None
        self.mock_adapter = None
        
        # 테스트 통계
        self.stats = {
            'start_time': None,
            'market_data_received': 0,
            'orderbook_received': 0,
            'signals_generated': 0,
            'test_duration': 0
        }
        
    async def initialize(self):
        """시스템 초기화"""
        self.logger.info("🚀 Initializing Mock System...")
        
        try:
            # Redis 매니저 초기화
            self.logger.info("📊 Initializing Redis Manager...")
            self.redis_manager = RedisManager()
            
            # Redis 연결 확인
            if not self.redis_manager.ping():
                raise Exception("Redis connection failed")
            
            # 이벤트 버스 초기화
            self.logger.info("📡 Initializing Event Bus...")
            self.event_bus = EventBus(self.redis_manager)
            self.event_bus.start()  # Event Bus 시작
            self.logger.info("✅ Event Bus started")
            
            # Mock KIS 어댑터 초기화
            self.logger.info("🎭 Initializing Mock KIS Adapter...")
            mock_config = {
                'tick_interval': 0.5,  # 0.5초마다 데이터 생성
                'mode': 'mock'
            }
            self.mock_adapter = MockKISDataAdapter(mock_config)
            
            # 데이터 컬렉터 초기화 (Mock 어댑터 사용)
            self.logger.info("📥 Initializing Data Collector...")
            collection_config = CollectionConfig(
                symbols=["005930", "000660", "035720"],
                adapters=["mock"],
                max_candles=200,
                collection_interval=1.0,
                quality_check_enabled=False  # Mock 데이터는 품질 검사 생략
            )
            
            self.data_collector = DataCollector(
                self.redis_manager, 
                self.event_bus, 
                collection_config
            )
            
            # Mock 어댑터를 데이터 컬렉터에 수동 등록
            self.data_collector.adapters['mock'] = self.mock_adapter
            
            # Mock 어댑터 연결
            self.logger.info("🔌 Connecting Mock KIS Adapter...")
            if await self.mock_adapter.connect():
                self.logger.info("✅ Mock adapter connected successfully")
            else:
                self.logger.error("❌ Failed to connect mock adapter")
                raise Exception("Mock adapter connection failed")
            
            # 전략 엔진 초기화
            self.logger.info("🧠 Initializing Strategy Engine...")
            self.strategy_engine = StrategyEngine(self.redis_manager, self.event_bus)
            await self.strategy_engine.start()
            
            # MovingAverage1M5M 전략 활성화
            self.logger.info("🎯 Activating MovingAverage1M5M strategy...")
            success = await self.strategy_engine.activate_strategy(
                "MovingAverage1M5MStrategy", 
                symbols=["005930"],  # 삼성전자
                params=None  # 기본 파라미터 사용
            )
            
            if success:
                self.logger.info("✅ Strategy activated successfully")
            else:
                self.logger.error("❌ Failed to activate strategy")
                raise Exception("Strategy activation failed")
            
            # 이벤트 구독 설정
            await self._setup_event_subscriptions()
            
            self.logger.info("✅ System initialization complete!")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize system: {e}")
            raise
    
    async def _setup_event_subscriptions(self):
        """이벤트 구독 설정"""
        try:
            # 시장 데이터 수신 이벤트 구독
            self.event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, self._on_market_data_received)
            
            # 거래 신호 이벤트 구독 (있다면)
            # self.event_bus.subscribe(EventType.TRADING_SIGNAL_GENERATED, self._on_trading_signal)
            
            self.logger.info("📬 Event subscriptions set up")
            
        except Exception as e:
            self.logger.error(f"Failed to set up event subscriptions: {e}")
            raise
    
    async def _on_market_data_received(self, event):
        """시장 데이터 수신 이벤트 핸들러"""
        try:
            data = event.data
            message_type = data.get('message_type', 'trade')
            
            if message_type == 'trade':
                self.stats['market_data_received'] += 1
                symbol = data.get('symbol')
                price = data.get('close')
                volume = data.get('volume')
                
                if self.stats['market_data_received'] % 10 == 0:  # 10개마다 로그
                    self.logger.info(f"📊 Market Data: {symbol} = ₩{price:,} (Vol: {volume:,})")
                    
            elif message_type == 'orderbook':
                self.stats['orderbook_received'] += 1
                symbol = data.get('symbol')
                bid_price = data.get('bid_price')
                ask_price = data.get('ask_price')
                
                if self.stats['orderbook_received'] % 5 == 0:  # 5개마다 로그
                    self.logger.info(f"📋 Orderbook: {symbol} Bid: ₩{bid_price:,} Ask: ₩{ask_price:,}")
                    
        except Exception as e:
            self.logger.error(f"Error handling market data event: {e}")
    
    async def start_test(self, duration: int = 60):
        """테스트 시작"""
        self.logger.info(f"🎬 Starting Mock System Test for {duration} seconds...")
        self.stats['start_time'] = time.time()
        
        try:
            # 데이터 수집기 시작
            self.logger.info("📥 Starting Data Collector...")
            await self.data_collector.start()
            
            # 전략 엔진 시작
            self.logger.info("🧠 Starting Strategy Engine...")
            await self.strategy_engine.start()
            
            # Moving Average 전략 활성화
            self.logger.info("📈 Activating Moving Average Strategy...")
            await self.strategy_engine.activate_strategy(
                "MovingAverage1M5MStrategy",
                symbols=["005930", "000660"],  # 삼성전자, SK하이닉스만 테스트
                params={
                    "ma_period": 5,
                    "confidence_threshold": 0.7
                }
            )
            
            self.logger.info(f"⏰ Running test for {duration} seconds...")
            
            # 중간 중간 상태 체크
            for i in range(duration):
                await asyncio.sleep(1)
                
                # 10초마다 상태 출력
                if (i + 1) % 10 == 0:
                    await self._print_status()
                    
            # 테스트 완료
            self.stats['test_duration'] = time.time() - self.stats['start_time']
            await self._print_final_results()
            
        except Exception as e:
            self.logger.error(f"❌ Test failed: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def _print_status(self):
        """현재 상태 출력"""
        elapsed = time.time() - self.stats['start_time']
        
        self.logger.info("=" * 60)
        self.logger.info(f"📊 Test Status (Elapsed: {elapsed:.1f}s)")
        self.logger.info(f"   Market Data Received: {self.stats['market_data_received']}")
        self.logger.info(f"   Orderbook Received: {self.stats['orderbook_received']}")
        self.logger.info(f"   Signals Generated: {self.stats['signals_generated']}")
        
        # Redis 데이터 확인
        try:
            # 삼성전자 최신 시장 데이터 확인
            market_data = self.redis_manager.get_market_data("005930")
            if market_data:
                self.logger.info(f"   📈 Samsung (005930) Latest: ₩{market_data.get('close', 'N/A')}")
                
            # 호가 데이터 확인
            orderbook = self.redis_manager.get_orderbook_data("005930")
            if orderbook:
                bid = orderbook.get('bid_price', 'N/A')
                ask = orderbook.get('ask_price', 'N/A')
                self.logger.info(f"   📋 Samsung Orderbook: Bid ₩{bid} / Ask ₩{ask}")
                
        except Exception as e:
            self.logger.warning(f"Failed to get Redis data: {e}")
            
        self.logger.info("=" * 60)
    
    async def _print_final_results(self):
        """최종 결과 출력"""
        self.logger.info("🎉 Test Complete!")
        self.logger.info("=" * 60)
        self.logger.info("📊 FINAL RESULTS")
        self.logger.info("=" * 60)
        self.logger.info(f"   Test Duration: {self.stats['test_duration']:.1f} seconds")
        self.logger.info(f"   Market Data Messages: {self.stats['market_data_received']}")
        self.logger.info(f"   Orderbook Messages: {self.stats['orderbook_received']}")
        self.logger.info(f"   Trading Signals: {self.stats['signals_generated']}")
        
        # 초당 처리량 계산
        if self.stats['test_duration'] > 0:
            mps = self.stats['market_data_received'] / self.stats['test_duration']
            ops = self.stats['orderbook_received'] / self.stats['test_duration']
            self.logger.info(f"   Market Data Rate: {mps:.1f} msg/sec")
            self.logger.info(f"   Orderbook Rate: {ops:.1f} msg/sec")
        
        # Redis 최종 상태 확인
        try:
            self.logger.info("📊 Redis Final State:")
            for symbol in ["005930", "000660", "035720"]:
                market_data = self.redis_manager.get_market_data(symbol)
                if market_data:
                    price = market_data.get('close', 'N/A')
                    self.logger.info(f"   {symbol}: ₩{price}")
                    
                # 호가 데이터 확인
                best_bid = self.redis_manager.get_best_bid_price(symbol)
                if best_bid > 0:
                    self.logger.info(f"   {symbol} Best Bid: ₩{int(best_bid)}")
                    
        except Exception as e:
            self.logger.warning(f"Failed to get final Redis state: {e}")
            
        self.logger.info("=" * 60)
    
    async def cleanup(self):
        """리소스 정리"""
        self.logger.info("🧹 Cleaning up...")
        
        try:
            if self.data_collector:
                await self.data_collector.stop()
                
            if self.strategy_engine:
                await self.strategy_engine.stop()
                
            # 이벤트 버스 정리
            if self.event_bus:
                self.event_bus.stop()
                self.logger.info("🛑 Event Bus stopped")
                
            # Redis 연결은 자동으로 닫힘
                
            self.logger.info("✅ Cleanup complete")
            
        except Exception as e:
            self.logger.error(f"❌ Cleanup failed: {e}")


async def main():
    """메인 함수"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('mock_test.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("🎭 Mock KIS System Test Starting...")
    
    # 테스터 초기화 및 실행
    tester = MockSystemTester()
    
    try:
        # 시스템 초기화
        await tester.initialize()
        
        # 테스트 실행 (5초)
        await tester.start_test(duration=5)
        
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())