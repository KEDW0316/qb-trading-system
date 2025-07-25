"""
KIS 클라이언트 테스트 예제
KIS Client Test Example

기본 API 클라이언트 클래스 테스트 스크립트
"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.collectors.kis_client import KISClient


async def test_kis_client():
    """KIS 클라이언트 기본 테스트"""
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        # KIS 클라이언트 초기화 (실전투자 모드)
        logger.info("Initializing KIS Client...")
        client = KISClient(mode='prod')
        
        # 클라이언트 기본 정보 출력
        logger.info(f"Client info: {client}")
        logger.info(f"Account info: {client.account_info}")
        logger.info(f"Paper trading: {client.is_paper_trading}")
        
        # Rate limit 상태 확인
        rate_limit_status = client.get_current_rate_limit_status()
        logger.info(f"Rate limit status: {rate_limit_status}")
        
        # 간단한 API 테스트 (토큰 발급 테스트)
        logger.info("Testing token acquisition...")
        token = client.auth.get_token()
        logger.info(f"Token acquired successfully: {token.access_token[:20]}...")
        
        logger.info("KIS Client test completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_kis_client())