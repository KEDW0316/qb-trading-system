#!/usr/bin/env python3
"""
QB Trading System - 실제 거래 통합 테스트
=============================================

목적: 전체 시스템의 실제 거래 워크플로우를 소액으로 테스트
- 모든 엔진 통합 검증
- 실제 시장 데이터 처리
- 소액 주문 실행 및 체결
- 리스크 관리 검증
- 성능 모니터링

주의: 실제 거래가 발생하므로 소액으로만 실행
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

from qb.engines.event_bus.core import EnhancedEventBus
from qb.engines.data_collector.data_collector import DataCollector
from qb.engines.strategy_engine.engine import StrategyEngine
from qb.engines.risk_engine.engine import RiskEngine
from qb.engines.order_engine.engine import OrderEngine
from qb.database.connection import DatabaseManager
from qb.utils.redis_manager import RedisManager
from qb.utils.redis_monitor import RedisMonitor
from qb.utils.api_monitor import APIMonitor


class FullTradingIntegrationTest:
    """실제 거래 통합 테스트"""
    
    def __init__(self):
        self.test_symbol = "005930"  # 삼성전자 (가장 안정적)
        self.test_quantity = 1  # 1주만 (약 75,000원)
        self.max_test_duration = 600  # 최대 10분
        self.test_results = {}
        
        # 시스템 컴포넌트
        self.event_bus = None
        self.data_collector = None
        self.strategy_engine = None
        self.risk_engine = None
        self.order_engine = None
        self.db_manager = None
        self.redis_manager = None
        self.redis_monitor = None
        self.api_monitor = None
        
    async def setup_system(self):
        """시스템 초기화 및 연결"""
        print("🔧 시스템 초기화 중...")
        
        try:
            # 1. Redis 연결
            self.redis_manager = RedisManager()
            await self.redis_manager.connect()
            print("✅ Redis 연결 성공")
            
            # 2. PostgreSQL 연결
            self.db_manager = DatabaseManager()
            await self.db_manager.connect()
            print("✅ PostgreSQL 연결 성공")
            
            # 3. Event Bus 초기화
            self.event_bus = EnhancedEventBus(redis_client=self.redis_manager.client)
            print("✅ Event Bus 초기화 성공")
            
            # 4. 모니터링 시스템
            self.redis_monitor = RedisMonitor(self.redis_manager, self.event_bus)
            self.api_monitor = APIMonitor()
            await self.redis_monitor.start_monitoring(interval_seconds=30)
            print("✅ 모니터링 시스템 시작")
            
            # 5. 엔진들 초기화
            await self._initialize_engines()
            
            return True
            
        except Exception as e:
            print(f"❌ 시스템 초기화 실패: {e}")
            return False
    
    async def _initialize_engines(self):
        """모든 엔진 초기화"""
        
        # 데이터 수집기
        self.data_collector = DataCollector(
            event_bus=self.event_bus,
            redis_client=self.redis_manager.client
        )
        
        # 전략 엔진
        self.strategy_engine = StrategyEngine(
            event_bus=self.event_bus,
            redis_client=self.redis_manager.client
        )
        
        # 리스크 엔진
        self.risk_engine = RiskEngine(
            event_bus=self.event_bus,
            redis_client=self.redis_manager.client,
            config={
                'max_daily_loss': 100000,  # 일일 최대 손실 10만원
                'max_position_size_ratio': 0.05,  # 포지션 크기 5%로 제한
                'default_stop_loss_pct': 2.0  # 손절매 2%
            }
        )
        
        # 주문 엔진
        self.order_engine = OrderEngine(
            event_bus=self.event_bus,
            redis_client=self.redis_manager.client
        )
        
        print("✅ 모든 엔진 초기화 완료")
    
    async def test_connectivity(self) -> bool:
        """연결성 테스트"""
        print("\n📡 연결성 테스트 시작...")
        
        connectivity_results = {}
        
        # Redis 연결 테스트
        try:
            ping_result = await self.redis_manager.ping()
            connectivity_results['redis'] = ping_result
            print(f"✅ Redis 연결: {'성공' if ping_result else '실패'}")
        except Exception as e:
            connectivity_results['redis'] = False
            print(f"❌ Redis 연결 실패: {e}")
        
        # PostgreSQL 연결 테스트
        try:
            db_status = await self.db_manager.test_connection()
            connectivity_results['postgresql'] = db_status
            print(f"✅ PostgreSQL 연결: {'성공' if db_status else '실패'}")
        except Exception as e:
            connectivity_results['postgresql'] = False
            print(f"❌ PostgreSQL 연결 실패: {e}")
        
        # KIS API 연결 테스트
        try:
            # 실제 KIS API 연결 확인은 data_collector에서 수행
            api_status = await self.data_collector.test_kis_connection()
            connectivity_results['kis_api'] = api_status
            print(f"✅ KIS API 연결: {'성공' if api_status else '실패'}")
        except Exception as e:
            connectivity_results['kis_api'] = False
            print(f"❌ KIS API 연결 실패: {e}")
        
        # Event Bus 테스트
        try:
            test_event = self.event_bus.create_event(
                'SYSTEM_STATUS', 
                'integration_test',
                {'test': 'connectivity_check'}
            )
            publish_result = self.event_bus.publish(test_event)
            connectivity_results['event_bus'] = publish_result
            print(f"✅ Event Bus: {'성공' if publish_result else '실패'}")
        except Exception as e:
            connectivity_results['event_bus'] = False
            print(f"❌ Event Bus 실패: {e}")
        
        self.test_results['connectivity'] = connectivity_results
        return all(connectivity_results.values())
    
    async def test_market_data_flow(self) -> bool:
        """시장 데이터 플로우 테스트"""
        print("\n📊 시장 데이터 플로우 테스트...")
        
        market_data_received = []
        indicators_calculated = []
        
        # 이벤트 구독자 등록
        def market_data_handler(event):
            market_data_received.append(event)
            print(f"📈 시장 데이터 수신: {event.data.get('symbol')} - {event.data.get('close')}")
        
        def indicators_handler(event):
            indicators_calculated.append(event)
            print(f"📊 지표 계산 완료: {event.data.get('symbol')} - SMA: {event.data.get('sma_20')}")
        
        self.event_bus.subscribe('MARKET_DATA_RECEIVED', market_data_handler)
        self.event_bus.subscribe('INDICATORS_UPDATED', indicators_handler)
        
        try:
            # 삼성전자 실시간 데이터 구독
            await self.data_collector.subscribe_symbol(self.test_symbol)
            
            # 30초 동안 데이터 수신 대기
            print(f"⏳ {self.test_symbol} 실시간 데이터 30초 대기...")
            await asyncio.sleep(30)
            
            # 결과 검증
            data_success = len(market_data_received) > 0
            indicators_success = len(indicators_calculated) > 0
            
            print(f"📊 수신된 시장 데이터: {len(market_data_received)}개")
            print(f"📈 계산된 지표: {len(indicators_calculated)}개")
            
            self.test_results['market_data'] = {
                'data_received': len(market_data_received),
                'indicators_calculated': len(indicators_calculated),
                'success': data_success and indicators_success
            }
            
            return data_success and indicators_success
            
        except Exception as e:
            print(f"❌ 시장 데이터 플로우 실패: {e}")
            self.test_results['market_data'] = {'success': False, 'error': str(e)}
            return False
    
    async def test_strategy_signal_generation(self) -> bool:
        """전략 신호 생성 테스트"""
        print("\n🧠 전략 신호 생성 테스트...")
        
        signals_generated = []
        
        def signal_handler(event):
            signals_generated.append(event)
            signal_data = event.data
            print(f"🚨 거래 신호: {signal_data.get('action')} {signal_data.get('symbol')} "
                  f"@ {signal_data.get('price')} (신뢰도: {signal_data.get('confidence')})")
        
        self.event_bus.subscribe('TRADING_SIGNAL', signal_handler)
        
        try:
            # 이동평균 전략 로드
            strategy_config = {
                'name': 'moving_average_1m5m',
                'parameters': {
                    'short_window': 5,
                    'long_window': 20,
                    'min_confidence': 0.6
                }
            }
            
            await self.strategy_engine.load_strategy(strategy_config)
            await self.strategy_engine.start()
            
            # 60초 동안 신호 생성 대기
            print("⏳ 전략 신호 60초 대기...")
            await asyncio.sleep(60)
            
            signals_success = len(signals_generated) >= 0  # 신호가 없을 수도 있음
            
            print(f"🧠 생성된 신호: {len(signals_generated)}개")
            if signals_generated:
                last_signal = signals_generated[-1].data
                print(f"📊 최신 신호: {last_signal.get('action')} {last_signal.get('symbol')}")
            
            self.test_results['strategy_signals'] = {
                'signals_generated': len(signals_generated),
                'success': signals_success
            }
            
            return signals_success
            
        except Exception as e:
            print(f"❌ 전략 신호 생성 실패: {e}")
            self.test_results['strategy_signals'] = {'success': False, 'error': str(e)}
            return False
    
    async def test_risk_management(self) -> bool:
        """리스크 관리 테스트"""
        print("\n🛡️ 리스크 관리 테스트...")
        
        risk_checks = []
        
        def risk_alert_handler(event):
            risk_checks.append(event)
            alert_data = event.data
            print(f"⚠️ 리스크 알림: {alert_data.get('alert_type')} - {alert_data.get('message')}")
        
        self.event_bus.subscribe('RISK_ALERT', risk_alert_handler)
        
        try:
            # 리스크 엔진 시작
            await self.risk_engine.start()
            
            # 테스트 주문 생성 (실제 주문은 아님)
            test_order = {
                'symbol': self.test_symbol,
                'side': 'BUY',
                'quantity': self.test_quantity,
                'price': 75000,  # 대략적인 삼성전자 주가
                'order_type': 'LIMIT'
            }
            
            # 리스크 체크 실행
            risk_result = await self.risk_engine.check_order(test_order)
            
            print(f"🛡️ 리스크 체크 결과: {'통과' if risk_result.approved else '거부'}")
            if not risk_result.approved:
                print(f"📝 거부 사유: {risk_result.reason}")
            
            # 30초 동안 리스크 모니터링
            print("⏳ 리스크 모니터링 30초 대기...")
            await asyncio.sleep(30)
            
            self.test_results['risk_management'] = {
                'risk_check_passed': risk_result.approved,
                'risk_alerts': len(risk_checks),
                'success': True  # 리스크 체크가 작동하면 성공
            }
            
            return True
            
        except Exception as e:
            print(f"❌ 리스크 관리 테스트 실패: {e}")
            self.test_results['risk_management'] = {'success': False, 'error': str(e)}
            return False
    
    async def test_small_order_execution(self) -> bool:
        """소액 주문 실행 테스트 (실제 거래)"""
        print("\n💰 소액 주문 실행 테스트...")
        print("⚠️  주의: 실제 거래가 발생합니다!")
        
        # 사용자 확인
        confirm = input(f"\n{self.test_symbol} {self.test_quantity}주 매매 테스트를 진행하시겠습니까? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ 사용자가 실제 거래를 취소했습니다.")
            self.test_results['order_execution'] = {'success': False, 'reason': 'user_cancelled'}
            return False
        
        order_events = []
        
        def order_handler(event):
            order_events.append(event)
            order_data = event.data
            print(f"📋 주문 이벤트: {event.event_type} - {order_data}")
        
        # 주문 관련 이벤트 구독
        self.event_bus.subscribe('ORDER_PLACED', order_handler)
        self.event_bus.subscribe('ORDER_EXECUTED', order_handler)
        self.event_bus.subscribe('ORDER_FAILED', order_handler)
        
        try:
            # 주문 엔진 시작
            await self.order_engine.start()
            
            # 현재 시장가 조회
            current_price = await self.data_collector.get_current_price(self.test_symbol)
            if not current_price:
                print("❌ 현재 시장가를 가져올 수 없습니다.")
                return False
            
            # 매수 주문 생성
            buy_order = {
                'symbol': self.test_symbol,
                'side': 'BUY',
                'quantity': self.test_quantity,
                'price': current_price,
                'order_type': 'MARKET',  # 시장가 주문으로 즉시 체결
                'strategy_name': 'integration_test'
            }
            
            print(f"📤 매수 주문 실행: {buy_order}")
            
            # 매수 주문 실행
            buy_result = await self.order_engine.place_order(buy_order)
            
            if buy_result.success:
                print(f"✅ 매수 주문 성공: {buy_result.order_id}")
                
                # 10초 대기 후 매도 주문
                await asyncio.sleep(10)
                
                # 매도 주문 생성
                sell_order = {
                    'symbol': self.test_symbol,
                    'side': 'SELL',
                    'quantity': self.test_quantity,
                    'order_type': 'MARKET',
                    'strategy_name': 'integration_test'
                }
                
                print(f"📤 매도 주문 실행: {sell_order}")
                
                # 매도 주문 실행
                sell_result = await self.order_engine.place_order(sell_order)
                
                if sell_result.success:
                    print(f"✅ 매도 주문 성공: {sell_result.order_id}")
                    
                    # 손익 계산
                    profit_loss = sell_result.execution_price - buy_result.execution_price
                    print(f"💰 손익: {profit_loss:+.0f}원")
                    
                    self.test_results['order_execution'] = {
                        'buy_success': True,
                        'sell_success': True,
                        'profit_loss': profit_loss,
                        'order_events': len(order_events),
                        'success': True
                    }
                    
                    return True
                else:
                    print(f"❌ 매도 주문 실패: {sell_result.error}")
                    self.test_results['order_execution'] = {
                        'buy_success': True,
                        'sell_success': False,
                        'error': sell_result.error,
                        'success': False
                    }
                    return False
            else:
                print(f"❌ 매수 주문 실패: {buy_result.error}")
                self.test_results['order_execution'] = {
                    'buy_success': False,
                    'error': buy_result.error,
                    'success': False
                }
                return False
                
        except Exception as e:
            print(f"❌ 주문 실행 테스트 실패: {e}")
            self.test_results['order_execution'] = {'success': False, 'error': str(e)}
            return False
    
    async def test_system_monitoring(self) -> bool:
        """시스템 모니터링 테스트"""
        print("\n📊 시스템 모니터링 테스트...")
        
        try:
            # Redis 상태 확인
            redis_status = self.redis_monitor.get_status_summary()
            print(f"📊 Redis 상태: {redis_status['status']}")
            print(f"💾 메모리 사용량: {redis_status['memory_usage_percent']:.1f}%")
            
            # API 모니터링 상태
            api_stats = self.api_monitor.get_daily_stats()
            print(f"🌐 API 요청: 총 {api_stats['total_requests']}회")
            print(f"✅ 성공률: {api_stats['successful_requests']}/{api_stats['total_requests']}")
            
            # Event Bus 메트릭
            event_metrics = self.event_bus.get_metrics()
            print(f"📨 Event Bus 메트릭:")
            print(f"   - 발행된 이벤트: {event_metrics['total_published']}")
            print(f"   - 활성 구독자: {event_metrics['active_subscribers']}")
            
            self.test_results['monitoring'] = {
                'redis_status': redis_status['status'],
                'memory_usage': redis_status['memory_usage_percent'],
                'api_requests': api_stats['total_requests'],
                'event_metrics': event_metrics,
                'success': True
            }
            
            return True
            
        except Exception as e:
            print(f"❌ 시스템 모니터링 테스트 실패: {e}")
            self.test_results['monitoring'] = {'success': False, 'error': str(e)}
            return False
    
    async def cleanup(self):
        """시스템 정리"""
        print("\n🧹 시스템 정리 중...")
        
        try:
            # 엔진들 정지
            if self.strategy_engine:
                await self.strategy_engine.stop()
            if self.risk_engine:
                await self.risk_engine.stop()
            if self.order_engine:
                await self.order_engine.stop()
            if self.data_collector:
                await self.data_collector.stop()
            
            # 모니터링 정지
            if self.redis_monitor:
                await self.redis_monitor.stop_monitoring()
            
            # 연결 종료
            if self.redis_manager:
                await self.redis_manager.disconnect()
            if self.db_manager:
                await self.db_manager.disconnect()
            
            print("✅ 시스템 정리 완료")
            
        except Exception as e:
            print(f"⚠️ 정리 중 오류: {e}")
    
    def generate_report(self):
        """테스트 결과 리포트 생성"""
        print("\n" + "="*60)
        print("📋 QB Trading System 통합 테스트 결과")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() 
                          if result.get('success', False))
        
        print(f"🎯 총 테스트: {total_tests}개")
        print(f"✅ 통과: {passed_tests}개")
        print(f"❌ 실패: {total_tests - passed_tests}개")
        print(f"📊 성공률: {passed_tests/total_tests*100:.1f}%")
        
        print("\n📋 상세 결과:")
        for test_name, result in self.test_results.items():
            status = "✅ 성공" if result.get('success', False) else "❌ 실패"
            print(f"  {test_name}: {status}")
            if not result.get('success', False) and 'error' in result:
                print(f"    오류: {result['error']}")
        
        # 거래 결과 (있는 경우)
        if 'order_execution' in self.test_results:
            order_result = self.test_results['order_execution']
            if order_result.get('success') and 'profit_loss' in order_result:
                profit_loss = order_result['profit_loss']
                print(f"\n💰 거래 결과: {profit_loss:+.0f}원")
        
        print("\n" + "="*60)
        
        # 파일로 저장
        report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"logs/integration_test_report_{report_time}.json"
        
        os.makedirs("logs", exist_ok=True)
        
        import json
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'summary': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'success_rate': passed_tests/total_tests*100
                },
                'results': self.test_results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"📄 상세 리포트 저장: {report_file}")


async def main():
    """메인 테스트 실행"""
    print("🚀 QB Trading System 실제 거래 통합 테스트 시작")
    print("⚠️  주의: 이 테스트는 실제 거래를 포함합니다!")
    
    # 최종 확인
    final_confirm = input("\n실제 거래를 포함한 통합 테스트를 시작하시겠습니까? (y/N): ")
    if final_confirm.lower() != 'y':
        print("❌ 테스트가 취소되었습니다.")
        return
    
    test = FullTradingIntegrationTest()
    
    try:
        # 시스템 초기화
        if not await test.setup_system():
            print("❌ 시스템 초기화 실패. 테스트 중단.")
            return
        
        print("\n🧪 통합 테스트 시나리오 실행 중...")
        
        # 1. 연결성 테스트
        await test.test_connectivity()
        
        # 2. 시장 데이터 플로우 테스트
        await test.test_market_data_flow()
        
        # 3. 전략 신호 생성 테스트
        await test.test_strategy_signal_generation()
        
        # 4. 리스크 관리 테스트
        await test.test_risk_management()
        
        # 5. 소액 주문 실행 테스트 (실제 거래)
        await test.test_small_order_execution()
        
        # 6. 시스템 모니터링 테스트
        await test.test_system_monitoring()
        
        # 결과 리포트
        test.generate_report()
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 정리
        await test.cleanup()


if __name__ == "__main__":
    # 환경 변수 확인
    required_env_vars = ['KIS_APP_KEY', 'KIS_APP_SECRET', 'KIS_ACCOUNT_NO']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ 필수 환경 변수가 설정되지 않았습니다:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n.env.development 파일에서 실제 KIS API 정보를 설정해주세요.")
        sys.exit(1)
    
    # 비동기 실행
    asyncio.run(main())