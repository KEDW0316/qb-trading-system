#!/usr/bin/env python3
"""
QB Trading System - 오프라인 통합 테스트 자동 실행
==============================================
"""

import asyncio
import os
import sys
from pathlib import Path

# 테스트 클래스 import
sys.path.append(str(Path(__file__).parent))
from tests.test_offline_system_integration import OfflineSystemIntegrationTest

async def auto_run_test():
    """자동으로 테스트 실행"""
    print("🚀 QB Trading System 오프라인 통합 테스트 자동 실행")
    print("📝 장마감 시간에도 전체 시스템 검증 가능한 테스트입니다.")
    print("💡 실제 거래 없이 모든 컴포넌트의 동작을 확인합니다.")
    
    test = OfflineSystemIntegrationTest()
    
    try:
        # 시스템 초기화
        print("\n🔧 시스템 초기화 중...")
        if not await test.setup_system():
            print("❌ 시스템 초기화 실패. 테스트 중단.")
            return
        
        print("\n🧪 오프라인 통합 테스트 시나리오 실행 중...")
        
        # 1. 기본 연결성 테스트
        print("\n1️⃣ 연결성 테스트...")
        await test.test_connectivity()
        
        # 2. 모의 시장 데이터 플로우 테스트
        print("\n2️⃣ 모의 시장 데이터 플로우 테스트...")
        await test.test_mock_market_data_flow()
        
        # 3. 전략 시뮬레이션 테스트
        print("\n3️⃣ 전략 시뮬레이션 테스트...")
        await test.test_strategy_simulation()
        
        # 4. 리스크 관리 시뮬레이션
        print("\n4️⃣ 리스크 관리 시뮬레이션...")
        await test.test_risk_management_simulation()
        
        # 5. 모의 주문 실행 테스트
        print("\n5️⃣ 모의 주문 실행 테스트...")
        await test.test_mock_order_execution()
        
        # 6. 시스템 성능 테스트
        print("\n6️⃣ 시스템 성능 테스트...")
        await test.test_system_performance()
        
        # 결과 리포트
        print("\n📋 최종 결과 리포트 생성...")
        test.generate_report()
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 정리
        print("\n🧹 시스템 정리...")
        await test.cleanup()

if __name__ == "__main__":
    # 환경 확인
    print("📋 환경 확인 중...")
    print(f"🐍 Python: {sys.executable}")
    print(f"📁 작업 디렉토리: {os.getcwd()}")
    
    # 비동기 실행
    asyncio.run(auto_run_test())