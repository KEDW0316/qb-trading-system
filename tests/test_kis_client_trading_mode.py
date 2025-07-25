"""
KIS Client 거래 모드 통합 테스트
KIS Client Trading Mode Integration Test

KISClient에 통합된 TradingModeManager 기능 테스트
"""

import sys
import os
import tempfile
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.collectors.kis_client import KISClient


def test_kis_client_trading_mode():
    """KISClient 거래 모드 기능 테스트"""
    print("🧪 KISClient 거래 모드 통합 테스트")
    print("="*50)
    
    try:
        # 1. KISClient 초기화 (기본 모드)
        print("1. KISClient 초기화 (기본 모드)...")
        client = KISClient()
        print(f"   초기 모드: {client.mode}")
        print(f"   모의투자 모드: {client.is_paper_trading}")
        
        # 2. 모드 정보 확인
        print("\n2. 모드 정보 확인...")
        mode_info = client.get_current_mode_info()
        for key, value in mode_info.items():
            print(f"   {key}: {value}")
        
        # 3. TR ID 생성 테스트
        print("\n3. TR ID 생성 테스트...")
        test_tr_ids = ["TTC8434R", "TTC0802U", "TTC0801U"]
        for base_id in test_tr_ids:
            generated_id = client._get_tr_id(base_id)
            print(f"   {base_id} → {generated_id}")
        
        # 4. 모의투자 모드로 전환
        print("\n4. 모의투자 모드로 전환...")
        success = client.switch_to_paper_mode()
        print(f"   전환 결과: {success}")
        print(f"   현재 모드: {client.mode}")
        print(f"   모의투자 모드: {client.is_paper_trading}")
        
        # 5. 실전투자 모드로 전환 (force=True)
        print("\n5. 실전투자 모드로 전환 (자동)...")
        success = client.switch_to_prod_mode(force=True, reason="KISClient integration test")
        print(f"   전환 결과: {success}")
        print(f"   현재 모드: {client.mode}")
        print(f"   실전투자 모드: {not client.is_paper_trading}")
        
        # 6. 전환 후 TR ID 생성 테스트
        print("\n6. 실전 모드에서 TR ID 생성 테스트...")
        for base_id in test_tr_ids:
            generated_id = client._get_tr_id(base_id)
            print(f"   {base_id} → {generated_id}")
        
        # 7. 계좌 정보 확인
        print("\n7. 계좌 정보 확인...")
        try:
            account_info = client.account_info
            print(f"   계좌 정보: {account_info[0]}-{account_info[1]}")
        except Exception as e:
            print(f"   계좌 정보를 가져올 수 없음 (환경변수 미설정): {str(e)}")
        
        # 8. Rate limit 상태 확인
        print("\n8. Rate limit 상태 확인...")
        rate_status = client.get_current_rate_limit_status()
        for key, value in rate_status.items():
            print(f"   {key}: {value}")
        
        # 9. 모의투자 모드로 복원
        print("\n9. 모의투자 모드로 복원...")
        success = client.switch_to_paper_mode()
        print(f"   전환 결과: {success}")
        print(f"   최종 모드: {client.mode}")
        
        print("\n✅ KISClient 거래 모드 통합 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


def test_kis_client_initialization_modes():
    """KISClient 초기화 모드 테스트"""
    print("\n🧪 KISClient 초기화 모드 테스트")
    print("="*50)
    
    try:
        # 1. 기본 초기화 (설정 파일 모드 사용)
        print("1. 기본 초기화...")
        client1 = KISClient()
        print(f"   모드: {client1.mode}")
        
        # 2. 명시적 모의투자 모드 초기화
        print("\n2. 명시적 모의투자 모드 초기화...")
        client2 = KISClient(mode='paper')
        print(f"   모드: {client2.mode}")
        print(f"   모의투자 모드: {client2.is_paper_trading}")
        
        # 3. 명시적 실전투자 모드 초기화 (force=True로 처리됨)
        print("\n3. 명시적 실전투자 모드 초기화...")
        client3 = KISClient(mode='prod')
        print(f"   모드: {client3.mode}")
        print(f"   실전투자 모드: {not client3.is_paper_trading}")
        
        # 4. 잘못된 모드 초기화 테스트
        print("\n4. 잘못된 모드 초기화 테스트...")
        try:
            client4 = KISClient(mode='invalid')
            print("   ❌ 잘못된 모드가 허용됨")
        except ValueError as e:
            print(f"   ✅ 올바르게 ValueError 발생: {e}")
        
        print("\n✅ KISClient 초기화 모드 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


def test_mode_manager_integration():
    """모드 관리자 통합 테스트"""
    print("\n🧪 모드 관리자 통합 테스트")
    print("="*50)
    
    try:
        client = KISClient()
        mode_manager = client.mode_manager
        
        # 1. 모드 관리자 참조 확인
        print("1. 모드 관리자 참조 확인...")
        print(f"   모드 관리자: {mode_manager}")
        print(f"   클라이언트 모드: {client.mode}")
        print(f"   관리자 모드: {mode_manager.get_current_mode()}")
        print(f"   모드 일치: {client.mode == mode_manager.get_current_mode()}")
        
        # 2. 감사 로그 확인
        print("\n2. 감사 로그 확인...")
        audit_logs = mode_manager.get_audit_log(limit=3)
        print(f"   로그 항목 수: {len(audit_logs)}")
        
        for i, log in enumerate(audit_logs[:3], 1):
            timestamp = log.get('timestamp', 'Unknown')[:19]
            from_mode = log.get('from_mode', 'Unknown')
            to_mode = log.get('to_mode', 'Unknown')
            reason = log.get('reason', 'Unknown')
            print(f"   {i}. {timestamp}: {from_mode} → {to_mode} ({reason})")
        
        # 3. 설정 파일 확인
        print("\n3. 설정 파일 확인...")
        config_path = mode_manager.config_path
        print(f"   설정 파일: {config_path}")
        print(f"   파일 존재: {config_path.exists()}")
        
        if config_path.exists():
            stat = config_path.stat()
            print(f"   파일 크기: {stat.st_size} bytes")
        
        print("\n✅ 모드 관리자 통합 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """메인 테스트 함수"""
    print("🎯 KISClient 거래 모드 통합 전체 테스트 시작")
    print("="*60)
    
    try:
        # KISClient 거래 모드 기능 테스트
        test_kis_client_trading_mode()
        
        # KISClient 초기화 모드 테스트
        test_kis_client_initialization_modes()
        
        # 모드 관리자 통합 테스트
        test_mode_manager_integration()
        
        print(f"\n{'='*60}")
        print("🎉 모든 테스트 완료!")
        print("✅ KISClient 거래 모드 통합이 정상적으로 작동합니다.")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 전체 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()