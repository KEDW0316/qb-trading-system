#!/usr/bin/env python3
"""
간단한 대시보드 테스트
"""

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.bithumb_api import BithumbAPI
from src.strategy.batch_volume_monitor import BatchVolumeMonitor

async def test_simple_dashboard():
    """간단한 대시보드 테스트"""
    print("🚀 간단한 대시보드 테스트 시작!")
    
    try:
        # API 초기화
        api = BithumbAPI()
        
        # 모니터 초기화
        monitor = BatchVolumeMonitor(api)
        
        # 초기화
        print("📊 초기화 중...")
        if await monitor.initialize():
            print("✅ 초기화 완료!")
            
            # 간단한 모니터링 시작 (5개 종목만)
            print("🔍 간단한 모니터링 시작...")
            monitor.markets = monitor.markets[:5]  # 처음 5개만 테스트
            
            # 1회성 스캔
            await monitor.process_all_markets()
            
            # 요약 출력
            monitor.dashboard.print_statistics()
            
        else:
            print("❌ 초기화 실패!")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_dashboard())
