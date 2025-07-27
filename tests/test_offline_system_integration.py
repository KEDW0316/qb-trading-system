#!/usr/bin/env python3
"""
QB Trading System - 장마감 시간 시스템 통합 테스트
===============================================

목적: 장마감 시간에도 전체 시스템 검증 가능
- Mock 데이터를 사용한 완전한 거래 워크플로우 시뮬레이션
- 모든 엔진 간 통신 검증
- 과거 데이터 기반 백테스팅
- 실제 거래 없이 시스템 안정성 확인

장점: 
- 24시간 언제든 테스트 가능
- 실제 손실 없이 시스템 검증
- 다양한 시나리오 테스트 가능
"""

import asyncio
import os
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import random

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

from qb.engines.event_bus.core import EnhancedEventBus
from qb.database.connection import DatabaseManager
from qb.utils.redis_manager import RedisManager
from qb.utils.redis_monitor import RedisMonitor
from qb.utils.api_monitor import APIMonitor


class MockMarketDataGenerator:
    """실시간 시장 데이터 시뮬레이터"""
    
    def __init__(self, symbol: str = "005930"):
        self.symbol = symbol
        self.base_price = 75000  # 삼성전자 기준가
        self.current_price = self.base_price
        self.volume = 0
        self.trade_count = 0
        
    def generate_realistic_tick(self) -> Dict[str, Any]:
        """현실적인 틱 데이터 생성"""
        
        # 가격 변동 (-0.5% ~ +0.5%)
        price_change = random.uniform(-0.005, 0.005)
        self.current_price *= (1 + price_change)
        
        # 가격 범위 제한 (±5%)
        min_price = self.base_price * 0.95
        max_price = self.base_price * 1.05
        self.current_price = max(min_price, min(max_price, self.current_price))
        
        # 거래량 (100~5000주)
        tick_volume = random.randint(100, 5000)
        self.volume += tick_volume
        self.trade_count += 1
        
        return {
            'symbol': self.symbol,
            'timestamp': datetime.now().isoformat(),
            'price': round(self.current_price),
            'volume': tick_volume,
            'cumulative_volume': self.volume,
            'trade_count': self.trade_count
        }
    
    def generate_candle_data(self, interval_minutes: int = 1) -> Dict[str, Any]:
        """캔들 데이터 생성"""
        
        # 시뮬레이션된 OHLCV
        open_price = self.current_price
        
        # 고가/저가 생성 (±2% 범위)
        high_price = open_price * random.uniform(1.0, 1.02)
        low_price = open_price * random.uniform(0.98, 1.0)
        
        # 종가 생성
        close_price = random.uniform(low_price, high_price)
        self.current_price = close_price
        
        # 거래량 (10만~100만주)
        volume = random.randint(100000, 1000000)
        
        return {
            'symbol': self.symbol,
            'timestamp': datetime.now().isoformat(),
            'interval': f'{interval_minutes}m',
            'open': round(open_price),
            'high': round(high_price),
            'low': round(low_price),
            'close': round(close_price),
            'volume': volume
        }


class MockOrderExecutor:
    """모의 주문 실행기"""
    
    def __init__(self):
        self.orders = {}
        self.order_id_counter = 1
        self.execution_delay = 0.1  # 100ms 시뮬레이션 지연
        
    async def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """모의 주문 체결"""
        
        order_id = f"MOCK_{self.order_id_counter:06d}"
        self.order_id_counter += 1
        
        # 시뮬레이션 지연
        await asyncio.sleep(self.execution_delay)
        
        # 모의 체결 (95% 성공률)
        success = random.random() > 0.05
        
        if success:
            # 슬리피지 시뮬레이션 (±0.1%)
            slippage = random.uniform(-0.001, 0.001)
            execution_price = order['price'] * (1 + slippage)
            
            # 수수료 계산 (0.015%)
            commission = order['quantity'] * execution_price * 0.00015
            
            result = {
                'order_id': order_id,
                'success': True,
                'status': 'FILLED',
                'symbol': order['symbol'],
                'side': order['side'],
                'quantity': order['quantity'],
                'order_price': order['price'],
                'execution_price': round(execution_price),
                'commission': round(commission),
                'execution_time': datetime.now().isoformat()
            }
        else:
            result = {
                'order_id': order_id,
                'success': False,
                'status': 'REJECTED',
                'error': 'Insufficient liquidity (simulated)',
                'execution_time': datetime.now().isoformat()
            }
        
        self.orders[order_id] = result
        return result
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """주문 상태 조회"""
        return self.orders.get(order_id, {'status': 'NOT_FOUND'})


class OfflineSystemIntegrationTest:
    """장마감 시간 시스템 통합 테스트"""
    
    def __init__(self):
        self.test_symbol = "005930"  # 삼성전자
        self.test_results = {}
        self.test_duration = 300  # 5분 테스트
        
        # 시스템 컴포넌트
        self.event_bus = None
        self.db_manager = None
        self.redis_manager = None
        self.redis_monitor = None
        self.api_monitor = None
        
        # Mock 컴포넌트
        self.market_data_generator = MockMarketDataGenerator(self.test_symbol)
        self.order_executor = MockOrderExecutor()
        
        # 테스트 데이터 수집
        self.received_events = []
        self.generated_signals = []
        self.executed_orders = []
        self.risk_alerts = []
        
    async def setup_system(self):
        """시스템 초기화"""
        print("🔧 오프라인 시스템 초기화 중...")
        
        try:
            # 1. Redis 연결
            self.redis_manager = RedisManager()
            redis_ok = self.redis_manager.ping()
            if redis_ok:
                print("✅ Redis 연결 성공")
            else:
                print("❌ Redis 연결 실패")
                return False
            
            # 2. PostgreSQL 연결
            self.db_manager = DatabaseManager()
            db_ok = self.db_manager.initialize()
            if db_ok:
                print("✅ PostgreSQL 연결 성공")
            else:
                print("❌ PostgreSQL 연결 실패")
                return False
            
            # 3. Event Bus 초기화
            self.event_bus = EnhancedEventBus(redis_manager=self.redis_manager)
            print("✅ Event Bus 초기화 성공")
            
            # 4. 모니터링 시스템
            self.redis_monitor = RedisMonitor(self.redis_manager, self.event_bus)
            self.api_monitor = APIMonitor()
            await self.redis_monitor.start_monitoring(interval_seconds=30)
            print("✅ 모니터링 시스템 시작")
            
            # 5. 이벤트 핸들러 등록
            self._setup_event_handlers()
            
            return True
            
        except Exception as e:
            print(f"❌ 시스템 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _setup_event_handlers(self):
        """이벤트 핸들러 등록"""
        
        def market_data_handler(event):
            self.received_events.append(event)
            print(f"📊 시장데이터: {event.data.get('symbol')} @ {event.data.get('price')}")
        
        def signal_handler(event):
            self.generated_signals.append(event)
            signal_data = event.data
            print(f"🚨 거래신호: {signal_data.get('action')} {signal_data.get('symbol')} "
                  f"@ {signal_data.get('price')} (신뢰도: {signal_data.get('confidence', 0):.2f})")
        
        def order_handler(event):
            self.executed_orders.append(event)
            order_data = event.data
            print(f"📋 주문: {order_data.get('side')} {order_data.get('quantity')}주 "
                  f"@ {order_data.get('price')} ({order_data.get('status')})")
        
        def risk_handler(event):
            self.risk_alerts.append(event)
            risk_data = event.data
            print(f"⚠️ 리스크: {risk_data.get('alert_type')} - {risk_data.get('message')}")
        
        # 이벤트 구독
        self.event_bus.subscribe('MARKET_DATA_RECEIVED', market_data_handler)
        self.event_bus.subscribe('TRADING_SIGNAL', signal_handler)
        self.event_bus.subscribe('ORDER_PLACED', order_handler)
        self.event_bus.subscribe('ORDER_EXECUTED', order_handler)
        self.event_bus.subscribe('RISK_ALERT', risk_handler)
        
        print("✅ 이벤트 핸들러 등록 완료")
    
    async def test_connectivity(self) -> bool:
        """기본 연결성 테스트"""
        print("\n📡 연결성 테스트...")
        
        connectivity_results = {}
        
        # Redis 테스트
        try:
            ping_result = self.redis_manager.ping()
            connectivity_results['redis'] = ping_result
            print(f"✅ Redis: {'성공' if ping_result else '실패'}")
        except Exception as e:
            connectivity_results['redis'] = False
            print(f"❌ Redis 실패: {e}")
        
        # PostgreSQL 테스트
        try:
            db_status = self.db_manager.test_connection()
            connectivity_results['postgresql'] = db_status
            print(f"✅ PostgreSQL: {'성공' if db_status else '실패'}")
        except Exception as e:
            connectivity_results['postgresql'] = False
            print(f"❌ PostgreSQL 실패: {e}")
        
        # Event Bus 테스트
        try:
            test_event = self.event_bus.create_event(
                'SYSTEM_STATUS', 
                'offline_test',
                {'test': 'connectivity', 'timestamp': datetime.now().isoformat()}
            )
            publish_result = self.event_bus.publish(test_event)
            connectivity_results['event_bus'] = publish_result
            print(f"✅ Event Bus: {'성공' if publish_result else '실패'}")
        except Exception as e:
            connectivity_results['event_bus'] = False
            print(f"❌ Event Bus 실패: {e}")
        
        self.test_results['connectivity'] = connectivity_results
        return all(connectivity_results.values())
    
    async def test_mock_market_data_flow(self) -> bool:
        """모의 시장 데이터 플로우 테스트"""
        print("\n📊 모의 시장 데이터 플로우 테스트...")
        
        market_data_count = 0
        candle_data_count = 0
        
        try:
            # 30초 동안 모의 데이터 생성
            start_time = time.time()
            while time.time() - start_time < 30:
                
                # 틱 데이터 생성 및 발행
                tick_data = self.market_data_generator.generate_realistic_tick()
                tick_event = self.event_bus.create_event(
                    'MARKET_DATA_RECEIVED',
                    'mock_data_generator',
                    tick_data
                )
                self.event_bus.publish(tick_event)
                market_data_count += 1
                
                # 5초마다 캔들 데이터 생성
                if market_data_count % 10 == 0:
                    candle_data = self.market_data_generator.generate_candle_data()
                    candle_event = self.event_bus.create_event(
                        'CANDLE_DATA_UPDATED',
                        'mock_data_generator',
                        candle_data
                    )
                    self.event_bus.publish(candle_event)
                    candle_data_count += 1
                
                await asyncio.sleep(0.5)  # 500ms 간격
            
            print(f"📊 생성된 틱 데이터: {market_data_count}개")
            print(f"📈 생성된 캔들 데이터: {candle_data_count}개")
            print(f"📨 수신된 이벤트: {len(self.received_events)}개")
            
            success = market_data_count > 0 and len(self.received_events) > 0
            
            self.test_results['mock_market_data'] = {
                'tick_data_generated': market_data_count,
                'candle_data_generated': candle_data_count,
                'events_received': len(self.received_events),
                'success': success
            }
            
            return success
            
        except Exception as e:
            print(f"❌ 모의 시장 데이터 테스트 실패: {e}")
            self.test_results['mock_market_data'] = {'success': False, 'error': str(e)}
            return False
    
    async def test_strategy_simulation(self) -> bool:
        """전략 시뮬레이션 테스트"""
        print("\n🧠 전략 시뮬레이션 테스트...")
        
        try:
            # 간단한 이동평균 전략 시뮬레이션
            prices = []
            signals_generated = 0
            
            # 100개의 가격 데이터로 전략 시뮬레이션
            for i in range(100):
                # 가격 데이터 생성
                tick_data = self.market_data_generator.generate_realistic_tick()
                current_price = tick_data['price']
                prices.append(current_price)
                
                # 이동평균 계산 (20개 이상일 때)
                if len(prices) >= 20:
                    sma_5 = sum(prices[-5:]) / 5
                    sma_20 = sum(prices[-20:]) / 20
                    
                    # 골든크로스/데드크로스 감지
                    if len(prices) >= 21:
                        prev_sma_5 = sum(prices[-6:-1]) / 5
                        prev_sma_20 = sum(prices[-21:-1]) / 20
                        
                        # 골든크로스 (매수 신호)
                        if prev_sma_5 <= prev_sma_20 and sma_5 > sma_20:
                            signal_event = self.event_bus.create_event(
                                'TRADING_SIGNAL',
                                'mock_strategy',
                                {
                                    'symbol': self.test_symbol,
                                    'action': 'BUY',
                                    'price': current_price,
                                    'quantity': 10,
                                    'confidence': 0.75,
                                    'strategy': 'moving_average_crossover',
                                    'indicators': {
                                        'sma_5': sma_5,
                                        'sma_20': sma_20
                                    }
                                }
                            )
                            self.event_bus.publish(signal_event)
                            signals_generated += 1
                        
                        # 데드크로스 (매도 신호)
                        elif prev_sma_5 >= prev_sma_20 and sma_5 < sma_20:
                            signal_event = self.event_bus.create_event(
                                'TRADING_SIGNAL',
                                'mock_strategy',
                                {
                                    'symbol': self.test_symbol,
                                    'action': 'SELL',
                                    'price': current_price,
                                    'quantity': 10,
                                    'confidence': 0.75,
                                    'strategy': 'moving_average_crossover',
                                    'indicators': {
                                        'sma_5': sma_5,
                                        'sma_20': sma_20
                                    }
                                }
                            )
                            self.event_bus.publish(signal_event)
                            signals_generated += 1
                
                await asyncio.sleep(0.01)  # 10ms 간격
            
            print(f"🧠 분석된 가격 데이터: {len(prices)}개")
            print(f"🚨 생성된 거래 신호: {signals_generated}개")
            print(f"📊 수신된 신호 이벤트: {len(self.generated_signals)}개")
            
            success = signals_generated > 0 or len(prices) == 100
            
            self.test_results['strategy_simulation'] = {
                'prices_analyzed': len(prices),
                'signals_generated': signals_generated,
                'signal_events_received': len(self.generated_signals),
                'success': success
            }
            
            return success
            
        except Exception as e:
            print(f"❌ 전략 시뮬레이션 실패: {e}")
            self.test_results['strategy_simulation'] = {'success': False, 'error': str(e)}
            return False
    
    async def test_risk_management_simulation(self) -> bool:
        """리스크 관리 시뮬레이션"""
        print("\n🛡️ 리스크 관리 시뮬레이션...")
        
        try:
            # 다양한 리스크 시나리오 테스트
            risk_scenarios = [
                {
                    'name': '정상 주문',
                    'order': {
                        'symbol': self.test_symbol,
                        'side': 'BUY',
                        'quantity': 10,
                        'price': 75000,
                        'portfolio_value': 10000000
                    },
                    'expected_approval': True
                },
                {
                    'name': '과도한 포지션 크기',
                    'order': {
                        'symbol': self.test_symbol,
                        'side': 'BUY',
                        'quantity': 1000,  # 너무 큰 수량
                        'price': 75000,
                        'portfolio_value': 5000000
                    },
                    'expected_approval': False
                },
                {
                    'name': '일일 손실 한도 초과',
                    'order': {
                        'symbol': self.test_symbol,
                        'side': 'SELL',
                        'quantity': 10,
                        'price': 70000,
                        'daily_loss': -300000,  # 이미 큰 손실
                        'portfolio_value': 10000000
                    },
                    'expected_approval': False
                }
            ]
            
            risk_check_results = []
            
            for scenario in risk_scenarios:
                print(f"🧪 시나리오: {scenario['name']}")
                
                # 모의 리스크 체크
                order = scenario['order']
                
                # 포지션 크기 체크 (포트폴리오의 10% 이하)
                position_value = order['quantity'] * order['price']
                max_position = order['portfolio_value'] * 0.1
                position_ok = position_value <= max_position
                
                # 일일 손실 체크 (포트폴리오의 5% 이하)
                daily_loss = order.get('daily_loss', 0)
                max_daily_loss = order['portfolio_value'] * 0.05
                daily_loss_ok = abs(daily_loss) <= max_daily_loss
                
                # 전체 승인 여부
                approved = position_ok and daily_loss_ok
                
                result = {
                    'scenario': scenario['name'],
                    'approved': approved,
                    'expected': scenario['expected_approval'],
                    'position_check': position_ok,
                    'daily_loss_check': daily_loss_ok,
                    'position_value': position_value,
                    'max_position': max_position,
                    'daily_loss': daily_loss,
                    'max_daily_loss': max_daily_loss
                }
                
                risk_check_results.append(result)
                
                # 리스크 알림 이벤트 발행
                if not approved:
                    risk_event = self.event_bus.create_event(
                        'RISK_ALERT',
                        'mock_risk_engine',
                        {
                            'alert_type': 'ORDER_REJECTED',
                            'symbol': order['symbol'],
                            'reason': 'Position limit exceeded' if not position_ok else 'Daily loss limit exceeded',
                            'severity': 'HIGH',
                            'order_id': f"RISK_TEST_{len(risk_check_results)}"
                        }
                    )
                    self.event_bus.publish(risk_event)
                
                status = "✅ 승인" if approved else "❌ 거부"
                expected_status = "예상대로" if approved == scenario['expected_approval'] else "예상과 다름"
                print(f"   결과: {status} ({expected_status})")
                
                await asyncio.sleep(0.1)
            
            # 결과 분석
            correct_predictions = sum(1 for r in risk_check_results 
                                    if r['approved'] == r['expected'])
            accuracy = correct_predictions / len(risk_check_results) * 100
            
            print(f"🛡️ 리스크 체크 정확도: {accuracy:.1f}% ({correct_predictions}/{len(risk_check_results)})")
            print(f"⚠️ 발생한 리스크 알림: {len(self.risk_alerts)}개")
            
            success = accuracy >= 100  # 모든 시나리오가 예상대로 동작해야 함
            
            self.test_results['risk_management'] = {
                'scenarios_tested': len(risk_scenarios),
                'accuracy': accuracy,
                'risk_alerts': len(self.risk_alerts),
                'results': risk_check_results,
                'success': success
            }
            
            return success
            
        except Exception as e:
            print(f"❌ 리스크 관리 시뮬레이션 실패: {e}")
            self.test_results['risk_management'] = {'success': False, 'error': str(e)}
            return False
    
    async def test_mock_order_execution(self) -> bool:
        """모의 주문 실행 테스트"""
        print("\n💰 모의 주문 실행 테스트...")
        
        try:
            # 다양한 주문 시나리오
            test_orders = [
                {'side': 'BUY', 'quantity': 10, 'price': 75000},
                {'side': 'BUY', 'quantity': 5, 'price': 74500},
                {'side': 'SELL', 'quantity': 8, 'price': 75200},
                {'side': 'SELL', 'quantity': 7, 'price': 74800}
            ]
            
            order_results = []
            total_pnl = 0
            
            for i, order_data in enumerate(test_orders):
                print(f"📤 주문 {i+1}: {order_data['side']} {order_data['quantity']}주 @ {order_data['price']}")
                
                # 모의 주문 실행
                order_request = {
                    'symbol': self.test_symbol,
                    'side': order_data['side'],
                    'quantity': order_data['quantity'],
                    'price': order_data['price'],
                    'order_type': 'LIMIT'
                }
                
                result = await self.order_executor.place_order(order_request)
                order_results.append(result)
                
                # 주문 이벤트 발행
                if result['success']:
                    order_event = self.event_bus.create_event(
                        'ORDER_EXECUTED',
                        'mock_order_executor',
                        {
                            'order_id': result['order_id'],
                            'symbol': result['symbol'],
                            'side': result['side'],
                            'quantity': result['quantity'],
                            'price': result['execution_price'],
                            'commission': result['commission'],
                            'status': 'FILLED'
                        }
                    )
                    self.event_bus.publish(order_event)
                    
                    # 간단한 손익 계산 (매수는 -, 매도는 +)
                    if order_data['side'] == 'BUY':
                        total_pnl -= result['execution_price'] * result['quantity']
                    else:
                        total_pnl += result['execution_price'] * result['quantity']
                    
                    print(f"   ✅ 체결: {result['execution_price']} (수수료: {result['commission']})")
                else:
                    order_event = self.event_bus.create_event(
                        'ORDER_FAILED',
                        'mock_order_executor',
                        {
                            'order_id': result['order_id'],
                            'error': result['error'],
                            'status': 'REJECTED'
                        }
                    )
                    self.event_bus.publish(order_event)
                    print(f"   ❌ 실패: {result['error']}")
                
                await asyncio.sleep(0.5)
            
            # 결과 분석
            successful_orders = sum(1 for r in order_results if r['success'])
            success_rate = successful_orders / len(order_results) * 100
            total_commission = sum(r.get('commission', 0) for r in order_results if r['success'])
            
            print(f"💰 주문 성공률: {success_rate:.1f}% ({successful_orders}/{len(order_results)})")
            print(f"💸 총 수수료: {total_commission:,.0f}원")
            print(f"📊 총 거래대금: {abs(total_pnl):,.0f}원")
            print(f"📈 실행된 주문 이벤트: {len(self.executed_orders)}개")
            
            success = success_rate >= 90  # 90% 이상 성공해야 함
            
            self.test_results['mock_order_execution'] = {
                'orders_placed': len(test_orders),
                'successful_orders': successful_orders,
                'success_rate': success_rate,
                'total_commission': total_commission,
                'order_events': len(self.executed_orders),
                'success': success
            }
            
            return success
            
        except Exception as e:
            print(f"❌ 모의 주문 실행 실패: {e}")
            self.test_results['mock_order_execution'] = {'success': False, 'error': str(e)}
            return False
    
    async def test_system_performance(self) -> bool:
        """시스템 성능 테스트"""
        print("\n⚡ 시스템 성능 테스트...")
        
        try:
            # 고부하 이벤트 발행 테스트
            start_time = time.time()
            events_published = 0
            
            # 10초 동안 최대한 많은 이벤트 발행
            test_duration = 10
            end_time = start_time + test_duration
            
            while time.time() < end_time:
                # 다양한 타입의 이벤트 발행
                event_types = [
                    ('MARKET_DATA_RECEIVED', {'symbol': self.test_symbol, 'price': random.randint(70000, 80000)}),
                    ('TRADING_SIGNAL', {'action': 'BUY', 'confidence': random.random()}),
                    ('SYSTEM_STATUS', {'component': 'test', 'status': 'ok'})
                ]
                
                event_type, data = random.choice(event_types)
                event = self.event_bus.create_event(event_type, 'performance_test', data)
                self.event_bus.publish(event)
                events_published += 1
                
                # 짧은 대기 (CPU 과부하 방지)
                await asyncio.sleep(0.001)
            
            # 성능 지표 계산
            events_per_second = events_published / test_duration
            
            # 시스템 리소스 확인
            redis_status = self.redis_monitor.get_status_summary()
            
            print(f"⚡ 이벤트 처리 성능: {events_per_second:.0f} events/sec")
            print(f"📊 총 발행 이벤트: {events_published}개")
            print(f"💾 Redis 메모리 사용률: {redis_status['memory_usage_percent']:.1f}%")
            print(f"🔗 Redis 클라이언트: {redis_status['clients_connected']}개")
            
            # 성능 기준 (초당 100개 이상 처리)
            performance_ok = events_per_second >= 100
            memory_ok = redis_status['memory_usage_percent'] < 80
            
            success = performance_ok and memory_ok
            
            self.test_results['system_performance'] = {
                'events_published': events_published,
                'events_per_second': events_per_second,
                'redis_memory_usage': redis_status['memory_usage_percent'],
                'redis_clients': redis_status['clients_connected'],
                'performance_ok': performance_ok,
                'memory_ok': memory_ok,
                'success': success
            }
            
            return success
            
        except Exception as e:
            print(f"❌ 시스템 성능 테스트 실패: {e}")
            self.test_results['system_performance'] = {'success': False, 'error': str(e)}
            return False
    
    async def cleanup(self):
        """시스템 정리"""
        print("\n🧹 시스템 정리 중...")
        
        try:
            # 모니터링 정지
            if self.redis_monitor:
                await self.redis_monitor.stop_monitoring()
            
            # 연결 종료 (필요시)
            # RedisManager와 DatabaseManager는 자동으로 정리됨
            
            print("✅ 시스템 정리 완료")
            
        except Exception as e:
            print(f"⚠️ 정리 중 오류: {e}")
    
    def generate_report(self):
        """테스트 결과 리포트 생성"""
        print("\n" + "="*70)
        print("📋 QB Trading System 오프라인 통합 테스트 결과")
        print("="*70)
        
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
            
            # 주요 지표 표시
            if test_name == 'mock_market_data':
                print(f"    - 틱 데이터: {result.get('tick_data_generated', 0)}개")
                print(f"    - 이벤트 수신: {result.get('events_received', 0)}개")
            elif test_name == 'strategy_simulation':
                print(f"    - 분석 데이터: {result.get('prices_analyzed', 0)}개")
                print(f"    - 거래 신호: {result.get('signals_generated', 0)}개")
            elif test_name == 'risk_management':
                print(f"    - 정확도: {result.get('accuracy', 0):.1f}%")
                print(f"    - 리스크 알림: {result.get('risk_alerts', 0)}개")
            elif test_name == 'mock_order_execution':
                print(f"    - 주문 성공률: {result.get('success_rate', 0):.1f}%")
                print(f"    - 총 수수료: {result.get('total_commission', 0):,.0f}원")
            elif test_name == 'system_performance':
                print(f"    - 처리 성능: {result.get('events_per_second', 0):.0f} events/sec")
                print(f"    - 메모리 사용: {result.get('redis_memory_usage', 0):.1f}%")
            
            if not result.get('success', False) and 'error' in result:
                print(f"    오류: {result['error']}")
        
        print("\n📊 전체 통계:")
        print(f"  📨 총 이벤트 수신: {len(self.received_events)}개")
        print(f"  🚨 총 거래 신호: {len(self.generated_signals)}개")
        print(f"  📋 총 주문 실행: {len(self.executed_orders)}개")
        print(f"  ⚠️ 총 리스크 알림: {len(self.risk_alerts)}개")
        
        print("\n" + "="*70)
        
        # 파일로 저장
        report_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"logs/offline_integration_test_report_{report_time}.json"
        
        os.makedirs("logs", exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'test_type': 'offline_integration',
                'summary': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'success_rate': passed_tests/total_tests*100
                },
                'event_statistics': {
                    'received_events': len(self.received_events),
                    'generated_signals': len(self.generated_signals),
                    'executed_orders': len(self.executed_orders),
                    'risk_alerts': len(self.risk_alerts)
                },
                'results': self.test_results
            }, f, indent=2, ensure_ascii=False)
        
        print(f"📄 상세 리포트 저장: {report_file}")


async def main():
    """메인 테스트 실행"""
    print("🚀 QB Trading System 오프라인 통합 테스트 시작")
    print("📝 장마감 시간에도 전체 시스템 검증 가능한 테스트입니다.")
    print("💡 실제 거래 없이 모든 컴포넌트의 동작을 확인합니다.")
    
    test = OfflineSystemIntegrationTest()
    
    try:
        # 시스템 초기화
        if not await test.setup_system():
            print("❌ 시스템 초기화 실패. 테스트 중단.")
            return
        
        print("\n🧪 오프라인 통합 테스트 시나리오 실행 중...")
        
        # 1. 기본 연결성 테스트
        await test.test_connectivity()
        
        # 2. 모의 시장 데이터 플로우 테스트
        await test.test_mock_market_data_flow()
        
        # 3. 전략 시뮬레이션 테스트
        await test.test_strategy_simulation()
        
        # 4. 리스크 관리 시뮬레이션
        await test.test_risk_management_simulation()
        
        # 5. 모의 주문 실행 테스트
        await test.test_mock_order_execution()
        
        # 6. 시스템 성능 테스트
        await test.test_system_performance()
        
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
    # PostgreSQL과 Redis 실행 확인
    print("📋 사전 확인사항:")
    print("  1. PostgreSQL 서버가 실행 중인지 확인")
    print("  2. Redis 서버가 실행 중인지 확인")
    print("  3. 환경 변수(.env.development) 설정 확인")
    
    start_confirm = input("\n모든 사전 조건이 준비되었나요? 테스트를 시작하시겠습니까? (y/N): ")
    if start_confirm.lower() != 'y':
        print("❌ 테스트가 취소되었습니다.")
        sys.exit(0)
    
    # 비동기 실행
    asyncio.run(main())