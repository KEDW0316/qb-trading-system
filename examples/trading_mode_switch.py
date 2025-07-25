"""
거래 모드 전환 예제 스크립트
Trading Mode Switch Example Script

모의투자와 실전투자 모드 간 전환 기능 테스트
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.collectors.kis_client import KISClient
from qb.utils.trading_mode import TradingModeManager


def setup_logging():
    """로깅 설정"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/trading_mode_example.log', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)


def print_mode_info(client: KISClient):
    """현재 모드 정보 출력"""
    mode_info = client.get_current_mode_info()
    
    print(f"\n{'='*50}")
    print("📊 현재 거래 모드 정보 / Current Trading Mode Info")
    print(f"{'='*50}")
    print(f"모드 / Mode: {mode_info['mode']}")
    print(f"모드명 / Mode Name: {mode_info['mode_name']}")
    print(f"모의투자 여부 / Is Paper Trading: {mode_info['is_paper_trading']}")
    print(f"Base URL: {mode_info['base_url']}")
    print(f"TR ID Prefix: {mode_info['tr_id_prefix']}")
    print(f"{'='*50}\n")


def print_safety_settings(mode_manager: TradingModeManager):
    """안전 설정 정보 출력"""
    safety = mode_manager.get_safety_settings()
    
    print(f"\n{'='*50}")
    print("🛡️ 안전 설정 / Safety Settings")
    print(f"{'='*50}")
    print(f"실전 모드 확인 / Confirm Real Mode: {safety.get('confirm_real_mode', True)}")
    print(f"최대 주문 금액 / Max Order Amount: {safety.get('max_order_amount', 1000000):,}원")
    print(f"일일 최대 주문 수 / Max Daily Orders: {safety.get('max_daily_orders', 20)}건")
    print(f"확인 키워드 요구 / Require Confirmation: {safety.get('require_confirmation_keywords', True)}")
    print(f"확인 키워드 / Confirmation Keyword: {safety.get('confirmation_keyword', 'CONFIRM')}")
    print(f"{'='*50}\n")


def print_audit_log(mode_manager: TradingModeManager):
    """감사 로그 출력"""
    logs = mode_manager.get_audit_log(limit=5)
    
    if not logs:
        print("📝 감사 로그가 없습니다 / No audit logs available\n")
        return
    
    print(f"\n{'='*50}")
    print("📝 최근 모드 전환 기록 / Recent Mode Changes")
    print(f"{'='*50}")
    
    for i, log in enumerate(logs, 1):
        timestamp = log.get('timestamp', 'Unknown')
        from_mode = log.get('from_mode', 'Unknown')
        to_mode = log.get('to_mode', 'Unknown') 
        reason = log.get('reason', 'Unknown')
        user = log.get('user', 'Unknown')
        
        print(f"{i}. {timestamp[:19]}")
        print(f"   {from_mode} → {to_mode}")
        print(f"   사유 / Reason: {reason}")
        print(f"   사용자 / User: {user}")
        print()


async def test_basic_functionality(client: KISClient):
    """기본 기능 테스트"""
    logger = logging.getLogger(__name__)
    
    print(f"\n{'='*50}")
    print("🧪 기본 기능 테스트 / Basic Functionality Test")
    print(f"{'='*50}")
    
    try:
        # 계좌 정보 조회 테스트
        print("1. 계좌 정보 조회 테스트...")
        account_info = client.account_info
        print(f"   계좌 정보: {account_info[0]}-{account_info[1]}")
        
        # TR ID 생성 테스트
        print("2. TR ID 생성 테스트...")
        test_tr_ids = ["TTC8434R", "TTC0802U", "TTC0801U"]
        for base_id in test_tr_ids:
            generated_id = client._get_tr_id(base_id)
            print(f"   {base_id} → {generated_id}")
        
        # Rate limit 상태 확인
        print("3. Rate limit 상태 확인...")
        rate_status = client.get_current_rate_limit_status()
        print(f"   현재 요청 수: {rate_status['requests_last_second']}/{rate_status['max_requests_per_second']}")
        print(f"   일일 요청 수: {rate_status['daily_request_count']}")
        
        print("✅ 기본 기능 테스트 완료\n")
        
    except Exception as e:
        logger.error(f"기본 기능 테스트 실패: {str(e)}")
        print(f"❌ 기본 기능 테스트 실패: {str(e)}\n")


async def interactive_mode_switch():
    """대화형 모드 전환"""
    logger = setup_logging()
    
    print(f"\n{'='*60}")
    print("🎛️  거래 모드 전환 도구 / Trading Mode Switch Tool")
    print(f"{'='*60}")
    
    try:
        # KIS 클라이언트 초기화
        logger.info("KIS 클라이언트 초기화 중...")
        client = KISClient()
        mode_manager = client.mode_manager
        
        while True:
            # 현재 상태 출력
            print_mode_info(client)
            print_safety_settings(mode_manager)
            
            # 메뉴 출력
            print("🎯 사용 가능한 작업 / Available Actions:")
            print("1. 모의투자 모드로 전환 / Switch to Paper Trading")
            print("2. 실전투자 모드로 전환 / Switch to Real Trading")
            print("3. 기본 기능 테스트 / Test Basic Functionality")
            print("4. 감사 로그 보기 / View Audit Log")
            print("5. 모드 관리자 정보 / Mode Manager Info")
            print("6. 종료 / Exit")
            
            try:
                choice = input("\n선택하세요 / Choose (1-6): ").strip()
                
                if choice == "1":
                    print("\n📘 모의투자 모드로 전환 중...")
                    if client.switch_to_paper_mode():
                        print("✅ 모의투자 모드로 전환 완료!")
                    else:
                        print("❌ 모의투자 모드 전환 실패")
                
                elif choice == "2":
                    print("\n📕 실전투자 모드로 전환 중...")
                    if client.switch_to_prod_mode(reason="Interactive mode switch"):
                        print("✅ 실전투자 모드로 전환 완료!")
                    else:
                        print("❌ 실전투자 모드 전환 실패 또는 취소됨")
                
                elif choice == "3":
                    await test_basic_functionality(client)
                
                elif choice == "4":
                    print_audit_log(mode_manager)
                
                elif choice == "5":
                    print(f"\n📋 모드 관리자 정보:")
                    print(f"   {mode_manager}")
                    print(f"   설정 파일: {mode_manager.config_path}")
                    print(f"   마지막 업데이트: {mode_manager.config.get('last_updated', 'Unknown')}")
                
                elif choice == "6":
                    print("👋 프로그램을 종료합니다. / Exiting program.")
                    break
                
                else:
                    print("❌ 잘못된 선택입니다. 1-6 사이의 숫자를 입력하세요.")
                
                # 계속하기 전 잠시 대기
                input("\nEnter를 눌러 계속하세요... / Press Enter to continue...")
                
            except KeyboardInterrupt:
                print("\n\n👋 사용자가 프로그램을 종료했습니다.")
                break
            except Exception as e:
                logger.error(f"오류 발생: {str(e)}")
                print(f"❌ 오류 발생: {str(e)}")
                input("\nEnter를 눌러 계속하세요... / Press Enter to continue...")
        
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류: {str(e)}")
        print(f"❌ 프로그램 실행 중 오류: {str(e)}")


async def automated_test():
    """자동화된 테스트"""
    logger = setup_logging()
    
    print(f"\n{'='*60}")
    print("🤖 자동화된 모드 전환 테스트 / Automated Mode Switch Test")
    print(f"{'='*60}")
    
    try:
        # 클라이언트 초기화
        client = KISClient()
        
        # 초기 상태 확인
        print("1. 초기 상태 확인...")
        print_mode_info(client)
        
        # 모의투자 모드로 전환
        print("2. 모의투자 모드로 전환...")
        success = client.switch_to_paper_mode()
        print(f"   결과: {'성공' if success else '실패'}")
        print_mode_info(client)
        
        # 기본 기능 테스트
        print("3. 기본 기능 테스트...")
        await test_basic_functionality(client)
        
        # 실전투자 모드로 전환 (force=True로 프롬프트 생략)
        print("4. 실전투자 모드로 전환 (자동)...")
        success = client.switch_to_prod_mode(force=True, reason="Automated test")
        print(f"   결과: {'성공' if success else '실패'}")
        print_mode_info(client)
        
        # 다시 모의투자 모드로 복원
        print("5. 모의투자 모드로 복원...")
        success = client.switch_to_paper_mode()
        print(f"   결과: {'성공' if success else '실패'}")
        print_mode_info(client)
        
        # 감사 로그 확인
        print("6. 감사 로그 확인...")
        print_audit_log(client.mode_manager)
        
        print("✅ 자동화된 테스트 완료!")
        
    except Exception as e:
        logger.error(f"자동화된 테스트 실패: {str(e)}")
        print(f"❌ 자동화된 테스트 실패: {str(e)}")


async def main():
    """메인 함수"""
    print("거래 모드 전환 예제 / Trading Mode Switch Example")
    print("1. 대화형 모드 / Interactive Mode")
    print("2. 자동화된 테스트 / Automated Test")
    
    try:
        choice = input("\n선택하세요 / Choose (1-2): ").strip()
        
        if choice == "1":
            await interactive_mode_switch()
        elif choice == "2":
            await automated_test()
        else:
            print("❌ 잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n\n👋 프로그램이 종료되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")


if __name__ == "__main__":
    # 로그 디렉토리 생성
    os.makedirs("logs", exist_ok=True)
    
    # 프로그램 실행
    asyncio.run(main())