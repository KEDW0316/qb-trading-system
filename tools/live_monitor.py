#!/usr/bin/env python3
"""
QB Trading System - 실시간 모니터링 도구
=====================================

시뮬레이터와 거래 시스템의 상태를 실시간으로 모니터링하는 도구입니다.
이벤트 수신, 매매 신호 생성, 주문 상태 등을 한눈에 확인할 수 있습니다.

사용법:
    python tools/live_monitor.py
    python tools/live_monitor.py --symbol 005930 --refresh-rate 2
"""

import asyncio
import argparse
import sys
import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

from qb.utils.redis_manager import RedisManager
from qb.engines.event_bus.core import EnhancedEventBus
from qb.utils.event_bus import EventType, Event

# 로깅 설정 (INFO 레벨로 설정하되 출력 최소화)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class LiveMonitor:
    """실시간 모니터링 도구"""
    
    def __init__(self, symbol: str = "005930", refresh_rate: int = 3):
        self.symbol = symbol
        self.refresh_rate = refresh_rate
        
        # Redis & Event Bus 초기화
        self.redis_manager = RedisManager()
        self.event_bus = EnhancedEventBus(redis_manager=self.redis_manager)
        
        # 모니터링 데이터
        self.last_market_data = None
        self.last_indicators = None
        self.last_orderbook = None
        self.event_counts = {
            'market_data': 0,
            'signals': 0,
            'orders': 0,
            'events_total': 0
        }
        self.last_event_time = None
        self.start_time = datetime.now()
        
        # 이벤트 구독 설정
        self._setup_event_monitoring()
        
    def _setup_event_monitoring(self):
        """이벤트 모니터링 설정"""
        try:
            # 주요 이벤트들 구독
            self.event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, self._on_market_data_event)
            self.event_bus.subscribe(EventType.TRADING_SIGNAL, self._on_trading_signal_event)
            self.event_bus.subscribe(EventType.ORDER_PLACED, self._on_order_event)
            self.event_bus.subscribe(EventType.ORDER_EXECUTED, self._on_order_event)
            
            # Event Bus 시작
            self.event_bus.start() if hasattr(self.event_bus, 'start') else None
            
        except Exception as e:
            print(f"❌ 이벤트 모니터링 설정 실패: {e}")
    
    def _on_market_data_event(self, event):
        """시장 데이터 이벤트 핸들러"""
        self.event_counts['market_data'] += 1
        self.event_counts['events_total'] += 1
        self.last_event_time = datetime.now()
        
        if hasattr(event, 'data'):
            self.last_market_data = event.data
    
    def _on_trading_signal_event(self, event):
        """거래 신호 이벤트 핸들러"""
        self.event_counts['signals'] += 1
        self.event_counts['events_total'] += 1
        self.last_event_time = datetime.now()
    
    def _on_order_event(self, event):
        """주문 이벤트 핸들러"""
        self.event_counts['orders'] += 1
        self.event_counts['events_total'] += 1
        self.last_event_time = datetime.now()
    
    async def start_monitoring(self):
        """모니터링 시작"""
        print("🔍 QB Trading System - 실시간 모니터링 시작")
        print("=" * 70)
        print(f"📊 대상 종목: {self.symbol}")
        print(f"🔄 새로고침: {self.refresh_rate}초")
        print(f"⚠️  종료하려면 Ctrl+C를 누르세요")
        print("=" * 70)
        
        try:
            while True:
                await self._update_data()
                self._display_dashboard()
                await asyncio.sleep(self.refresh_rate)
                
        except KeyboardInterrupt:
            print("\n\n⚠️ 모니터링이 중단되었습니다.")
            await self._cleanup()
        except Exception as e:
            print(f"\n❌ 모니터링 오류: {e}")
            await self._cleanup()
    
    async def _update_data(self):
        """데이터 업데이트"""
        try:
            # Redis에서 최신 데이터 조회
            self.last_market_data = await asyncio.to_thread(
                self.redis_manager.get_market_data, self.symbol
            )
            
            # 기술 지표 조회
            indicators_data = await asyncio.to_thread(
                self.redis_manager.get_data, f"indicators:{self.symbol}"
            )
            if indicators_data:
                if isinstance(indicators_data, str):
                    self.last_indicators = json.loads(indicators_data)
                else:
                    self.last_indicators = indicators_data
            
            # 호가 데이터 조회
            self.last_orderbook = await asyncio.to_thread(
                self.redis_manager.get_orderbook_data, self.symbol
            )
            
        except Exception as e:
            print(f"❌ 데이터 업데이트 오류: {e}")
    
    def _display_dashboard(self):
        """대시보드 화면 출력"""
        # 화면 클리어 (Unix/Linux/Mac)
        os.system('clear' if os.name == 'posix' else 'cls')
        
        runtime = datetime.now() - self.start_time
        
        print("🔍 QB Trading System - 실시간 모니터링 대시보드")
        print("=" * 70)
        print(f"⏰ 실행 시간: {runtime}")
        print(f"🕒 마지막 업데이트: {datetime.now().strftime('%H:%M:%S')}")
        print(f"📊 종목: {self.symbol}")
        print("=" * 70)
        
        # 이벤트 통계
        print("📡 이벤트 통계")
        print("-" * 30)
        print(f"📈 시장데이터: {self.event_counts['market_data']:,}개")
        print(f"🚨 거래신호: {self.event_counts['signals']:,}개")
        print(f"📋 주문이벤트: {self.event_counts['orders']:,}개")
        print(f"🔢 총 이벤트: {self.event_counts['events_total']:,}개")
        
        if self.last_event_time:
            time_since_last = datetime.now() - self.last_event_time
            print(f"⏱️  마지막 이벤트: {time_since_last.total_seconds():.1f}초 전")
        else:
            print("⏱️  마지막 이벤트: 없음")
        
        print()
        
        # 시장 데이터 상태
        print("💹 시장 데이터 상태")
        print("-" * 30)
        if self.last_market_data:
            try:
                close_price = float(self.last_market_data.get('close', 0))
                volume = int(self.last_market_data.get('volume', 0))
                timestamp = self.last_market_data.get('timestamp', 'N/A')
                
                print(f"💰 현재가: ₩{close_price:,.0f}")
                print(f"📊 거래량: {volume:,}")
                print(f"🕒 시간: {timestamp}")
                print("✅ 상태: 데이터 수신 중")
            except Exception as e:
                print(f"❌ 데이터 파싱 오류: {e}")
        else:
            print("❌ 시장 데이터 없음")
        
        print()
        
        # 기술 지표 상태
        print("📊 기술 지표 상태")
        print("-" * 30)
        if self.last_indicators:
            try:
                sma_5 = self.last_indicators.get('sma_5', 0)
                avg_volume_5d = self.last_indicators.get('avg_volume_5d', 0)
                
                print(f"📈 SMA5: ₩{sma_5:,.0f}")
                print(f"💼 5일 평균 거래대금: {avg_volume_5d/1e9:.1f}B원")
                
                # 매매 신호 예측
                if self.last_market_data:
                    current_price = float(self.last_market_data.get('close', 0))
                    if current_price > sma_5:
                        print("🟢 신호 예측: 매수 조건 충족")
                    elif current_price <= sma_5:
                        print("🔴 신호 예측: 매도 조건 충족")
                    else:
                        print("🟡 신호 예측: 중립")
                
                print("✅ 상태: 지표 데이터 있음")
            except Exception as e:
                print(f"❌ 지표 파싱 오류: {e}")
        else:
            print("❌ 기술 지표 데이터 없음")
        
        print()
        
        # 호가 데이터 상태
        print("📋 호가 데이터 상태")
        print("-" * 30)
        if self.last_orderbook:
            try:
                bid_price = float(self.last_orderbook.get('bid_price', 0))
                ask_price = float(self.last_orderbook.get('ask_price', 0))
                
                print(f"💸 매수호가: ₩{bid_price:,.0f}")
                print(f"💰 매도호가: ₩{ask_price:,.0f}")
                print("✅ 상태: 호가 데이터 있음")
            except Exception as e:
                print(f"❌ 호가 파싱 오류: {e}")
        else:
            print("❌ 호가 데이터 없음")
        
        print()
        
        # 시스템 상태 진단
        print("🔧 시스템 진단")
        print("-" * 30)
        
        # Redis 연결 상태
        redis_ok = self.redis_manager.ping()
        print(f"💾 Redis: {'✅ 연결됨' if redis_ok else '❌ 연결 실패'}")
        
        # 데이터 흐름 진단
        has_market_data = bool(self.last_market_data)
        has_indicators = bool(self.last_indicators)
        has_orderbook = bool(self.last_orderbook)
        
        print(f"📊 시장데이터: {'✅ 정상' if has_market_data else '❌ 없음'}")
        print(f"📈 기술지표: {'✅ 정상' if has_indicators else '❌ 없음'}")
        print(f"📋 호가데이터: {'✅ 정상' if has_orderbook else '❌ 없음'}")
        
        # 이벤트 수신 상태
        recent_events = self.last_event_time and (datetime.now() - self.last_event_time).total_seconds() < 60
        print(f"📡 이벤트 수신: {'✅ 정상' if recent_events else '❌ 1분 이상 없음'}")
        
        # 문제 진단 및 해결 방안
        print()
        print("🚨 문제 진단")
        print("-" * 30)
        
        if not redis_ok:
            print("❌ Redis 서버가 실행되지 않았습니다")
            print("   해결방안: redis-server 명령으로 Redis 시작")
        elif not has_market_data and not has_indicators:
            print("❌ 이벤트 시뮬레이터가 동작하지 않는 것 같습니다")
            print("   해결방안: event_simulator.py 실행 확인")
        elif not recent_events:
            print("❌ 최근 1분간 이벤트 수신이 없습니다")
            print("   해결방안: 시뮬레이터 재시작 또는 설정 확인")
        elif self.event_counts['market_data'] > 0 and self.event_counts['signals'] == 0:
            print("⚠️ 시장데이터는 수신되지만 거래신호가 생성되지 않습니다")
            print("   원인: 매매 조건 불충족 또는 전략 엔진 문제")
        elif self.event_counts['signals'] > 0 and self.event_counts['orders'] == 0:
            print("⚠️ 거래신호는 생성되지만 주문이 실행되지 않습니다")
            print("   원인: 주문 엔진 문제 또는 리스크 관리")
        else:
            print("✅ 시스템이 정상적으로 동작하는 것 같습니다")
        
        print()
        print("=" * 70)
        print("🔄 다음 업데이트까지 기다리는 중... (Ctrl+C로 종료)")
    
    async def _cleanup(self):
        """정리 작업"""
        try:
            if hasattr(self.event_bus, 'stop'):
                self.event_bus.stop()
        except Exception as e:
            print(f"정리 작업 오류: {e}")

async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='QB Trading System - 실시간 모니터링')
    parser.add_argument('--symbol', default='005930', help='모니터링할 종목 코드 (기본: 005930)')
    parser.add_argument('--refresh-rate', type=int, default=3, help='새로고침 간격 (초, 기본: 3)')
    
    args = parser.parse_args()
    
    # 모니터링 시작
    monitor = LiveMonitor(symbol=args.symbol, refresh_rate=args.refresh_rate)
    await monitor.start_monitoring()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ 모니터링이 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()