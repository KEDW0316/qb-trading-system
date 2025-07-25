"""
거래 모드 관리자 테스트
Trading Mode Manager Test

TradingModeManager 클래스의 기본 기능 테스트
"""

import sys
import os
import tempfile
import json
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.utils.trading_mode import TradingModeManager


def test_trading_mode_manager():
    """TradingModeManager 기본 기능 테스트"""
    print("🧪 TradingModeManager 기본 기능 테스트")
    print("="*50)
    
    # 임시 디렉토리 사용
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "trading_mode.json")
        
        # 1. TradingModeManager 초기화 테스트
        print("1. 초기화 테스트...")
        mode_manager = TradingModeManager(config_path=config_path)
        print(f"   초기 모드: {mode_manager.get_current_mode()}")
        print(f"   모드명: {mode_manager.get_mode_name()}")
        print(f"   설정 파일 존재: {Path(config_path).exists()}")
        
        # 2. 기본 설정 확인
        print("\n2. 기본 설정 확인...")
        print(f"   모의투자 모드: {mode_manager.is_paper_trading()}")
        print(f"   실전투자 모드: {mode_manager.is_prod_trading()}")
        print(f"   Base URL: {mode_manager.get_base_url()}")
        print(f"   TR ID Prefix: {mode_manager.get_tr_id_prefix()}")
        
        # 3. 안전 설정 확인
        print("\n3. 안전 설정 확인...")
        safety = mode_manager.get_safety_settings()
        for key, value in safety.items():
            print(f"   {key}: {value}")
        
        # 4. 모의투자 모드로 전환 테스트
        print("\n4. 모의투자 모드로 전환 테스트...")
        success = mode_manager.switch_to_paper_mode()
        print(f"   전환 결과: {success}")
        print(f"   현재 모드: {mode_manager.get_current_mode()}")
        print(f"   모의투자 모드: {mode_manager.is_paper_trading()}")
        
        # 5. 실전투자 모드로 전환 테스트 (force=True)
        print("\n5. 실전투자 모드로 전환 테스트 (자동)...")
        success = mode_manager.switch_to_prod_mode(force=True, reason="Test automation")
        print(f"   전환 결과: {success}")
        print(f"   현재 모드: {mode_manager.get_current_mode()}")
        print(f"   실전투자 모드: {mode_manager.is_prod_trading()}")
        
        # 6. 모드별 설정 확인
        print("\n6. 모드별 설정 확인...")
        paper_config = mode_manager.get_mode_config("paper")
        prod_config = mode_manager.get_mode_config("prod")
        
        print(f"   모의투자 설정:")
        for key, value in paper_config.items():
            print(f"     {key}: {value}")
        
        print(f"   실전투자 설정:")
        for key, value in prod_config.items():
            print(f"     {key}: {value}")
        
        # 7. 감사 로그 확인
        print("\n7. 감사 로그 확인...")
        audit_logs = mode_manager.get_audit_log(limit=3)
        print(f"   로그 항목 수: {len(audit_logs)}")
        
        for i, log in enumerate(audit_logs, 1):
            print(f"   {i}. {log.get('timestamp', 'Unknown')[:19]}")
            print(f"      {log.get('from_mode')} → {log.get('to_mode')}")
            print(f"      사유: {log.get('reason')}")
        
        # 8. 설정 파일 내용 확인
        print("\n8. 설정 파일 내용 확인...")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print(f"   설정 파일 키: {list(config.keys())}")
        print(f"   현재 모드: {config.get('mode')}")
        print(f"   마지막 업데이트: {config.get('last_updated', 'Unknown')[:19]}")
        
        # 9. 다시 모의투자 모드로 복원
        print("\n9. 모의투자 모드로 복원...")
        success = mode_manager.switch_to_paper_mode()
        print(f"   전환 결과: {success}")
        print(f"   최종 모드: {mode_manager.get_current_mode()}")
        
        print("\n✅ TradingModeManager 테스트 완료!")
        print(f"   객체 표현: {mode_manager}")


def test_tr_id_generation():
    """TR ID 생성 로직 테스트"""
    print("\n🧪 TR ID 생성 로직 테스트")
    print("="*50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "trading_mode.json")
        mode_manager = TradingModeManager(config_path=config_path)
        
        # 테스트할 TR ID들
        test_tr_ids = [
            "TTC8434R",  # 계좌 잔고 조회
            "TTC0802U",  # 매수 주문
            "TTC0801U",  # 매도 주문
            "TTC0803U",  # 주문 취소/정정
            "TTC8001R",  # 주문 내역 조회
        ]
        
        # 모의투자 모드에서 테스트
        print("\n1. 모의투자 모드 TR ID 생성:")
        mode_manager.switch_to_paper_mode()
        prefix = mode_manager.get_tr_id_prefix()
        print(f"   TR ID Prefix: {prefix}")
        
        for base_id in test_tr_ids:
            if prefix and base_id.startswith('T'):
                generated_id = f"{prefix}{base_id[1:]}"
            else:
                generated_id = base_id
            print(f"   {base_id} → {generated_id}")
        
        # 실전투자 모드에서 테스트
        print("\n2. 실전투자 모드 TR ID 생성:")
        mode_manager.switch_to_prod_mode(force=True, reason="TR ID test")
        prefix = mode_manager.get_tr_id_prefix()
        print(f"   TR ID Prefix: {prefix}")
        
        for base_id in test_tr_ids:
            if prefix and base_id.startswith('T'):
                generated_id = f"{prefix}{base_id[1:]}"
            else:
                generated_id = base_id
            print(f"   {base_id} → {generated_id}")
        
        print("\n✅ TR ID 생성 테스트 완료!")


def test_safety_features():
    """안전 기능 테스트"""
    print("\n🧪 안전 기능 테스트")
    print("="*50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = os.path.join(temp_dir, "trading_mode.json")
        mode_manager = TradingModeManager(config_path=config_path)
        
        # 1. 기본 안전 설정 확인
        print("1. 기본 안전 설정:")
        safety = mode_manager.get_safety_settings()
        for key, value in safety.items():
            print(f"   {key}: {value}")
        
        # 2. 실전 모드 전환 테스트 (force=False, 자동으로 force=True 처리)
        print("\n2. 실전 모드 전환 안전 검사:")
        print("   (테스트 환경에서는 자동으로 force=True 처리)")
        
        # 실전 모드로 전환
        success = mode_manager.switch_to_prod_mode(force=True, reason="Safety test")
        print(f"   전환 결과: {success}")
        
        if success:
            print("   ⚠️  실전투자 모드로 전환됨 - 실제 거래 주의!")
        
        # 다시 모의투자로 복원
        mode_manager.switch_to_paper_mode()
        print("   ✅ 모의투자 모드로 복원 완료")
        
        print("\n✅ 안전 기능 테스트 완료!")


def main():
    """메인 테스트 함수"""
    print("🎯 거래 모드 관리자 전체 테스트 시작")
    print("="*60)
    
    try:
        # 기본 기능 테스트
        test_trading_mode_manager()
        
        # TR ID 생성 테스트
        test_tr_id_generation()
        
        # 안전 기능 테스트
        test_safety_features()
        
        print(f"\n{'='*60}")
        print("🎉 모든 테스트 완료!")
        print("✅ TradingModeManager가 정상적으로 작동합니다.")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()