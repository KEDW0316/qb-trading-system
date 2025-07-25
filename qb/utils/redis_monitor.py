import time
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from .redis_manager import RedisManager
from .event_bus import EventBus, EventType


class RedisMonitor:
    """Redis 서버 모니터링 및 상태 확인 도구"""
    
    def __init__(self, redis_manager: RedisManager, event_bus: Optional[EventBus] = None):
        self.redis = redis_manager
        self.event_bus = event_bus
        self.logger = logging.getLogger(__name__)
        self.stats_history = []  # 통계 기록
        self.max_history = 100  # 최대 기록 수
        self.running = False
        self.monitor_task = None
        
    async def start_monitoring(self, interval_seconds: int = 60):
        """모니터링 시작"""
        if self.running:
            return
            
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop(interval_seconds))
        self.logger.info(f"Redis monitoring started with {interval_seconds}s interval")
        
    async def stop_monitoring(self):
        """모니터링 중지"""
        if not self.running:
            return
            
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
                
        self.logger.info("Redis monitoring stopped")
        
    async def _monitoring_loop(self, interval_seconds: int):
        """모니터링 루프"""
        while self.running:
            try:
                stats = self.collect_stats()
                self._add_to_history(stats)
                
                # 메모리 사용량 경고
                self._check_memory_alerts(stats)
                
                # 이벤트 버스로 상태 발행
                if self.event_bus:
                    event = self.event_bus.create_event(
                        EventType.SYSTEM_STATUS,
                        'redis_monitor',
                        {
                            'component': 'redis',
                            'status': 'ok' if stats['is_connected'] else 'error',
                            'memory_usage_percent': stats.get('memory_usage_percent', 0),
                            'clients_connected': stats.get('clients_connected', 0),
                            'timestamp': int(time.time())
                        }
                    )
                    self.event_bus.publish(event)
                    
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)
                
    def collect_stats(self) -> Dict[str, Any]:
        """Redis 서버 통계 수집"""
        try:
            # 연결 확인
            is_connected = self.redis.ping()
            
            if not is_connected:
                return {
                    'timestamp': datetime.now().isoformat(),
                    'is_connected': False
                }
                
            # 서버 정보 조회
            info = self.redis.get_info()
            memory_stats = self.redis.get_memory_stats()
            
            # 메모리 사용량 계산
            used_memory = info.get('used_memory', 0)
            max_memory = info.get('maxmemory', 0)
            # maxmemory가 0이면 시스템 메모리의 일부로 추정 (예: 150MB)
            if max_memory == 0:
                max_memory = 150 * 1024 * 1024  # 150MB
            memory_usage_percent = (used_memory / max_memory * 100) if max_memory > 0 else 0
            
            # 통계 구성
            stats = {
                'timestamp': datetime.now().isoformat(),
                'is_connected': True,
                'redis_version': info.get('redis_version', 'unknown'),
                'uptime_days': info.get('uptime_in_days', 0),
                'used_memory': used_memory,
                'used_memory_human': memory_stats.get('used_memory_human', '0B'),
                'max_memory': max_memory,
                'max_memory_human': memory_stats.get('maxmemory_human', '0B'),
                'memory_usage_percent': memory_usage_percent,
                'clients_connected': info.get('connected_clients', 0),
                'total_commands': info.get('total_commands_processed', 0),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(info),
                'evicted_keys': info.get('evicted_keys', 0),
                'expired_keys': info.get('expired_keys', 0),
                'db_keys': self._count_keys(info)
            }
            
            return stats
        except Exception as e:
            self.logger.error(f"Failed to collect Redis stats: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'is_connected': False,
                'error': str(e)
            }
            
    def _calculate_hit_rate(self, info: Dict[str, Any]) -> float:
        """캐시 히트율 계산"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0
        
    def _count_keys(self, info: Dict[str, Any]) -> Dict[str, int]:
        """데이터베이스별 키 개수 조회"""
        result = {}
        try:
            for key, value in info.items():
                if key.startswith('db'):
                    db_number = key[2:]  # 'db0' -> '0'
                    if isinstance(value, dict):
                        keys_count = value.get('keys', 0)
                    elif isinstance(value, str) and 'keys=' in value:
                        # 'keys=10,expires=0,avg_ttl=0' 형식 파싱
                        parts = value.split(',')
                        for part in parts:
                            if part.startswith('keys='):
                                keys_count = int(part.split('=')[1])
                                break
                    else:
                        keys_count = 0
                    result[db_number] = keys_count
        except Exception as e:
            self.logger.error(f"Failed to count keys: {e}")
        return result
        
    def _add_to_history(self, stats: Dict[str, Any]):
        """통계 기록에 추가"""
        self.stats_history.append(stats)
        if len(self.stats_history) > self.max_history:
            self.stats_history.pop(0)  # 가장 오래된 기록 제거
            
    def _check_memory_alerts(self, stats: Dict[str, Any]):
        """메모리 사용량 경고 확인"""
        if not stats.get('is_connected', False):
            return
            
        memory_percent = stats.get('memory_usage_percent', 0)
        
        # 메모리 사용량 경고
        if memory_percent > 90:
            message = f"CRITICAL: Redis memory usage at {memory_percent:.1f}%"
            self.logger.critical(message)
            
            # 이벤트 버스로 알림 발행
            if self.event_bus:
                event = self.event_bus.create_event(
                    EventType.RISK_ALERT,
                    'redis_monitor',
                    {
                        'level': 'critical',
                        'component': 'redis',
                        'message': message,
                        'memory_percent': memory_percent,
                        'timestamp': int(time.time())
                    }
                )
                self.event_bus.publish(event)
                
            # 자동 메모리 최적화 시도
            self.redis.optimize_memory()
            
        elif memory_percent > 75:
            message = f"WARNING: Redis memory usage at {memory_percent:.1f}%"
            self.logger.warning(message)
            
            # 이벤트 버스로 알림 발행
            if self.event_bus:
                event = self.event_bus.create_event(
                    EventType.RISK_ALERT,
                    'redis_monitor',
                    {
                        'level': 'warning',
                        'component': 'redis',
                        'message': message,
                        'memory_percent': memory_percent,
                        'timestamp': int(time.time())
                    }
                )
                self.event_bus.publish(event)
                
    def get_stats_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """특정 기간 동안의 통계 기록 조회"""
        if not self.stats_history:
            return []
            
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()
        
        return [stats for stats in self.stats_history 
                if stats.get('timestamp', '') >= cutoff_str]
                
    def get_memory_trend(self, hours: int = 24) -> List[Tuple[str, float]]:
        """메모리 사용량 추이 조회"""
        stats = self.get_stats_history(hours)
        return [(s['timestamp'], s.get('memory_usage_percent', 0)) for s in stats 
                if s.get('is_connected', False)]
                
    def get_hit_rate_trend(self, hours: int = 24) -> List[Tuple[str, float]]:
        """캐시 히트율 추이 조회"""
        stats = self.get_stats_history(hours)
        return [(s['timestamp'], s.get('hit_rate', 0)) for s in stats 
                if s.get('is_connected', False)]
                
    def get_key_distribution(self) -> Dict[str, int]:
        """키 패턴별 분포 조회"""
        patterns = [
            'market:*',
            'candles:*',
            'indicators:*',
            'orderbook:*',
            'trades:*'
        ]
        
        result = {}
        for pattern in patterns:
            keys = self.redis.get_keys_by_pattern(pattern)
            result[pattern] = len(keys)
            
        return result
        
    def get_key_memory_distribution(self) -> Dict[str, int]:
        """키 패턴별 메모리 사용량 조회"""
        patterns = [
            'market:*',
            'candles:*',
            'indicators:*',
            'orderbook:*',
            'trades:*'
        ]
        
        result = {}
        for pattern in patterns:
            memory_usage = self.redis.get_pattern_memory_usage(pattern)
            result[pattern] = sum(memory_usage.values())
            
        return result
        
    def get_status_summary(self) -> Dict[str, Any]:
        """Redis 상태 요약 조회"""
        stats = self.collect_stats()
        
        if not stats.get('is_connected', False):
            return {
                'status': 'disconnected',
                'timestamp': stats.get('timestamp')
            }
            
        # 상태 평가
        memory_percent = stats.get('memory_usage_percent', 0)
        if memory_percent > 90:
            status = 'critical'
        elif memory_percent > 75:
            status = 'warning'
        else:
            status = 'ok'
            
        return {
            'status': status,
            'timestamp': stats.get('timestamp'),
            'memory_usage_percent': memory_percent,
            'used_memory_human': stats.get('used_memory_human'),
            'max_memory_human': stats.get('max_memory_human'),
            'clients_connected': stats.get('clients_connected'),
            'hit_rate': stats.get('hit_rate'),
            'total_keys': sum(stats.get('db_keys', {}).values()),
            'uptime_days': stats.get('uptime_days')
        }