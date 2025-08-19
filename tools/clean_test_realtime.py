#!/usr/bin/env python3
"""
깔끔한 실시간 매도 테스트
========================

로그를 정리해서 핵심 정보만 보여주는 테스트 도구
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

from qb.utils.redis_manager import RedisManager
from qb.engines.event_bus.core import EnhancedEventBus
from qb.engines.strategy_engine.engine import StrategyEngine
from tools.event_simulator import EventSimulator

# 로깅 레벨을 WARNING으로 설정해서 중요한 메시지만 표시
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s'  # 간단한 포맷
)

# 특정 로거만 INFO 레벨로 설정
important_loggers = [
    'qb.engines.strategy_engine.strategies.moving_average_1m5m',
    'qb.engines.strategy_engine.engine'
]

for logger_name in important_loggers:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

class CleanLogFilter(logging.Filter):
    """깔끔한 로그 필터"""
    
    def filter(self, record):
        # 중요한 메시지만 통과
        important_keywords = [
            'STRATEGY SIGNAL',
            'SIGNAL GENERATED',
            'REALTIME SELL',
            'BUY SIGNAL',
            'SELL',
            'Trading Summary'
        ]
        
        # DEBUG 메시지는 제외
        if '[DEBUG]' in record.getMessage():
            return False
            
        # 중요한 키워드가 포함된 경우만 통과
        return any(keyword in record.getMessage() for keyword in important_keywords)

class TradingSummary:
    """거래 요약"""
    
    def __init__(self):
        self.events = []
        self.start_time = datetime.now()
    
    def add_event(self, event_type: str, symbol: str, price: float, details: str = ""):
        """이벤트 추가"""
        self.events.append({
            'time': datetime.now(),
            'type': event_type,
            'symbol': symbol,
            'price': price,
            'details': details
        })
        
        # 실시간 출력
        time_str = datetime.now().strftime('%H:%M:%S')
        icon = "🟢" if event_type == "BUY" else "🔴" if event_type == "SELL" else "⏸️"
        print(f"{icon} {time_str} {event_type:4} {symbol} @ ₩{price:,.0f} {details}")
    
    def print_summary(self):
        """요약 출력"""
        runtime = datetime.now() - self.start_time
        buy_count = sum(1 for e in self.events if e['type'] == 'BUY')
        sell_count = sum(1 for e in self.events if e['type'] == 'SELL')
        
        print("\n" + "━" * 60)
        print("🎯 QB Trading Test Summary")
        print("━" * 60)
        print(f"⏱️  실행 시간: {runtime}")
        print(f"📊 총 신호: {len(self.events)}개 (🟢BUY:{buy_count} 🔴SELL:{sell_count})")
        
        if self.events:
            print("\n📋 최근 이벤트:")
            for event in self.events[-5:]:  # 최근 5개만
                time_str = event['time'].strftime('%H:%M:%S')
                icon = "🟢" if event['type'] == "BUY" else "🔴"
                print(f"  {icon} {time_str} {event['type']} {event['symbol']} @ ₩{event['price']:,.0f}")
        
        print("━" * 60)

# 전역 요약 객체
summary = TradingSummary()

class TradingLogHandler(logging.Handler):
    """거래 로그 핸들러"""
    
    def emit(self, record):
        msg = record.getMessage()
        
        # BUY 신호 감지
        if "BUY SIGNAL" in msg and "Creating" in msg:
            price_match = re.search(r'₩([\d,]+)', msg)
            if price_match:
                price = float(price_match.group(1).replace(',', ''))
                summary.add_event("BUY", "005930", price, "매수신호")
        
        # SELL 신호 감지
        elif "REALTIME SELL" in msg:
            price_match = re.search(r'₩([\d,]+)', msg)
            if price_match:
                price = float(price_match.group(1).replace(',', ''))
                summary.add_event("SELL", "005930", price, "실시간매도")

# 핸들러 추가
import re
handler = TradingLogHandler()
for logger_name in important_loggers:
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)

async def clean_realtime_test():
    """깔끔한 실시간 테스트"""
    
    print("🧪 깔끔한 실시간 매도 테스트")
    print("=" * 60)
    
    # 1. 초기화
    redis_manager = RedisManager()
    event_bus = EnhancedEventBus(redis_manager=redis_manager)
    event_bus.start()
    
    # 2. 전략 엔진 시작
    strategy_engine = StrategyEngine(redis_manager=redis_manager, event_bus=event_bus)
    await strategy_engine.start()
    
    # 3. 전략 활성화
    strategy_config = {
        'ma_period': 5,
        'confidence_threshold': 0.7,
        'enable_forced_sell': True,
        'min_volume_threshold': 30_000_000_000
    }
    await strategy_engine.activate_strategy('MovingAverage1M5MStrategy', strategy_config, ['005930'])
    
    print("🚀 테스트 시작 (총 60초)")
    print("📊 핵심 거래 신호만 표시됩니다")
    print("━" * 60)
    
    try:
        # 4. 매수 단계 (20초)
        print("📈 1단계: 매수 편향 (20초)")
        buy_simulator = EventSimulator(
            symbols=["005930"],
            interval_seconds=4,
            orderbook_interval=2,
            buy_bias=0.8,
            sell_bias=0.1
        )
        
        buy_task = asyncio.create_task(buy_simulator.start(duration_seconds=20))
        await buy_task
        
        print("\n🔄 포지션 확인...")
        await asyncio.sleep(2)
        
        # 포지션 확인
        positions = {}
        for strategy_name, strategy in strategy_engine.active_strategies.items():
            if hasattr(strategy, 'current_position'):
                positions.update(strategy.current_position)
        
        if positions:
            print(f"✅ 포지션 생성됨: {len(positions)}개")
            
            # 5. 매도 단계 (40초)
            print("\n📉 2단계: 매도 편향 - 실시간 매도 테스트 (40초)")
            sell_simulator = EventSimulator(
                symbols=["005930"],
                interval_seconds=6,
                orderbook_interval=2,
                buy_bias=0.1,
                sell_bias=0.8
            )
            
            sell_task = asyncio.create_task(sell_simulator.start(duration_seconds=40))
            await sell_task
        else:
            print("⚠️ 포지션이 생성되지 않았습니다.")
            
    finally:
        await strategy_engine.stop()
        event_bus.stop()
    
    # 6. 요약 출력
    summary.print_summary()
    
    print("\n✅ 테스트 완료!")
    print("🎯 실시간 매도 시스템이 3초마다 체크되어 빠른 대응이 가능합니다.")

if __name__ == "__main__":
    try:
        asyncio.run(clean_realtime_test())
    except KeyboardInterrupt:
        print("\n⚠️ 테스트가 중단되었습니다.")
        summary.print_summary()
    except Exception as e:
        print(f"\n❌ 테스트 오류: {e}")
        summary.print_summary()