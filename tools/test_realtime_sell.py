#!/usr/bin/env python3
"""
실시간 매도 시스템 테스트 도구
===========================

수정된 전략 엔진의 실시간 매도 기능을 테스트합니다.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

from qb.utils.redis_manager import RedisManager
from qb.engines.event_bus.core import EnhancedEventBus
from qb.engines.strategy_engine.engine import StrategyEngine
from tools.event_simulator import EventSimulator

async def test_realtime_sell():
    """실시간 매도 테스트"""
    
    print("🧪 실시간 매도 시스템 테스트")
    print("=" * 50)
    
    # 1. Redis & Event Bus 초기화
    redis_manager = RedisManager()
    event_bus = EnhancedEventBus(redis_manager=redis_manager)
    
    # 🔧 Event Bus 시작 (중요: 이벤트 수신을 위해 필수!)
    event_bus.start()
    
    # 2. 전략 엔진 시작
    strategy_engine = StrategyEngine(redis_manager=redis_manager, event_bus=event_bus)
    await strategy_engine.start()
    
    # 3. Moving Average 전략 활성화
    strategy_config = {
        'ma_period': 5,
        'confidence_threshold': 0.7,
        'enable_forced_sell': True,
        'min_volume_threshold': 30_000_000_000
    }
    await strategy_engine.activate_strategy('MovingAverage1M5MStrategy', strategy_config, ['005930'])
    
    print("🚀 실시간 매도 테스트 시작 (총 90초)")
    print("🧠 전략엔진: Moving Average 1M5M 활성화")
    print("📋 테스트 시나리오:")
    print("   1단계 (30초): 매수 편향으로 포지션 생성")
    print("   2단계 (60초): 매도 편향으로 실시간 매도 테스트")
    print("⚠️  실시간 매도 신호 확인을 위해 로그를 주시하세요!")
    print("🔍 [REALTIME SELL] 또는 🚨 거래신호 메시지를 찾아보세요!")
    print("=" * 50)
    
    try:
        # 5-1. 1단계: 매수 편향 시뮬레이터 (포지션 생성)
        print("\n📈 1단계: 매수 포지션 생성 중... (30초)")
        buy_simulator = EventSimulator(
            symbols=["005930"],
            interval_seconds=5,         # 5초마다 시장데이터
            orderbook_interval=2,       # 2초마다 호가 업데이트
            buy_bias=0.8,               # 매수 80% (높음)
            sell_bias=0.1               # 매도 10%
        )
        
        buy_task = asyncio.create_task(buy_simulator.start(duration_seconds=30))
        await buy_task
        
        print("\n🔄 포지션 확인 중...")
        await asyncio.sleep(2)
        
        # 포지션 상태 확인
        positions = {}
        for strategy_name, strategy in strategy_engine.active_strategies.items():
            if hasattr(strategy, 'current_position'):
                positions.update(strategy.current_position)
        
        print(f"📊 현재 포지션: {len(positions)}개")
        for symbol, pos in positions.items():
            print(f"   {symbol}: ₩{pos.get('entry_price', 0):,.0f}")
        
        if positions:
            # 5-2. 2단계: 매도 편향 시뮬레이터 (실시간 매도 테스트)
            print("\n📉 2단계: 실시간 매도 테스트... (60초)")
            sell_simulator = EventSimulator(
                symbols=["005930"],
                interval_seconds=8,         # 8초마다 시장데이터
                orderbook_interval=2,       # 2초마다 호가 업데이트
                buy_bias=0.1,              # 매수 10%
                sell_bias=0.8              # 매도 80% (높음)
            )
            
            sell_task = asyncio.create_task(sell_simulator.start(duration_seconds=60))
            await sell_task
        else:
            print("⚠️ 포지션이 생성되지 않았습니다. 매도 테스트를 건너뜁니다.")
        
    finally:
        # 6. 전략 엔진 정리
        await strategy_engine.stop()
        
        # 7. Event Bus 정리
        event_bus.stop()
    
    print("\n✅ 실시간 매도 테스트 완료")
    print("📋 결과:")
    print("- 기존: 30초마다 매도 신호 체크")
    print("- 개선: 3초마다 매도 신호 체크 (호가 변동과 동기화)")
    print("- 로그에서 [REALTIME SELL] 메시지가 나타났다면 성공!")

if __name__ == "__main__":
    try:
        asyncio.run(test_realtime_sell())
    except KeyboardInterrupt:
        print("\n⚠️ 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 테스트 오류: {e}")
        import traceback
        traceback.print_exc()