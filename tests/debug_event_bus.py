#!/usr/bin/env python3
"""
Event Bus 디버깅 테스트
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.utils.redis_manager import RedisManager
from qb.utils.event_bus import EventBus, EventType, Event

class EventDebugger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_manager = RedisManager()
        self.event_bus = EventBus(self.redis_manager)
        self.received_events = []
        
    def setup_event_handlers(self):
        """이벤트 핸들러 설정"""
        
        def market_data_handler(event):
            self.logger.info(f"🎯 [HANDLER] Market data event received!")
            self.received_events.append(('market_data', event))
            
        def trading_signal_handler(event):
            self.logger.info(f"🎯 [HANDLER] Trading signal event received!")
            self.received_events.append(('trading_signal', event))
        
        # 이벤트 구독
        self.event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, market_data_handler)
        self.event_bus.subscribe(EventType.TRADING_SIGNAL, trading_signal_handler)
        
        self.logger.info("Event handlers set up")
        
    def test_event_publishing(self):
        """이벤트 발행 테스트"""
        self.logger.info("Testing event publishing...")
        
        # 테스트 이벤트 발행
        test_event = {
            'symbol': '005930',
            'price': 75000,
            'volume': 1000,
            'timestamp': time.time()
        }
        
        # 이벤트 직접 발행
        market_event = Event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source="test",
            data=test_event,
            timestamp=datetime.now()
        )
        self.event_bus.publish(market_event)
        self.logger.info("Market data event published")
        
        # 거래 신호 이벤트 발행
        signal_data = {
            'symbol': '005930',
            'action': 'BUY',
            'price': 75000,
            'confidence': 0.8
        }
        
        signal_event = Event(
            event_type=EventType.TRADING_SIGNAL,
            source="test",
            data=signal_data,
            timestamp=datetime.now()
        )
        self.event_bus.publish(signal_event)
        self.logger.info("Trading signal event published")
        
    def wait_for_events(self, timeout=5):
        """이벤트 수신 대기"""
        self.logger.info(f"Waiting for events (timeout: {timeout}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.received_events:
                break
            time.sleep(0.1)
        
        self.logger.info(f"Received {len(self.received_events)} events")
        for event_type, event in self.received_events:
            self.logger.info(f"  - {event_type}: {event}")
            
        return len(self.received_events)

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logger = logging.getLogger(__name__)
    logger.info("🔍 Event Bus Debug Test Starting...")
    
    debugger = EventDebugger()
    
    try:
        # Event Bus 시작
        debugger.event_bus.start()
        
        # 핸들러 설정
        debugger.setup_event_handlers()
        
        # 잠시 대기 (구독 완료를 위해)
        await asyncio.sleep(1)
        
        # 이벤트 발행
        debugger.test_event_publishing()
        
        # 이벤트 수신 대기
        event_count = debugger.wait_for_events(timeout=5)
        
        if event_count > 0:
            logger.info("✅ Event Bus working correctly!")
        else:
            logger.error("❌ No events received - there's an issue")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        debugger.event_bus.stop()

if __name__ == "__main__":
    asyncio.run(main())