import unittest
import asyncio
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qb.utils.redis_manager import RedisManager
from qb.utils.redis_monitor import RedisMonitor
from qb.utils.event_bus import EventBus, EventType, Event


class TestRedisMonitor(unittest.TestCase):
    """RedisMonitor 동기 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.redis = RedisManager()
        self.event_bus = MagicMock(spec=EventBus)
        self.monitor = RedisMonitor(self.redis, self.event_bus)
        
    def test_collect_stats_connected(self):
        """연결된 상태에서 통계 수집 테스트"""
        stats = self.monitor.collect_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('is_connected', stats)
        self.assertIn('timestamp', stats)
        
        if stats['is_connected']:
            # 필수 필드 확인
            required_fields = [
                'redis_version', 'uptime_days', 'used_memory',
                'used_memory_human', 'memory_usage_percent',
                'clients_connected', 'total_commands',
                'keyspace_hits', 'keyspace_misses', 'hit_rate'
            ]
            for field in required_fields:
                self.assertIn(field, stats, f"Missing field: {field}")
    
    def test_collect_stats_disconnected(self):
        """연결 실패 시 통계 수집 테스트"""
        # Redis 연결 실패 시뮬레이션
        with patch.object(self.redis, 'ping', return_value=False):
            stats = self.monitor.collect_stats()
            
            self.assertFalse(stats['is_connected'])
            self.assertIn('timestamp', stats)
    
    def test_calculate_hit_rate(self):
        """캐시 히트율 계산 테스트"""
        # 케이스 1: 정상적인 경우
        info = {'keyspace_hits': 80, 'keyspace_misses': 20}
        hit_rate = self.monitor._calculate_hit_rate(info)
        self.assertEqual(hit_rate, 80.0)
        
        # 케이스 2: 모두 0인 경우
        info = {'keyspace_hits': 0, 'keyspace_misses': 0}
        hit_rate = self.monitor._calculate_hit_rate(info)
        self.assertEqual(hit_rate, 0.0)
        
        # 케이스 3: 100% 히트율
        info = {'keyspace_hits': 100, 'keyspace_misses': 0}
        hit_rate = self.monitor._calculate_hit_rate(info)
        self.assertEqual(hit_rate, 100.0)
    
    def test_count_keys(self):
        """키 개수 카운트 테스트"""
        # 문자열 형식 테스트
        info = {
            'db0': 'keys=10,expires=0,avg_ttl=0',
            'db1': 'keys=5,expires=2,avg_ttl=3600',
            'redis_version': '7.0.0'  # 다른 필드는 무시되어야 함
        }
        
        result = self.monitor._count_keys(info)
        self.assertEqual(result['0'], 10)
        self.assertEqual(result['1'], 5)
        self.assertNotIn('redis_version', result)
    
    def test_add_to_history(self):
        """통계 기록 추가 테스트"""
        # 기록 추가
        for i in range(5):
            stats = {'timestamp': f'2025-01-01T{i:02d}:00:00', 'value': i}
            self.monitor._add_to_history(stats)
        
        self.assertEqual(len(self.monitor.stats_history), 5)
        self.assertEqual(self.monitor.stats_history[0]['value'], 0)
        self.assertEqual(self.monitor.stats_history[4]['value'], 4)
        
        # 최대 개수 초과 테스트
        self.monitor.max_history = 3
        self.monitor.stats_history = []
        
        for i in range(5):
            stats = {'timestamp': f'2025-01-01T{i:02d}:00:00', 'value': i}
            self.monitor._add_to_history(stats)
        
        self.assertEqual(len(self.monitor.stats_history), 3)
        self.assertEqual(self.monitor.stats_history[0]['value'], 2)  # 오래된 것 제거
        self.assertEqual(self.monitor.stats_history[2]['value'], 4)
    
    def test_get_stats_history(self):
        """통계 기록 조회 테스트"""
        # 현재 시간 기준으로 테스트 데이터 생성
        now = datetime.now()
        
        # 다양한 시간대의 데이터 추가
        for i in range(48, -1, -12):  # 48, 36, 24, 12, 0 시간 전
            timestamp = (now - timedelta(hours=i)).isoformat()
            self.monitor._add_to_history({
                'timestamp': timestamp,
                'hour_ago': i
            })
        
        # 24시간 기록 조회
        history_24h = self.monitor.get_stats_history(24)
        
        # 24시간 이내 데이터만 포함되어야 함
        for stat in history_24h:
            self.assertLessEqual(stat['hour_ago'], 24)
    
    def test_get_key_distribution(self):
        """키 분포 조회 테스트"""
        # 테스트 데이터 생성
        test_data = {
            'market:BTC': 'test',
            'market:ETH': 'test',
            'candles:BTC:1m': 'test',
            'indicators:BTC': 'test'
        }
        
        for key, value in test_data.items():
            self.redis.redis.set(key.encode(), value.encode())
        
        # 키 분포 조회
        distribution = self.monitor.get_key_distribution()
        
        self.assertGreaterEqual(distribution.get('market:*', 0), 2)
        self.assertGreaterEqual(distribution.get('candles:*', 0), 1)
        self.assertGreaterEqual(distribution.get('indicators:*', 0), 1)
        
        # 정리
        for key in test_data.keys():
            self.redis.redis.delete(key.encode())
    
    def test_get_status_summary(self):
        """상태 요약 조회 테스트"""
        summary = self.monitor.get_status_summary()
        
        self.assertIn('status', summary)
        self.assertIn('timestamp', summary)
        
        if summary['status'] != 'disconnected':
            self.assertIn('memory_usage_percent', summary)
            self.assertIn('used_memory_human', summary)
            self.assertIn('hit_rate', summary)
            self.assertIn('total_keys', summary)


class TestRedisMonitorAsync(unittest.IsolatedAsyncioTestCase):
    """RedisMonitor 비동기 테스트"""
    
    async def asyncSetUp(self):
        """비동기 테스트 설정"""
        self.redis = RedisManager()
        self.event_bus = MagicMock(spec=EventBus)
        
        # create_event가 실제 Event 객체를 반환하도록 설정
        def mock_create_event(event_type, source, data, correlation_id=None):
            return Event(
                event_type=event_type,
                source=source,
                timestamp=datetime.now(),
                data=data,
                correlation_id=correlation_id
            )
        
        self.event_bus.create_event.side_effect = mock_create_event
        self.monitor = RedisMonitor(self.redis, self.event_bus)
    
    async def test_monitoring_loop(self):
        """모니터링 루프 테스트"""
        # 짧은 간격으로 모니터링 시작
        await self.monitor.start_monitoring(interval_seconds=0.1)
        
        # 0.3초 대기 (최소 3회 실행)
        await asyncio.sleep(0.3)
        
        # 모니터링 중지
        await self.monitor.stop_monitoring()
        
        # 통계 기록 확인
        self.assertGreater(len(self.monitor.stats_history), 0)
        
        # 이벤트 발행 확인
        self.event_bus.publish.assert_called()
        
        # SYSTEM_STATUS 이벤트 발행 확인
        calls = self.event_bus.publish.call_args_list
        system_status_events = any(
            call[0][0].event_type.value == 'system_status'
            for call in calls
        )
        self.assertTrue(system_status_events)
    
    async def test_memory_alerts_warning(self):
        """메모리 경고 알림 테스트"""
        # 높은 메모리 사용량 모의
        with patch.object(self.monitor, 'collect_stats') as mock_collect:
            mock_collect.return_value = {
                'is_connected': True,
                'timestamp': datetime.now().isoformat(),
                'memory_usage_percent': 80,  # 경고 레벨
                'used_memory_human': '80MB',
                'max_memory_human': '100MB',
                'clients_connected': 1
            }
            
            await self.monitor.start_monitoring(interval_seconds=0.1)
            await asyncio.sleep(0.15)
            await self.monitor.stop_monitoring()
            
            # RISK_ALERT 이벤트 확인
            risk_alerts = [
                call for call in self.event_bus.publish.call_args_list
                if call[0][0].event_type.value == 'risk_alert'
            ]
            
            self.assertGreater(len(risk_alerts), 0)
            
            # 경고 레벨 확인
            alert_event = risk_alerts[0][0][0]
            self.assertEqual(alert_event.data['level'], 'warning')
    
    async def test_memory_alerts_critical(self):
        """메모리 위험 알림 및 자동 최적화 테스트"""
        # 매우 높은 메모리 사용량 모의
        with patch.object(self.monitor, 'collect_stats') as mock_collect:
            mock_collect.return_value = {
                'is_connected': True,
                'timestamp': datetime.now().isoformat(),
                'memory_usage_percent': 95,  # 위험 레벨
                'used_memory_human': '95MB',
                'max_memory_human': '100MB',
                'clients_connected': 1
            }
            
            # optimize_memory 모의
            with patch.object(self.redis, 'optimize_memory') as mock_optimize:
                await self.monitor.start_monitoring(interval_seconds=0.1)
                await asyncio.sleep(0.15)
                await self.monitor.stop_monitoring()
                
                # 자동 최적화 호출 확인
                mock_optimize.assert_called()
                
                # RISK_ALERT 이벤트 확인
                risk_alerts = [
                    call for call in self.event_bus.publish.call_args_list
                    if call[0][0].event_type.value == 'risk_alert'
                ]
                
                self.assertGreater(len(risk_alerts), 0)
                
                # 위험 레벨 확인
                alert_event = risk_alerts[0][0][0]
                self.assertEqual(alert_event.data['level'], 'critical')
    
    async def test_start_stop_monitoring(self):
        """모니터링 시작/중지 테스트"""
        # 시작
        await self.monitor.start_monitoring(interval_seconds=0.1)
        self.assertTrue(self.monitor.running)
        self.assertIsNotNone(self.monitor.monitor_task)
        
        # 중복 시작 방지
        await self.monitor.start_monitoring(interval_seconds=0.1)
        
        # 중지
        await self.monitor.stop_monitoring()
        self.assertFalse(self.monitor.running)
        
        # 중복 중지 방지
        await self.monitor.stop_monitoring()
    
    async def test_monitoring_error_handling(self):
        """모니터링 에러 처리 테스트"""
        # collect_stats 에러 발생 시뮬레이션
        with patch.object(self.monitor, 'collect_stats') as mock_collect:
            mock_collect.side_effect = Exception("Test error")
            
            await self.monitor.start_monitoring(interval_seconds=0.1)
            await asyncio.sleep(0.15)
            await self.monitor.stop_monitoring()
            
            # 에러 발생해도 계속 실행되어야 함
            self.assertGreater(mock_collect.call_count, 1)


class TestRedisMonitorIntegration(unittest.TestCase):
    """통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.redis = RedisManager()
        self.monitor = RedisMonitor(self.redis)
    
    def test_memory_trend(self):
        """메모리 사용량 추이 테스트"""
        # 테스트 데이터 추가
        now = datetime.now()
        for i in range(5):
            timestamp = (now - timedelta(hours=i)).isoformat()
            self.monitor._add_to_history({
                'timestamp': timestamp,
                'is_connected': True,
                'memory_usage_percent': 50 + i * 5
            })
        
        # 추이 조회
        trend = self.monitor.get_memory_trend(hours=24)
        
        self.assertEqual(len(trend), 5)
        for timestamp, percent in trend:
            self.assertIsInstance(timestamp, str)
            self.assertIsInstance(percent, (int, float))
    
    def test_hit_rate_trend(self):
        """캐시 히트율 추이 테스트"""
        # 테스트 데이터 추가
        now = datetime.now()
        for i in range(5):
            timestamp = (now - timedelta(hours=i)).isoformat()
            self.monitor._add_to_history({
                'timestamp': timestamp,
                'is_connected': True,
                'hit_rate': 70 + i * 2
            })
        
        # 추이 조회
        trend = self.monitor.get_hit_rate_trend(hours=24)
        
        self.assertEqual(len(trend), 5)
        for timestamp, rate in trend:
            self.assertIsInstance(timestamp, str)
            self.assertIsInstance(rate, (int, float))


if __name__ == '__main__':
    unittest.main()