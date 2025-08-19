#!/usr/bin/env python3
"""
QB Trading System - 빠른 디버깅 도구
=================================

시스템 상태를 빠르게 확인하는 원샷 디버깅 도구입니다.

사용법:
    python tools/quick_debug.py
    python tools/quick_debug.py --symbol 005930
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

from qb.utils.redis_manager import RedisManager

def quick_debug(symbol: str = "005930"):
    """빠른 시스템 상태 확인"""
    
    print("🔍 QB Trading System - 빠른 디버깅")
    print("=" * 50)
    print(f"📊 종목: {symbol}")
    print(f"🕒 확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Redis 연결 테스트
    print("\n1️⃣ Redis 연결 테스트")
    print("-" * 20)
    try:
        redis_manager = RedisManager()
        if redis_manager.ping():
            print("✅ Redis 연결 성공")
            
            # Redis 메모리 정보
            memory_info = redis_manager.get_memory_stats()
            if memory_info:
                print(f"💾 메모리 사용량: {memory_info.get('used_memory_human', 'N/A')}")
        else:
            print("❌ Redis 연결 실패")
            print("   해결방안: redis-server 명령으로 Redis 시작")
            return
    except Exception as e:
        print(f"❌ Redis 오류: {e}")
        return
    
    # 시장 데이터 확인
    print("\n2️⃣ 시장 데이터 확인")
    print("-" * 20)
    try:
        market_data = redis_manager.get_market_data(symbol)
        if market_data:
            print("✅ 시장 데이터 있음")
            close_price = market_data.get('close', 'N/A')
            volume = market_data.get('volume', 'N/A')
            timestamp = market_data.get('timestamp', 'N/A')
            print(f"💰 현재가: ₩{close_price}")
            print(f"📊 거래량: {volume}")
            print(f"🕒 시간: {timestamp}")
        else:
            print("❌ 시장 데이터 없음")
            print("   원인: event_simulator.py가 실행되지 않았거나 데이터 생성 중")
    except Exception as e:
        print(f"❌ 시장 데이터 오류: {e}")
    
    # 기술 지표 확인
    print("\n3️⃣ 기술 지표 확인")
    print("-" * 20)
    try:
        indicators_data = redis_manager.get_data(f"indicators:{symbol}")
        if indicators_data:
            print("✅ 기술 지표 있음")
            
            if isinstance(indicators_data, str):
                indicators = json.loads(indicators_data)
            else:
                indicators = indicators_data
            
            sma_5 = indicators.get('sma_5', 'N/A')
            avg_volume_5d = indicators.get('avg_volume_5d', 0)
            
            print(f"📈 SMA5: ₩{sma_5}")
            print(f"💼 5일 평균 거래대금: {avg_volume_5d/1e9:.1f}B원")
            
            # 매매 신호 조건 확인
            if market_data and sma_5 != 'N/A':
                try:
                    current_price = float(market_data.get('close', 0))
                    sma_5_val = float(sma_5)
                    
                    if current_price > sma_5_val:
                        print("🟢 매수 조건: 현재가 > SMA5 (매수 신호 가능)")
                    elif current_price <= sma_5_val:
                        print("🔴 매도 조건: 현재가 <= SMA5 (매도 신호 가능)")
                    
                    # 거래대금 필터 확인
                    if avg_volume_5d >= 30_000_000_000:
                        print("✅ 거래대금 필터: 통과 (30B원 이상)")
                    else:
                        print("❌ 거래대금 필터: 미통과 (30B원 미만)")
                        
                except Exception as e:
                    print(f"⚠️ 신호 조건 계산 오류: {e}")
        else:
            print("❌ 기술 지표 없음")
            print("   원인: event_simulator.py의 지표 생성 문제")
    except Exception as e:
        print(f"❌ 기술 지표 오류: {e}")
    
    # 호가 데이터 확인
    print("\n4️⃣ 호가 데이터 확인")
    print("-" * 20)
    try:
        orderbook = redis_manager.get_orderbook_data(symbol)
        if orderbook:
            print("✅ 호가 데이터 있음")
            bid_price = orderbook.get('bid_price', 'N/A')
            ask_price = orderbook.get('ask_price', 'N/A')
            print(f"💸 매수호가: ₩{bid_price}")
            print(f"💰 매도호가: ₩{ask_price}")
        else:
            print("❌ 호가 데이터 없음")
    except Exception as e:
        print(f"❌ 호가 데이터 오류: {e}")
    
    # Redis 키 패턴 확인
    print("\n5️⃣ Redis 키 현황")
    print("-" * 20)
    try:
        # 관련 키들 확인
        market_keys = redis_manager.get_keys_by_pattern(f"market:{symbol}*")
        indicator_keys = redis_manager.get_keys_by_pattern(f"indicators:{symbol}*")
        orderbook_keys = redis_manager.get_keys_by_pattern(f"orderbook:{symbol}*")
        event_keys = redis_manager.get_keys_by_pattern("event:*")
        
        print(f"📊 시장데이터 키: {len(market_keys)}개")
        print(f"📈 지표 키: {len(indicator_keys)}개") 
        print(f"📋 호가 키: {len(orderbook_keys)}개")
        print(f"📡 이벤트 키: {len(event_keys)}개")
        
        if event_keys:
            print("📡 이벤트 채널들:")
            for key in event_keys[:5]:  # 처음 5개만 표시
                print(f"   - {key}")
                
    except Exception as e:
        print(f"❌ Redis 키 확인 오류: {e}")
    
    # 프로세스 확인 (시스템 명령어 사용)
    print("\n6️⃣ 프로세스 확인")
    print("-" * 20)
    try:
        import subprocess
        
        # Python 프로세스 확인
        result = subprocess.run(['pgrep', '-f', 'run_live_trading.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ run_live_trading.py 실행 중")
        else:
            print("❌ run_live_trading.py 실행되지 않음")
        
        result = subprocess.run(['pgrep', '-f', 'event_simulator.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ event_simulator.py 실행 중")
        else:
            print("❌ event_simulator.py 실행되지 않음")
            print("   해결방안: python tools/event_simulator.py 실행")
            
        # Redis 프로세스 확인
        result = subprocess.run(['pgrep', '-f', 'redis-server'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ redis-server 실행 중")
        else:
            print("❌ redis-server 실행되지 않음")
            print("   해결방안: redis-server 명령으로 시작")
            
    except Exception as e:
        print(f"⚠️ 프로세스 확인 불가: {e}")
    
    # 종합 진단
    print("\n🚨 종합 진단")
    print("-" * 20)
    
    # 체결이 안되는 원인 분석
    has_market_data = bool(redis_manager.get_market_data(symbol))
    has_indicators = bool(redis_manager.get_data(f"indicators:{symbol}"))
    
    if not has_market_data and not has_indicators:
        print("❌ 주요 원인: 이벤트 시뮬레이터가 데이터를 생성하지 않음")
        print("   해결방안:")
        print("   1. python tools/event_simulator.py --symbol 005930 실행")
        print("   2. 또는 python tools/run_simulation_test.py 실행")
    elif has_market_data and has_indicators:
        print("✅ 데이터는 정상적으로 생성되고 있음")
        print("⚠️ 체결이 안되는 다른 원인:")
        print("   1. 전략 엔진이 신호를 생성하지 않음 (조건 불충족)")
        print("   2. 주문 엔진에서 주문을 실행하지 않음")
        print("   3. 리스크 엔진에서 주문을 차단함")
        print("   4. 모의 거래 모드로 실제 체결이 발생하지 않음")
    else:
        print("⚠️ 부분적 데이터 문제")
        print("   일부 데이터만 생성되고 있습니다")
    
    print("\n📋 권장 다음 단계:")
    print("1. python tools/live_monitor.py 실행 (실시간 모니터링)")
    print("2. logs/trading.log 파일 확인")
    print("3. 전략 로그에서 신호 생성 여부 확인")
    
    print("\n" + "=" * 50)
    print("✅ 빠른 진단 완료")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='QB Trading System - 빠른 디버깅')
    parser.add_argument('--symbol', default='005930', help='확인할 종목 코드 (기본: 005930)')
    
    args = parser.parse_args()
    
    try:
        quick_debug(args.symbol)
    except Exception as e:
        print(f"\n❌ 디버깅 도구 오류: {e}")
        import traceback
        traceback.print_exc()