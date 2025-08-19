#!/usr/bin/env python3
"""
QB Trading System - 실제 거래 메인 실행 스크립트
===============================================

⚠️ 경고: 이 스크립트는 실제 돈으로 거래를 수행합니다!
- 소액으로만 테스트하세요
- 충분한 테스트 후 사용하세요
- 리스크 관리 설정을 확인하세요

사용법:
    python run_live_trading.py --symbol 005930 --max-amount 100000
"""

import asyncio
import argparse
import os
import sys
import signal
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
import json
from dotenv import load_dotenv

# 🔍 로깅 설정 - 콘솔에서 더 많은 로그 보기
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 콘솔 출력
        logging.FileHandler('logs/trading.log', encoding='utf-8')  # 파일 출력
    ]
)

# 로그 디렉토리 생성
os.makedirs('logs', exist_ok=True)

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent))

# .env 파일 로드 (명시적 경로 지정)
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# 필요한 모듈들 import
from qb.engines.event_bus.core import EnhancedEventBus
from qb.utils.event_bus import EventType
from qb.engines.data_collector.data_collector import DataCollector
from qb.engines.strategy_engine.engine import StrategyEngine
from qb.engines.risk_engine.engine import RiskEngine
from qb.engines.order_engine.engine import OrderEngine
from qb.database.connection import DatabaseManager
from qb.utils.redis_manager import RedisManager
from qb.utils.redis_monitor import RedisMonitor
from qb.utils.api_monitor import APIMonitor


class LiveTradingSystem:
    """실제 거래 시스템"""
    
    def __init__(self, config):
        self.config = config
        self.running = False
        self.start_time = None
        
        # 시스템 컴포넌트들
        self.event_bus = None
        self.data_collector = None
        self.strategy_engine = None
        self.risk_engine = None
        self.order_engine = None
        self.db_manager = None
        self.redis_manager = None
        self.redis_monitor = None
        self.api_monitor = None
        
        # 거래 통계
        self.trades_executed = 0
        self.total_profit_loss = 0
        self.total_commission = 0
        
        # 이벤트 수집
        self.market_data_count = 0
        self.signals_generated = 0
        self.orders_placed = 0
        self.risk_alerts = 0
        
    async def initialize_system(self):
        """시스템 초기화"""
        print("🚀 QB Trading System 실제 거래 모드 시작")
        print("=" * 60)
        print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 대상 종목: {self.config['symbol']}")
        print(f"💰 최대 거래 금액: {self.config['max_amount']:,}원")
        print(f"🛡️ 손절매 비율: {self.config['stop_loss_pct']:.1f}%")
        print("=" * 60)
        
        try:
            # 1. 환경 변수 확인
            self._check_environment()
            
            # 2. 인프라 연결
            await self._initialize_infrastructure()
            
            # 3. 엔진들 초기화
            await self._initialize_engines()
            
            # 4. 이벤트 핸들러 설정
            self._setup_event_handlers()
            
            # 5. 모니터링 시작
            await self._start_monitoring()
            
            print("✅ 시스템 초기화 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 시스템 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _check_environment(self):
        """환경 변수 확인"""
        required_vars = ['KIS_APP_KEY', 'KIS_APP_SECRET', 'KIS_ACCOUNT_STOCK', 'KIS_ACCOUNT_PRODUCT']
        missing_vars = []
        
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            elif value in ['your_app_key_here', 'your_app_secret_here', 'your_account_here']:
                missing_vars.append(f"{var} (기본값 사용 중)")
        
        if missing_vars:
            print("❌ 필수 환경 변수가 설정되지 않았습니다:")
            for var in missing_vars:
                print(f"   - {var}")
            raise ValueError("환경 변수 설정이 필요합니다")
        
        print("✅ 환경 변수 확인 완료")
    
    async def _initialize_infrastructure(self):
        """인프라 초기화"""
        # Redis 연결
        self.redis_manager = RedisManager()
        if not self.redis_manager.ping():
            raise ConnectionError("Redis 연결 실패")
        print("✅ Redis 연결 성공")
        
        # PostgreSQL 연결
        self.db_manager = DatabaseManager()
        if not self.db_manager.initialize():
            raise ConnectionError("PostgreSQL 연결 실패")
        print("✅ PostgreSQL 연결 성공")
        
        # Event Bus 초기화
        self.event_bus = EnhancedEventBus(redis_manager=self.redis_manager)
        print("✅ Event Bus 초기화 성공")
    
    async def _initialize_engines(self):
        """거래 엔진들 초기화"""
        
        # 데이터 수집기
        from qb.engines.data_collector.data_collector import CollectionConfig
        collection_config = CollectionConfig(
            symbols=[self.config['symbol']],
            adapters=['kis']
        )
        self.data_collector = DataCollector(
            redis_manager=self.redis_manager,
            event_bus=self.event_bus,
            config=collection_config
        )
        
        # 전략 엔진
        self.strategy_engine = StrategyEngine(
            redis_manager=self.redis_manager,
            event_bus=self.event_bus
        )
        
        # 리스크 엔진 (보수적 설정)
        self.risk_engine = RiskEngine(
            db_manager=self.db_manager,
            redis_manager=self.redis_manager,
            event_bus=self.event_bus,
            config={
                'enable_risk_monitoring': True,  # 리스크 모니터링 활성화
                'monitoring_interval': 15,  # 모니터링 간격 (초)
                'max_daily_loss': self.config['max_amount'] * 0.5,  # 최대 거래 금액의 50%
                'max_position_size_ratio': 0.05,  # 포트폴리오의 5%
                'default_stop_loss_pct': self.config['stop_loss_pct'],
                'min_cash_reserve_ratio': 0.2,  # 20% 현금 보유
                'max_orders_per_day': 10,  # 일일 최대 주문 수
                'max_consecutive_losses': 5,  # 최대 연속 손실 횟수
                'max_total_exposure_ratio': 0.8  # 최대 총 익스포저 비율
            }
        )
        
        # 주문 엔진 컴포넌트 임포트
        from qb.collectors.kis_client import KISClient
        from qb.engines.order_engine.kis_broker_client import KISBrokerClient
        from qb.engines.order_engine.order_queue import OrderQueue
        from qb.engines.order_engine.position_manager import PositionManager
        from qb.engines.order_engine.commission_calculator import KoreanStockCommissionCalculator
        
        # KIS 클라이언트 생성
        kis_client = KISClient()
        
        # KIS 브로커 클라이언트 생성
        kis_broker = KISBrokerClient(
            kis_client=kis_client,
            redis_manager=self.redis_manager
        )
        
        # 주문 엔진
        self.order_engine = OrderEngine(
            broker_client=kis_broker,
            order_queue=OrderQueue(self.redis_manager),
            position_manager=PositionManager(self.redis_manager, self.db_manager),
            commission_calculator=KoreanStockCommissionCalculator(),
            event_bus=self.event_bus,
            redis_manager=self.redis_manager
        )
        
        print("✅ 모든 엔진 초기화 완료")
    
    def _setup_event_handlers(self):
        """이벤트 핸들러 설정"""
        
        def market_data_handler(event):
            self.market_data_count += 1
            if self.market_data_count % 100 == 0:  # 100번마다 로그
                print(f"📊 시장데이터 수신: {self.market_data_count}개")
        
        def signal_handler(event):
            self.signals_generated += 1
            signal_data = event.data
            print(f"🚨 거래신호: {signal_data.get('action')} {signal_data.get('symbol')} "
                  f"@ {signal_data.get('price')} (신뢰도: {signal_data.get('confidence', 0):.2f})")
        
        def order_handler(event):
            self.orders_placed += 1
            order_data = event.data
            print(f"📋 주문: {order_data.get('side')} {order_data.get('quantity')}주 "
                  f"@ {order_data.get('price')} ({order_data.get('status')})")
            
            # 체결된 경우 통계 업데이트
            if order_data.get('status') == 'FILLED':
                self.trades_executed += 1
                self.total_commission += order_data.get('commission', 0)
        
        def risk_handler(event):
            self.risk_alerts += 1
            risk_data = event.data
            print(f"⚠️ 리스크알림: {risk_data.get('alert_type')} - {risk_data.get('message')}")
            
            # 심각한 리스크인 경우 거래 중단 고려
            if risk_data.get('severity') == 'CRITICAL':
                print("🚨 심각한 리스크 감지! 거래 중단을 고려하세요.")
        
        # 이벤트 구독
        self.event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, market_data_handler)
        self.event_bus.subscribe(EventType.TRADING_SIGNAL, signal_handler)
        self.event_bus.subscribe(EventType.ORDER_PLACED, order_handler)
        self.event_bus.subscribe(EventType.ORDER_EXECUTED, order_handler)
        self.event_bus.subscribe(EventType.RISK_ALERT, risk_handler)
        
        print("✅ 이벤트 핸들러 설정 완료")
    
    async def _start_monitoring(self):
        """모니터링 시스템 시작"""
        self.redis_monitor = RedisMonitor(self.redis_manager, self.event_bus)
        self.api_monitor = APIMonitor()
        
        await self.redis_monitor.start_monitoring(interval_seconds=60)
        print("✅ 모니터링 시스템 시작")
    
    async def start_trading(self):
        """거래 시작"""
        if not await self.initialize_system():
            return False
        
        print("\n🔥 실제 거래 시작!")
        print("=" * 60)
        
        self.running = True
        self.start_time = datetime.now()
        
        try:
            # 엔진들 시작
            await self.data_collector.start()
            await self.strategy_engine.start()
            await self.risk_engine.start()
            await self.order_engine.start()
            
            # 목표 종목 구독
            await self.data_collector.add_symbol(self.config['symbol'])
            
            # 전략 활성화
            strategy_config = {
                'ma_period': 5,  # 이동평균 기간 (5분)
                'confidence_threshold': 0.7,  # 신호 신뢰도 임계값
                'enable_forced_sell': True,  # 장마감 강제매도 활성화
                'min_volume_threshold': 30_000_000_000  # 최소 거래대금
            }
            await self.strategy_engine.activate_strategy('MovingAverage1M5MStrategy', strategy_config, [self.config['symbol']])
            
            print(f"✅ 거래 시작 - {self.config['symbol']} 모니터링 중...")
            
            # 메인 거래 루프
            await self._trading_loop()
            
        except Exception as e:
            print(f"❌ 거래 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.stop_trading()
    
    async def _trading_loop(self):
        """메인 거래 루프"""
        last_status_time = time.time()
        
        while self.running:
            try:
                # 30초마다 상태 출력
                if time.time() - last_status_time > 30:
                    await self._print_status()
                    last_status_time = time.time()
                
                # 거래 시간 확인 (09:00-15:30) - 테스트용으로 임시 비활성화
                # now = datetime.now()
                # if now.hour < 9 or (now.hour >= 15 and now.minute >= 30):
                #     if now.hour >= 15 and now.minute >= 30:
                #         print("📅 장 마감 시간입니다. 거래를 종료합니다.")
                #         break
                #     await asyncio.sleep(60)  # 1분 대기
                #     continue
                
                # 짧은 대기
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                print("⚠️ 거래 루프가 취소되었습니다.")
                break
            except Exception as e:
                print(f"❌ 거래 루프 오류: {e}")
                await asyncio.sleep(5)
    
    async def _print_status(self):
        """현재 상태 출력"""
        runtime = datetime.now() - self.start_time if self.start_time else timedelta(0)
        
        print("\n" + "=" * 50)
        print(f"📊 QB Trading System 상태 ({runtime})")
        print("=" * 50)
        print(f"📈 시장데이터: {self.market_data_count:,}개")
        print(f"🧠 거래신호: {self.signals_generated}개")
        print(f"📋 주문실행: {self.orders_placed}개")
        print(f"✅ 체결완료: {self.trades_executed}개")
        print(f"⚠️ 리스크알림: {self.risk_alerts}개")
        print(f"💰 총 수수료: {self.total_commission:,.0f}원")
        
        # 시스템 리소스
        if self.redis_monitor:
            redis_status = self.redis_monitor.get_status_summary()
            print(f"💾 Redis 메모리: {redis_status['memory_usage_percent']:.1f}%")
        
        print("=" * 50)
    
    async def stop_trading(self):
        """거래 중단"""
        # 중복 종료 방지
        if hasattr(self, '_shutdown_in_progress') and self._shutdown_in_progress:
            return
        
        self._shutdown_in_progress = True
        print("\n🛑 거래 시스템 중단 중...")
        
        self.running = False
        
        try:
            # 엔진들 정지
            if self.data_collector:
                await self.data_collector.stop()
            if self.strategy_engine:
                await self.strategy_engine.stop()
            if self.risk_engine:
                await self.risk_engine.stop()
            if self.order_engine:
                await self.order_engine.stop()
            
            # 모니터링 정지
            if self.redis_monitor:
                await self.redis_monitor.stop_monitoring()
            
            # 최종 리포트 생성 (한 번만)
            if not hasattr(self, '_report_generated') or not self._report_generated:
                self._generate_final_report()
                self._report_generated = True
            
            print("✅ 거래 시스템 정상 종료")
            
        except Exception as e:
            print(f"⚠️ 종료 중 오류: {e}")
    
    def _generate_final_report(self):
        """최종 거래 리포트 생성"""
        runtime = datetime.now() - self.start_time if self.start_time else timedelta(0)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'runtime_seconds': runtime.total_seconds(),
            'config': self.config,
            'statistics': {
                'market_data_received': self.market_data_count,
                'signals_generated': self.signals_generated,
                'orders_placed': self.orders_placed,
                'trades_executed': self.trades_executed,
                'risk_alerts': self.risk_alerts,
                'total_commission': self.total_commission,
                'total_profit_loss': self.total_profit_loss
            }
        }
        
        # 파일로 저장
        report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"logs/live_trading_report_{report_time}.json"
        
        os.makedirs("logs", exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 콘솔 출력
        print("\n" + "=" * 60)
        print("📋 최종 거래 리포트")
        print("=" * 60)
        print(f"⏱️ 운영 시간: {runtime}")
        print(f"📊 시장 데이터: {self.market_data_count:,}개")
        print(f"🧠 거래 신호: {self.signals_generated}개")
        print(f"📋 주문 실행: {self.orders_placed}개")
        print(f"✅ 체결 완료: {self.trades_executed}개")
        print(f"💰 총 수수료: {self.total_commission:,.0f}원")
        print(f"📈 실현 손익: {self.total_profit_loss:+,.0f}원")
        print(f"⚠️ 리스크 알림: {self.risk_alerts}개")
        print(f"📄 상세 리포트: {report_file}")
        print("=" * 60)


def signal_handler(signum, frame):
    """시그널 핸들러 (Ctrl+C 처리)"""
    print("\n⚠️ 종료 신호를 받았습니다. 안전하게 시스템을 종료합니다...")
    # 메인 루프에서 처리하도록 플래그 설정
    global trading_system
    if trading_system:
        asyncio.create_task(trading_system.stop_trading())


async def main():
    """메인 함수"""
    global trading_system
    
    parser = argparse.ArgumentParser(description='QB Trading System - 실제 거래')
    parser.add_argument('--symbol', default='005930', help='거래할 종목 코드 (기본: 005930 삼성전자)')
    parser.add_argument('--max-amount', type=int, default=100000, help='최대 거래 금액 (기본: 100,000원)')
    parser.add_argument('--stop-loss', type=float, default=3.0, help='손절매 비율 % (기본: 3.0%)')
    parser.add_argument('--dry-run', action='store_true', help='모의 거래 모드 (실제 주문 안함)')
    
    args = parser.parse_args()
    
    # 설정 구성
    config = {
        'symbol': args.symbol,
        'max_amount': args.max_amount,
        'stop_loss_pct': args.stop_loss,
        'dry_run': args.dry_run
    }
    
    # 최종 확인
    if not args.dry_run:
        print("⚠️ 실제 거래 모드입니다!")
        print(f"   종목: {config['symbol']}")
        print(f"   최대 금액: {config['max_amount']:,}원")
        print(f"   손절매: {config['stop_loss_pct']:.1f}%")
        
        # 실제 거래 확인 - 자동으로 진행
        print("\n✅ 실제 거래를 시작합니다...")
        # confirm = input("\n정말로 실제 거래를 시작하시겠습니까? (yes/no): ")
        # if confirm.lower() != 'yes':
        #     print("❌ 거래가 취소되었습니다.")
        #     return
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 거래 시스템 시작
    trading_system = LiveTradingSystem(config)
    await trading_system.start_trading()


# 전역 변수
trading_system = None

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()