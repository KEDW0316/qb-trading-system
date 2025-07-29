"""
DataCollector Engine

실시간 데이터 수집을 위한 메인 엔진 클래스
이벤트 기반 아키텍처를 지원하는 데이터 수집기
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from ...utils.event_bus import EventBus, EventType, Event
from ...utils.redis_manager import RedisManager
from .adapters import BaseDataAdapter
from .normalizer import DataNormalizer
from .connection_manager import ConnectionManager
from .quality_checker import DataQualityChecker


class CollectorStatus(Enum):
    """데이터 수집기 상태"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class CollectionConfig:
    """데이터 수집 설정"""
    symbols: List[str]
    adapters: List[str]  # ['kis', 'naver', 'yahoo']
    max_candles: int = 200
    collection_interval: float = 1.0  # 초
    quality_check_enabled: bool = True
    auto_restart: bool = True
    heartbeat_interval: int = 30  # 초
    

class DataCollector:
    """
    실시간 데이터 수집 엔진
    
    주요 기능:
    - 다중 데이터 소스 통합 수집
    - Redis Rolling 업데이트 (최근 200개 캔들)
    - 이벤트 기반 아키텍처 지원
    - 자동 재연결 및 오류 복구
    - 데이터 품질 검증
    """
    
    def __init__(self, redis_manager: RedisManager, event_bus: EventBus, config: CollectionConfig):
        self.redis_manager = redis_manager
        self.event_bus = event_bus
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 상태 관리
        self.status = CollectorStatus.STOPPED
        self.start_time: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None
        
        # 컴포넌트 초기화
        self.data_normalizer = DataNormalizer()
        self.connection_manager = ConnectionManager()
        self.quality_checker = DataQualityChecker() if config.quality_check_enabled else None
        
        # 데이터 어댑터들
        self.adapters: Dict[str, BaseDataAdapter] = {}
        self.active_symbols: Set[str] = set()
        
        # 통계
        self.stats = {
            'messages_received': 0,
            'messages_processed': 0,
            'messages_failed': 0,
            'last_message_time': None,
            'uptime_seconds': 0,
            'restarts': 0
        }
        
        # 비동기 작업
        self.collection_tasks: List[asyncio.Task] = []
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.running = False
        
        self.logger.info(f"DataCollector initialized with {len(config.symbols)} symbols")
        
    async def start(self) -> bool:
        """데이터 수집 시작"""
        if self.status == CollectorStatus.RUNNING:
            self.logger.warning("DataCollector is already running")
            return True
            
        try:
            self.status = CollectorStatus.STARTING
            self.start_time = datetime.now()
            self.running = True
            
            # 어댑터 초기화
            await self._initialize_adapters()
            
            # 심볼 구독 시작
            await self._subscribe_symbols()
            
            # 수집 작업 시작
            await self._start_collection_tasks()
            
            # 하트비트 시작
            self._start_heartbeat()
            
            self.status = CollectorStatus.RUNNING
            
            # 시작 이벤트 발행
            await self._publish_event(
                EventType.SYSTEM_STATUS,
                {
                    'component': 'DataCollector',
                    'status': 'started',
                    'symbols': list(self.active_symbols),
                    'adapters': list(self.adapters.keys())
                }
            )
            
            self.logger.info("DataCollector started successfully")
            return True
            
        except Exception as e:
            self.status = CollectorStatus.ERROR
            self.logger.error(f"Failed to start DataCollector: {e}")
            await self._publish_error_event(f"DataCollector start failed: {e}")
            return False
    
    async def stop(self) -> bool:
        """데이터 수집 중지"""
        if self.status == CollectorStatus.STOPPED:
            self.logger.warning("DataCollector is already stopped")
            return True
            
        try:
            self.logger.info("Stopping DataCollector...")
            self.running = False
            
            # 수집 작업 중지
            await self._stop_collection_tasks()
            
            # 하트비트 중지
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # 어댑터 연결 해제
            await self._disconnect_adapters()
            
            self.status = CollectorStatus.STOPPED
            
            # 중지 이벤트 발행
            await self._publish_event(
                EventType.SYSTEM_STATUS,
                {
                    'component': 'DataCollector',
                    'status': 'stopped',
                    'uptime_seconds': self._get_uptime_seconds(),
                    'stats': self.stats.copy()
                }
            )
            
            self.logger.info("DataCollector stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop DataCollector: {e}")
            return False
    
    async def pause(self) -> bool:
        """데이터 수집 일시 중지"""
        if self.status != CollectorStatus.RUNNING:
            self.logger.warning("DataCollector is not running")
            return False
            
        self.status = CollectorStatus.PAUSED
        self.logger.info("DataCollector paused")
        return True
    
    async def resume(self) -> bool:
        """데이터 수집 재개"""
        if self.status != CollectorStatus.PAUSED:
            self.logger.warning("DataCollector is not paused")
            return False
            
        self.status = CollectorStatus.RUNNING
        self.logger.info("DataCollector resumed")
        return True
    
    async def add_symbol(self, symbol: str) -> bool:
        """심볼 추가"""
        try:
            if symbol in self.active_symbols:
                self.logger.warning(f"Symbol {symbol} is already active")
                return True
                
            # 모든 어댑터에 심볼 구독 추가
            success = True
            for adapter_name, adapter in self.adapters.items():
                try:
                    await adapter.subscribe_symbol(symbol)
                    self.logger.info(f"Subscribed to {symbol} on {adapter_name}")
                except Exception as e:
                    self.logger.error(f"Failed to subscribe {symbol} on {adapter_name}: {e}")
                    success = False
            
            if success:
                self.active_symbols.add(symbol)
                self.logger.info(f"Symbol {symbol} added successfully")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to add symbol {symbol}: {e}")
            return False
    
    async def remove_symbol(self, symbol: str) -> bool:
        """심볼 제거"""
        try:
            if symbol not in self.active_symbols:
                self.logger.warning(f"Symbol {symbol} is not active")
                return True
                
            # 모든 어댑터에서 심볼 구독 해제
            for adapter_name, adapter in self.adapters.items():
                try:
                    await adapter.unsubscribe_symbol(symbol)
                    self.logger.info(f"Unsubscribed from {symbol} on {adapter_name}")
                except Exception as e:
                    self.logger.error(f"Failed to unsubscribe {symbol} on {adapter_name}: {e}")
            
            self.active_symbols.remove(symbol)
            self.logger.info(f"Symbol {symbol} removed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove symbol {symbol}: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """수집기 상태 정보 반환"""
        return {
            'status': self.status.value,
            'uptime_seconds': self._get_uptime_seconds(),
            'active_symbols': list(self.active_symbols),
            'adapters': {
                name: adapter.get_status() 
                for name, adapter in self.adapters.items()
            },
            'stats': self.stats.copy(),
            'config': {
                'max_candles': self.config.max_candles,
                'collection_interval': self.config.collection_interval,
                'quality_check_enabled': self.config.quality_check_enabled
            }
        }
    
    async def _initialize_adapters(self):
        """어댑터들 초기화"""
        try:
            from .adapters import KISDataAdapter
            
            # KIS 어댑터 초기화
            if 'kis' in self.config.adapters:
                kis_config = {
                    'mode': 'prod',  # 실제거래 모드
                    'max_retries': 3,
                    'retry_delay': 5,
                    'approval_key': None  # WebSocket 승인키 (필요시 환경변수에서 로드)
                }
                
                kis_adapter = KISDataAdapter(kis_config)
                self.adapters['kis'] = kis_adapter
                
                # 연결 시도
                if await kis_adapter.connect():
                    self.logger.info("KIS adapter connected successfully")
                else:
                    self.logger.warning("KIS adapter connection failed, but continuing...")
                    
        except Exception as e:
            self.logger.error(f"Failed to initialize adapters: {e}")
            # 어댑터 초기화 실패해도 계속 진행
    
    async def _subscribe_symbols(self):
        """설정된 심볼들 구독"""
        for symbol in self.config.symbols:
            await self.add_symbol(symbol)
    
    async def _start_collection_tasks(self):
        """수집 작업들 시작"""
        # 각 어댑터별로 수집 작업 시작
        for adapter_name, adapter in self.adapters.items():
            task = asyncio.create_task(
                self._collection_worker(adapter_name, adapter)
            )
            self.collection_tasks.append(task)
            
        self.logger.info(f"Started {len(self.collection_tasks)} collection tasks")
    
    async def _stop_collection_tasks(self):
        """수집 작업들 중지"""
        for task in self.collection_tasks:
            task.cancel()
            
        # 모든 작업이 완료될 때까지 대기
        if self.collection_tasks:
            await asyncio.gather(*self.collection_tasks, return_exceptions=True)
            
        self.collection_tasks.clear()
        self.logger.info("Stopped all collection tasks")
    
    async def _collection_worker(self, adapter_name: str, adapter: BaseDataAdapter):
        """개별 어댑터 수집 워커"""
        self.logger.info(f"🔄 Collection worker started for {adapter_name}")
        
        try:
            while self.running:
                if self.status == CollectorStatus.PAUSED:
                    await asyncio.sleep(1)
                    continue
                    
                try:
                    # 어댑터에서 데이터 수집
                    messages = await adapter.collect_data()
                    
                    # 🔍 수집된 메시지 수 로그
                    if messages:
                        self.logger.debug(f"🔄 [{adapter_name}] Collected {len(messages)} messages")
                    
                    for message in messages:
                        await self._process_message(adapter_name, message)
                        
                except Exception as e:
                    self.logger.error(f"Error in collection worker {adapter_name}: {e}")
                    self.stats['messages_failed'] += 1
                    
                    if self.config.auto_restart:
                        await self._restart_adapter(adapter_name)
                
                await asyncio.sleep(self.config.collection_interval)
                
        except asyncio.CancelledError:
            self.logger.info(f"Collection worker {adapter_name} cancelled")
        except Exception as e:
            self.logger.error(f"Collection worker {adapter_name} failed: {e}")
    
    async def _process_message(self, adapter_name: str, raw_data: Dict[str, Any]):
        """메시지 처리"""
        try:
            self.stats['messages_received'] += 1
            self.stats['last_message_time'] = datetime.now().isoformat()
            
            # 호가 데이터 처리 (정규화 전에 먼저 처리)
            message_type = raw_data.get('message_type')
            if message_type == 'orderbook':
                await self._save_orderbook_to_redis(raw_data)
                # 호가 데이터는 별도 이벤트 발행 후 리턴
                await self._publish_orderbook_event(raw_data, adapter_name)
                self.stats['messages_processed'] += 1
                return
            
            # 데이터 정규화 (체결 데이터만)
            normalized_data = await self.data_normalizer.normalize(raw_data, adapter_name)
            
            # 🔍 실시간 데이터 수신 로그
            symbol = normalized_data.get('symbol', 'Unknown')
            price = normalized_data.get('close', 0)
            volume = normalized_data.get('volume', 0)
            timestamp = normalized_data.get('timestamp', 'Unknown')
            
            self.logger.info(f"📊 [{adapter_name}] {symbol}: ₩{price:,} (거래량: {volume:,}) at {timestamp}")
            
            # 품질 검증
            if self.quality_checker:
                is_valid, issues = await self.quality_checker.validate(normalized_data)
                if not is_valid:
                    self.logger.warning(f"❌ Data quality issues from {adapter_name}: {issues}")
                    return
            
            # Redis에 저장 (Rolling 업데이트)
            await self._save_to_redis(normalized_data)
            
            # 이벤트 발행
            await self._publish_market_data_event(normalized_data, adapter_name)
            
            self.stats['messages_processed'] += 1
            
            # 🔍 처리 통계 로그 (100개마다)
            if self.stats['messages_processed'] % 100 == 0:
                self.logger.info(f"📈 DataCollector Stats: {self.stats['messages_processed']} processed, "
                               f"{self.stats['messages_failed']} failed from {adapter_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to process message from {adapter_name}: {e}")
            self.stats['messages_failed'] += 1
    
    async def _save_to_redis(self, data: Dict[str, Any]):
        """Redis에 데이터 저장 (Rolling 업데이트)"""
        try:
            symbol = data['symbol']
            
            # 실시간 시장 데이터 업데이트
            await asyncio.to_thread(
                self.redis_manager.set_market_data,
                symbol,
                {
                    'timestamp': data['timestamp'],
                    'open': data['open'],
                    'high': data['high'],
                    'low': data['low'],
                    'close': data['close'],
                    'volume': data['volume']
                }
            )
            
            # 캔들 데이터 추가 (최대 200개 유지)
            await asyncio.to_thread(
                self.redis_manager.add_candle,
                symbol,
                '1m',  # 1분 캔들
                data,
                self.config.max_candles
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save data to Redis: {e}")
            raise
    
    async def _save_orderbook_to_redis(self, data: Dict[str, Any]):
        """호가 데이터를 Redis에 저장"""
        try:
            symbol = data['symbol']
            
            # 호가 데이터만 저장
            orderbook_data = {
                'timestamp': data['timestamp'],
                'bid_price': data.get('bid_price', 0),
                'ask_price': data.get('ask_price', 0),
                'bid_volume': data.get('bid_volume', 0),
                'ask_volume': data.get('ask_volume', 0)
            }
            
            await asyncio.to_thread(
                self.redis_manager.set_orderbook_data,
                symbol,
                orderbook_data
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save orderbook data to Redis: {e}")
            raise
    
    async def _publish_market_data_event(self, data: Dict[str, Any], source: str):
        """market_data_received 이벤트 발행"""
        self.logger.info(f"📤 Publishing MARKET_DATA_RECEIVED event for {data['symbol']} = ₩{data['close']:,.0f}")
        
        event = self.event_bus.create_event(
            EventType.MARKET_DATA_RECEIVED,
            source=f"DataCollector({source})",
            data={
                'symbol': data['symbol'],
                'timestamp': data['timestamp'],
                'open': data['open'],
                'high': data['high'],
                'low': data['low'],
                'close': data['close'],
                'volume': data['volume'],
                'source': source
            }
        )
        
        self.event_bus.publish(event)
    
    async def _publish_orderbook_event(self, data: Dict[str, Any], source: str):
        """orderbook_received 이벤트 발행"""
        event = self.event_bus.create_event(
            EventType.MARKET_DATA_RECEIVED,  # 동일한 이벤트타입 사용 (호가도 시장데이터)
            source=f"DataCollector({source})",
            data={
                'symbol': data['symbol'],
                'timestamp': data['timestamp'],
                'bid_price': data.get('bid_price', 0),
                'ask_price': data.get('ask_price', 0),
                'bid_volume': data.get('bid_volume', 0),
                'ask_volume': data.get('ask_volume', 0),
                'message_type': 'orderbook',
                'source': source
            }
        )
        
        self.event_bus.publish(event)
    
    async def _publish_event(self, event_type: EventType, data: Dict[str, Any]):
        """이벤트 발행 헬퍼"""
        event = self.event_bus.create_event(
            event_type,
            source="DataCollector",
            data=data
        )
        self.event_bus.publish(event)
    
    async def _publish_error_event(self, error_message: str):
        """에러 이벤트 발행"""
        await self._publish_event(
            EventType.ERROR_OCCURRED,
            {
                'component': 'DataCollector',
                'error': error_message,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def _start_heartbeat(self):
        """하트비트 시작"""
        if self.config.heartbeat_interval > 0:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_worker())
    
    async def _heartbeat_worker(self):
        """하트비트 워커"""
        while self.running:
            try:
                self.last_heartbeat = datetime.now()
                
                await self._publish_event(
                    EventType.HEARTBEAT,
                    {
                        'component': 'DataCollector',
                        'status': self.status.value,
                        'uptime_seconds': self._get_uptime_seconds(),
                        'stats': self.stats.copy()
                    }
                )
                
                await asyncio.sleep(self.config.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(5)
    
    async def _restart_adapter(self, adapter_name: str):
        """어댑터 재시작"""
        try:
            self.logger.info(f"Restarting adapter: {adapter_name}")
            adapter = self.adapters.get(adapter_name)
            if adapter:
                await adapter.disconnect()
                await asyncio.sleep(2)  # 잠시 대기
                await adapter.connect()
                
                # 활성 심볼들 다시 구독
                for symbol in self.active_symbols:
                    await adapter.subscribe_symbol(symbol)
                    
                self.stats['restarts'] += 1
                self.logger.info(f"Adapter {adapter_name} restarted successfully")
                
        except Exception as e:
            self.logger.error(f"Failed to restart adapter {adapter_name}: {e}")
    
    async def _disconnect_adapters(self):
        """모든 어댑터 연결 해제"""
        for adapter_name, adapter in self.adapters.items():
            try:
                await adapter.disconnect()
                self.logger.info(f"Disconnected adapter: {adapter_name}")
            except Exception as e:
                self.logger.error(f"Failed to disconnect adapter {adapter_name}: {e}")
    
    def _get_uptime_seconds(self) -> int:
        """업타임(초) 계산"""
        if self.start_time:
            return int((datetime.now() - self.start_time).total_seconds())
        return 0