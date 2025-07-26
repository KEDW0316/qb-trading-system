import unittest
import json
import time
from unittest.mock import Mock, MagicMock, patch
from qb.analysis.cache_manager import IndicatorCacheManager


class TestIndicatorCacheManager(unittest.TestCase):
    """IndicatorCacheManager 단위 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # Redis 클라이언트 모킹
        self.mock_redis = MagicMock()
        self.mock_redis_manager = Mock()
        self.mock_redis_manager.redis = self.mock_redis
        
        self.cache_manager = IndicatorCacheManager(
            self.mock_redis_manager, 
            default_expiry=3600
        )
        
    def test_cache_indicator(self):
        """지표 캐싱 테스트"""
        symbol = "005930"
        indicator_name = "rsi"
        value = 65.5
        timeframe = "1m"
        
        # 캐싱 실행
        self.cache_manager.cache_indicator(symbol, indicator_name, value, timeframe=timeframe)
        
        # Redis 호출 확인
        expected_key = f"indicators:{symbol}:{timeframe}"
        self.mock_redis.hset.assert_called_once()
        self.mock_redis.expire.assert_called_once_with(expected_key, 3600)
        
        # 통계 업데이트 확인
        self.assertEqual(self.cache_manager.stats['sets'], 1)
        
    def test_get_cached_indicator(self):
        """캐시된 지표 조회 테스트"""
        symbol = "005930"
        indicator_name = "rsi"
        timeframe = "1m"
        
        # 캐시된 데이터 모킹
        cached_data = {
            'value': 65.5,
            'timestamp': time.time(),
            'expiry': 3600,
            'params': {}
        }
        self.mock_redis.hget.return_value = json.dumps(cached_data)
        
        # 조회 실행
        result = self.cache_manager.get_cached_indicator(symbol, indicator_name, timeframe=timeframe)
        
        # 결과 확인
        self.assertEqual(result, 65.5)
        self.assertEqual(self.cache_manager.stats['hits'], 1)
        
    def test_cache_miss(self):
        """캐시 미스 테스트"""
        symbol = "005930"
        indicator_name = "rsi"
        timeframe = "1m"
        
        # 캐시 없음
        self.mock_redis.hget.return_value = None
        
        # 조회 실행
        result = self.cache_manager.get_cached_indicator(symbol, indicator_name, timeframe=timeframe)
        
        # 결과 확인
        self.assertIsNone(result)
        self.assertEqual(self.cache_manager.stats['misses'], 1)
        
    def test_expired_cache(self):
        """만료된 캐시 테스트"""
        symbol = "005930"
        indicator_name = "rsi"
        timeframe = "1m"
        
        # 만료된 캐시 데이터
        cached_data = {
            'value': 65.5,
            'timestamp': time.time() - 7200,  # 2시간 전
            'expiry': 3600,  # 1시간 TTL
            'params': {}
        }
        self.mock_redis.hget.return_value = json.dumps(cached_data)
        
        # 조회 실행
        result = self.cache_manager.get_cached_indicator(symbol, indicator_name, timeframe=timeframe)
        
        # 결과 확인 (만료되어 None 반환)
        self.assertIsNone(result)
        self.assertEqual(self.cache_manager.stats['misses'], 1)
        
        # 만료된 캐시 삭제 확인
        self.mock_redis.hdel.assert_called_once()
        
    def test_cache_all_indicators(self):
        """모든 지표 캐싱 테스트"""
        symbol = "005930"
        timeframe = "1m"
        indicators = {
            'rsi': 65.5,
            'sma_20': 50000,
            'macd': 150.2
        }
        
        # 캐싱 실행
        self.cache_manager.cache_all_indicators(symbol, indicators, timeframe)
        
        # Redis 호출 확인
        expected_key = f"indicators:{symbol}:{timeframe}"
        self.mock_redis.hset.assert_called_once_with(
            expected_key, 
            'all_indicators',
            unittest.mock.ANY  # JSON 문자열
        )
        self.mock_redis.expire.assert_called_once_with(expected_key, 3600)
        
    def test_get_all_cached_indicators(self):
        """모든 캐시된 지표 조회 테스트"""
        symbol = "005930"
        timeframe = "1m"
        
        indicators = {
            'rsi': 65.5,
            'sma_20': 50000,
            'macd': 150.2
        }
        
        cached_data = {
            'indicators': indicators,
            'timestamp': time.time(),
            'expiry': 3600
        }
        self.mock_redis.hget.return_value = json.dumps(cached_data)
        
        # 조회 실행
        result = self.cache_manager.get_all_cached_indicators(symbol, timeframe)
        
        # 결과 확인
        self.assertEqual(result, indicators)
        self.assertEqual(self.cache_manager.stats['hits'], 1)
        
    def test_invalidate_cache(self):
        """캐시 무효화 테스트"""
        symbol = "005930"
        timeframe = "1m"
        
        self.mock_redis.delete.return_value = 1
        
        # 캐시 무효화 실행
        self.cache_manager.invalidate_cache(symbol, timeframe)
        
        # Redis 호출 확인
        expected_key = f"indicators:{symbol}:{timeframe}"
        self.mock_redis.delete.assert_called_once_with(expected_key)
        self.assertEqual(self.cache_manager.stats['invalidations'], 1)
        
    def test_build_cache_key(self):
        """캐시 키 생성 테스트"""
        # 파라미터 없는 경우
        key = self.cache_manager._build_cache_key("005930", "rsi")
        self.assertEqual(key, "rsi")
        
        # 파라미터 있는 경우
        params = {'period': 14, 'source': 'close'}
        key = self.cache_manager._build_cache_key("005930", "rsi", params)
        self.assertEqual(key, "rsi_period:14_source:close")
        
        # 긴 키의 경우 해시 사용
        long_params = {f'param_{i}': f'value_{i}' for i in range(20)}
        key = self.cache_manager._build_cache_key("005930", "custom_indicator", long_params)
        self.assertTrue(key.startswith("custom_indicator_"))
        self.assertEqual(len(key), len("custom_indicator_") + 16)  # 해시 길이
        
    def test_cache_stats(self):
        """캐시 통계 테스트"""
        # 초기 상태
        stats = self.cache_manager.get_cache_stats()
        self.assertEqual(stats['hits'], 0)
        self.assertEqual(stats['misses'], 0)
        self.assertEqual(stats['hit_rate_percent'], 0)
        
        # 히트와 미스 시뮬레이션
        self.cache_manager.stats['hits'] = 8
        self.cache_manager.stats['misses'] = 2
        
        stats = self.cache_manager.get_cache_stats()
        self.assertEqual(stats['hits'], 8)
        self.assertEqual(stats['misses'], 2)
        self.assertEqual(stats['total_requests'], 10)
        self.assertEqual(stats['hit_rate_percent'], 80.0)
        
    def test_reset_stats(self):
        """통계 초기화 테스트"""
        # 통계 설정
        self.cache_manager.stats['hits'] = 10
        self.cache_manager.stats['misses'] = 5
        
        # 초기화
        self.cache_manager.reset_stats()
        
        # 확인
        self.assertEqual(self.cache_manager.stats['hits'], 0)
        self.assertEqual(self.cache_manager.stats['misses'], 0)
        
    def test_cache_size_info(self):
        """캐시 크기 정보 테스트"""
        symbol = "005930"
        
        # Redis keys와 memory_usage 모킹
        self.mock_redis.keys.return_value = [
            b'indicators:005930:1m',
            b'indicators:005930:5m'
        ]
        self.mock_redis.memory_usage.side_effect = [1024, 2048]
        
        # 크기 정보 조회
        size_info = self.cache_manager.get_cache_size_info(symbol)
        
        # 결과 확인
        self.assertEqual(size_info['total_keys'], 2)
        self.assertEqual(size_info['total_memory_bytes'], 3072)
        self.assertEqual(size_info['total_memory_mb'], 0.0)  # 반올림으로 0.0
        
    def test_error_handling(self):
        """에러 처리 테스트"""
        symbol = "005930"
        indicator_name = "rsi"
        
        # Redis 에러 시뮬레이션
        self.mock_redis.hget.side_effect = Exception("Redis connection error")
        
        # 조회 시 에러가 발생해도 None 반환하고 미스로 카운트
        result = self.cache_manager.get_cached_indicator(symbol, indicator_name)
        self.assertIsNone(result)
        self.assertEqual(self.cache_manager.stats['misses'], 1)
        
    def test_json_serialization(self):
        """JSON 직렬화 테스트"""
        symbol = "005930"
        indicator_name = "rsi"
        
        # 복잡한 데이터 구조
        complex_value = {
            'main_value': 65.5,
            'sub_values': [1, 2, 3],
            'metadata': {'calculated_at': '2025-01-01T10:00:00'}
        }
        
        # 캐싱
        self.cache_manager.cache_indicator(symbol, indicator_name, complex_value)
        
        # hset 호출 시 JSON 문자열이 전달되었는지 확인
        call_args = self.mock_redis.hset.call_args
        json_data = call_args[0][2]  # 세 번째 인자가 JSON 데이터
        
        # JSON 파싱 가능한지 확인
        parsed_data = json.loads(json_data)
        self.assertEqual(parsed_data['value'], complex_value)


if __name__ == '__main__':
    unittest.main()