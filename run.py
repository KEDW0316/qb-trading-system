#!/usr/bin/env python3
"""
KIS 자동매매 프로그램 실행 스크립트
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def parse_arguments():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="한국투자증권 API 자동매매 프로그램"
    )
    
    parser.add_argument(
        "--env", 
        choices=["prod", "vps"], 
        default="vps",
        help="실행 환경 (prod: 실전투자, vps: 모의투자)"
    )
    
    parser.add_argument(
        "--strategy", 
        default="realtime_rsi",
        help="사용할 매매 전략"
    )
    
    parser.add_argument(
        "--test-mode", 
        action="store_true",
        help="테스트 모드 (실제 주문 없이 시뮬레이션)"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="디버그 모드"
    )
    
    parser.add_argument(
        "--config", 
        default="config/config.yaml",
        help="설정 파일 경로"
    )
    
    return parser.parse_args()


async def main():
    """메인 실행 함수"""
    args = parse_arguments()
    
    print("🚀 KIS 자동매매 프로그램 시작")
    print(f"환경: {args.env}")
    print(f"전략: {args.strategy}")
    print(f"테스트 모드: {args.test_mode}")
    print("-" * 50)
    
    try:
        # TODO: 실제 메인 로직은 Phase 1.2 이후에 구현
        # from src.main import TradingSystem
        # system = TradingSystem(args)
        # await system.start()
        
        print("⚠️ 아직 메인 로직이 구현되지 않았습니다.")
        print("Phase 1.2 (KIS API 인증) 완료 후 사용 가능합니다.")
        
        # 기본 설정 파일 확인
        config_file = Path(args.config)
        if config_file.exists():
            print(f"✅ 설정 파일 확인: {config_file}")
        else:
            print(f"❌ 설정 파일 없음: {config_file}")
        
        # 환경변수 파일 확인
        env_file = Path(".env")
        if env_file.exists():
            print(f"✅ 환경변수 파일 확인: {env_file}")
        else:
            print(f"⚠️ 환경변수 파일 없음: {env_file}")
            print("   '.env.example'을 '.env'로 복사하고 설정을 입력해주세요.")
        
        print("\n📁 현재 프로젝트 구조:")
        print("✅ src/ - 소스 코드")
        print("✅ tests/ - 테스트 코드") 
        print("✅ config/ - 설정 파일")
        print("✅ data/ - 데이터 저장소")
        print("✅ logs/ - 로그 디렉터리")
        print("\n🎯 다음 단계: Phase 1.2 KIS API 인증 시스템 구현")
        
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Python 3.11+ 체크
    if sys.version_info < (3, 11):
        print("❌ Python 3.11 이상이 필요합니다.")
        sys.exit(1)
    
    # 비동기 메인 실행
    asyncio.run(main())