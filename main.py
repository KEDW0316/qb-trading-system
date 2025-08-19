"""
QuickBit Trading System Entry Point

한국투자증권 API 기반 알고리즘 트레이딩 시스템
"""

import asyncio
import logging
from pathlib import Path

from qb.engines.event_bus.engine import EventBusEngine
from qb.engines.data_collector.engine import DataCollectorEngine
from qb.engines.strategy_engine.engine import StrategyEngine
from qb.engines.order_engine.engine import OrderEngine
from qb.engines.risk_engine.engine import RiskEngine
from qb.utils.redis_manager import RedisManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """메인 실행 함수"""
    logger.info("QuickBit Trading System 시작")
    
    try:
        # 이벤트 버스 초기화
        event_bus = EventBusEngine()
        await event_bus.initialize()
        
        # Redis 매니저 초기화
        redis_manager = RedisManager()
        await redis_manager.initialize()
        
        # 엔진들 생성
        engines = {
            'data_collector': DataCollectorEngine(event_bus),
            'strategy': StrategyEngine(event_bus),
            'order': OrderEngine(event_bus),
            'risk': RiskEngine(event_bus)
        }
        
        # 엔진들 초기화
        for name, engine in engines.items():
            logger.info(f"{name} 엔진 초기화 중...")
            await engine.initialize()
        
        logger.info("모든 엔진 초기화 완료")
        
        # 시스템 실행
        tasks = []
        for name, engine in engines.items():
            tasks.append(asyncio.create_task(engine.run(), name=name))
        
        # 모든 엔진 실행 대기
        await asyncio.gather(*tasks)
        
    except KeyboardInterrupt:
        logger.info("사용자 종료 요청")
    except Exception as e:
        logger.error(f"시스템 오류: {e}")
        raise
    finally:
        # 정리
        logger.info("시스템 종료 중...")
        if 'engines' in locals():
            for engine in engines.values():
                await engine.shutdown()
        await event_bus.shutdown()
        await redis_manager.shutdown()
        logger.info("시스템 종료 완료")

if __name__ == "__main__":
    asyncio.run(main())