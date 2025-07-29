#!/usr/bin/env python3
"""
Quick Test - 10초 짧은 테스트
"""

import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from tests.enhanced_mock_test import EnhancedMockTester

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logger = logging.getLogger(__name__)
    logger.info("🚀 Quick 10-second test starting...")
    
    tester = EnhancedMockTester()
    
    try:
        await tester.initialize()
        await tester.run_pipeline_test(duration=10)  # 10초 테스트
        
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted")
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())