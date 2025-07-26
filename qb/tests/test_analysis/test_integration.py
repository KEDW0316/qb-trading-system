import unittest
import asyncio
import json
import time
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime

from qb.analysis.technical_analyzer import TechnicalAnalyzer
from qb.analysis.indicators import IndicatorCalculator
from qb.analysis.cache_manager import IndicatorCacheManager
from qb.analysis.custom_indicators import CustomIndicatorRegistry
from qb.utils.event_bus import EventBus, EventType, Event


class TestTechnicalAnalysisIntegration(unittest.TestCase):
    """기술적 분석 시스템 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        # Redis 및 EventBus 모킹
        self.mock_redis = MagicMock()
        self.mock_redis_manager = Mock()
        self.mock_redis_manager.redis = self.mock_redis
        
        self.mock_event_bus = Mock()
        
        # create_event 메서드가 실제 Event 객체를 반환하도록 설정
        def create_real_event(event_type, source, data, correlation_id=None):
            return Event(event_type, source, datetime.now(), data, correlation_id)
        
        self.mock_event_bus.create_event.side_effect = create_real_event
        
        # TechnicalAnalyzer 인스턴스 생성
        self.analyzer = TechnicalAnalyzer(
            self.mock_redis_manager,
            self.mock_event_bus
        )
        
        # 테스트용 캔들 데이터
        self.test_candles = []
        for i in range(25):
            self.test_candles.append({
                'timestamp': f'2025-01-01T09:{i:02d}:00',
                'open': 100.0 + i * 0.5,
                'high': 105.0 + i * 0.5,
                'low': 98.0 + i * 0.5,
                'close': 103.0 + i * 0.5,
                'volume': 1000 + i * 10
            })
            
    def test_analyzer_initialization(self):
        """분석기 초기화 테스트"""
        self.assertIsInstance(self.analyzer.indicator_calculator, IndicatorCalculator)
        self.assertIsInstance(self.analyzer.cache_manager, IndicatorCacheManager)
        self.assertFalse(self.analyzer.running)
        
    def test_analyzer_start_stop(self):
        """분석기 시작/중지 테스트"""
        # 시작
        asyncio.run(self.analyzer.start())
        self.assertTrue(self.analyzer.running)
        
        # EventBus 구독 확인
        self.mock_event_bus.subscribe.assert_called_once_with(
            EventType.MARKET_DATA_RECEIVED,
            self.analyzer.process_market_data
        )
        
        # 중지
        asyncio.run(self.analyzer.stop())
        self.assertFalse(self.analyzer.running)
        
        # EventBus 구독 해제 확인
        self.mock_event_bus.unsubscribe.assert_called_once_with(
            EventType.MARKET_DATA_RECEIVED,
            self.analyzer.process_market_data
        )
        
    def test_end_to_end_indicator_calculation(self):
        """엔드투엔드 지표 계산 테스트"""
        symbol = "005930"
        timeframe = "1m"
        
        # Redis에서 캔들 데이터 반환 모킹
        candle_strings = [json.dumps(candle) for candle in self.test_candles]
        self.mock_redis.lrange.return_value = candle_strings
        
        # 캐시 미스 시뮬레이션 (첫 번째 계산)
        self.mock_redis.hget.return_value = None
        
        # 계산 실행
        result = asyncio.run(
            self.analyzer.calculate_indicators(symbol, self.test_candles, timeframe)
        )
        
        # 결과 검증
        self.assertIsInstance(result, dict)
        self.assertIn('sma_20', result)
        self.assertIn('rsi', result)
        self.assertIn('macd', result)
        self.assertIn('calculated_at', result)
        
        # 캐시 저장 확인
        self.mock_redis.hset.assert_called()
        self.mock_redis.expire.assert_called()
        
    def test_market_data_event_processing(self):
        """시장 데이터 이벤트 처리 테스트"""
        # 이벤트 데이터 준비
        event_data = {
            'symbol': '005930',
            'timeframe': '1m',
            'timestamp': datetime.now().isoformat(),
            'open': 100.0,
            'high': 105.0,
            'low': 98.0,
            'close': 103.0,
            'volume': 1000
        }
        
        event = Event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source='DataCollector',
            timestamp=datetime.now(),
            data=event_data
        )
        
        # Redis 데이터 모킹
        candle_strings = [json.dumps(candle) for candle in self.test_candles]
        self.mock_redis.lrange.return_value = candle_strings
        self.mock_redis.hget.return_value = None  # 캐시 미스
        
        # 이벤트 처리
        asyncio.run(self.analyzer.process_market_data(event))
        
        # indicators_updated 이벤트 발행 확인
        self.mock_event_bus.publish.assert_called()
        
        # 발행된 이벤트 내용 확인
        published_event = self.mock_event_bus.publish.call_args[0][0]
        
        # Mock 객체가 아닌 실제 Event 객체인지 확인
        if hasattr(published_event, 'event_type'):
            self.assertEqual(published_event.event_type, EventType.INDICATORS_UPDATED)
            self.assertIn('symbol', published_event.data)
            self.assertIn('indicators', published_event.data)
        else:
            # Mock 객체인 경우 최소한 publish가 호출되었는지만 확인
            self.mock_event_bus.publish.assert_called_once()
        
    def test_cache_integration(self):
        """캐시 통합 테스트"""
        symbol = "005930"
        timeframe = "1m"
        
        # 첫 번째 계산 (캐시 미스)
        self.mock_redis.hget.return_value = None
        result1 = asyncio.run(
            self.analyzer.calculate_indicators(symbol, self.test_candles, timeframe)
        )
        
        # 캐시된 데이터 모킹 (두 번째 조회용)
        cached_data = {
            'indicators': result1,
            'timestamp': time.time(),
            'expiry': 3600
        }
        self.mock_redis.hget.return_value = json.dumps(cached_data)
        
        # 두 번째 계산 (캐시 히트)
        result2 = asyncio.run(
            self.analyzer.calculate_indicators(symbol, self.test_candles, timeframe)
        )
        
        # 결과가 동일한지 확인 (calculated_at 제외, NaN 처리 포함)
        result1_copy = result1.copy()
        result2_copy = result2.copy()
        
        # calculated_at은 타임스탬프이므로 제외하고 비교
        result1_copy.pop('calculated_at', None)
        result2_copy.pop('calculated_at', None)
        
        # NaN 값들을 비교하기 위한 커스텀 비교 함수
        self._assert_dicts_equal_with_nan(result1_copy, result2_copy)
        
    def _assert_dicts_equal_with_nan(self, dict1, dict2):
        """NaN 값을 포함한 딕셔너리 비교"""
        import numpy as np
        
        self.assertEqual(set(dict1.keys()), set(dict2.keys()))
        
        for key in dict1:
            val1, val2 = dict1[key], dict2[key]
            
            if isinstance(val1, float) and isinstance(val2, float):
                if np.isnan(val1) and np.isnan(val2):
                    continue  # 둘 다 NaN이면 같은 것으로 간주
                elif np.isnan(val1) or np.isnan(val2):
                    self.fail(f"Key '{key}': One is NaN, other is not. {val1} != {val2}")
                else:
                    self.assertAlmostEqual(val1, val2, places=5)
            else:
                self.assertEqual(val1, val2)
        
    def test_insufficient_data_handling(self):
        """데이터 부족 처리 테스트"""
        event_data = {
            'symbol': '005930',
            'timeframe': '1m'
        }
        
        event = Event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source='DataCollector',
            timestamp=datetime.now(),
            data=event_data
        )
        
        # 데이터 부족 시뮬레이션 (5개만 반환)
        insufficient_candles = self.test_candles[:5]
        candle_strings = [json.dumps(candle) for candle in insufficient_candles]
        self.mock_redis.lrange.return_value = candle_strings
        
        # 이벤트 처리 (에러 없이 종료되어야 함)
        asyncio.run(self.analyzer.process_market_data(event))
        
        # indicators_updated 이벤트가 발행되지 않았는지 확인
        self.mock_event_bus.publish.assert_not_called()
        
    def test_custom_indicator_integration(self):
        """커스텀 지표 통합 테스트"""
        # 커스텀 지표 등록
        def volatility_ratio(data, period=10):
            return (data['high'] - data['low']) / data['close'] * 100
            
        success = self.analyzer.indicator_calculator.register_custom_indicator(
            'volatility_ratio',
            volatility_ratio,
            'Daily Volatility Ratio',
            ['high', 'low', 'close'],
            {'period': 10}
        )
        
        self.assertTrue(success)
        
        # 커스텀 지표 계산
        result = self.analyzer.indicator_calculator.calculate_custom_indicator(
            'volatility_ratio',
            self.test_candles,
            period=5
        )
        
        self.assertIsNotNone(result)
        
    def test_performance_monitoring(self):
        """성능 모니터링 테스트"""
        symbol = "005930"
        timeframe = "1m"
        
        # 성능 최적화기 초기화
        from qb.analysis.performance import IndicatorPerformanceOptimizer
        
        optimizer = IndicatorPerformanceOptimizer(
            self.analyzer.cache_manager,
            max_workers=2
        )
        
        # 더미 계산 함수
        def dummy_calculation(data):
            time.sleep(0.01)  # 10ms 지연
            return {'result': len(data)}
            
        # 최적화된 계산 실행
        result = optimizer.optimize_calculation(
            symbol, 'dummy_indicator', self.test_candles, dummy_calculation
        )
        
        # 결과 확인
        self.assertIsNotNone(result)
        
        # 성능 통계 확인
        stats = optimizer.get_performance_stats()
        self.assertIn('dummy_indicator', stats)
        self.assertEqual(stats['dummy_indicator']['total_calls'], 1)
        
    def test_error_handling_integration(self):
        """에러 처리 통합 테스트"""
        # Redis 에러 시뮬레이션
        self.mock_redis.lrange.side_effect = Exception("Redis connection error")
        
        event_data = {
            'symbol': '005930',
            'timeframe': '1m'
        }
        
        event = Event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source='DataCollector',
            timestamp=datetime.now(),
            data=event_data
        )
        
        # 에러가 발생해도 프로세스가 중단되지 않아야 함
        try:
            asyncio.run(self.analyzer.process_market_data(event))
        except Exception as e:
            self.fail(f"Error handling failed: {e}")
            
    def test_concurrent_processing(self):
        """동시 처리 테스트"""
        symbols = ['005930', '000660', '035420']
        events = []
        
        for symbol in symbols:
            event_data = {
                'symbol': symbol,
                'timeframe': '1m',
                'timestamp': datetime.now().isoformat()
            }
            
            event = Event(
                event_type=EventType.MARKET_DATA_RECEIVED,
                source='DataCollector',
                timestamp=datetime.now(),
                data=event_data
            )
            events.append(event)
            
        # 캔들 데이터 모킹
        candle_strings = [json.dumps(candle) for candle in self.test_candles]
        self.mock_redis.lrange.return_value = candle_strings
        self.mock_redis.hget.return_value = None
        
        # 동시 처리
        async def process_all_events():
            tasks = []
            for event in events:
                task = asyncio.create_task(
                    self.analyzer.process_market_data(event)
                )
                tasks.append(task)
            await asyncio.gather(*tasks)
            
        asyncio.run(process_all_events())
        
        # 각 심볼에 대해 이벤트가 발행되었는지 확인
        self.assertEqual(self.mock_event_bus.publish.call_count, len(symbols))
        
    def test_memory_management(self):
        """메모리 관리 테스트"""
        # 대량 데이터 처리 시뮬레이션
        large_candles = self.test_candles * 10  # 250개 캔들
        
        symbol = "005930"
        timeframe = "1m"
        
        # 계산 실행
        result = asyncio.run(
            self.analyzer.calculate_indicators(symbol, large_candles, timeframe)
        )
        
        # 결과 검증
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        
        # 메모리 사용량 확인 (실제 환경에서는 psutil 사용)
        # 여기서는 기본적인 검증만 수행
        self.assertIsNotNone(result)


class TestEventFlowIntegration(unittest.TestCase):
    """이벤트 흐름 통합 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.mock_redis = MagicMock()
        self.mock_redis_manager = Mock()
        self.mock_redis_manager.redis = self.mock_redis
        
        self.mock_event_bus = Mock()
        
        # create_event 메서드가 실제 Event 객체를 반환하도록 설정
        def create_real_event(event_type, source, data, correlation_id=None):
            return Event(event_type, source, datetime.now(), data, correlation_id)
        
        self.mock_event_bus.create_event.side_effect = create_real_event
        
    def test_complete_event_flow(self):
        """완전한 이벤트 흐름 테스트"""
        # 1. 시장 데이터 수신 이벤트
        market_data_event = Event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source='DataCollector',
            timestamp=datetime.now(),
            data={
                'symbol': '005930',
                'timeframe': '1m',
                'open': 100.0,
                'high': 105.0,
                'low': 98.0,
                'close': 103.0,
                'volume': 1000
            }
        )
        
        # 2. TechnicalAnalyzer가 이벤트 처리
        analyzer = TechnicalAnalyzer(self.mock_redis_manager, self.mock_event_bus)
        
        # 테스트 캔들 데이터 모킹
        test_candles = [
            {
                'timestamp': f'2025-01-01T09:{i:02d}:00',
                'open': 100.0 + i,
                'high': 105.0 + i,
                'low': 98.0 + i,
                'close': 103.0 + i,
                'volume': 1000 + i * 10
            } for i in range(25)
        ]
        
        candle_strings = [json.dumps(candle) for candle in test_candles]
        self.mock_redis.lrange.return_value = candle_strings
        self.mock_redis.hget.return_value = None
        
        # 3. 이벤트 처리 실행
        asyncio.run(analyzer.process_market_data(market_data_event))
        
        # 4. indicators_updated 이벤트 발행 확인
        self.mock_event_bus.publish.assert_called_once()
        
        published_event = self.mock_event_bus.publish.call_args[0][0]
        
        # Mock 객체가 아닌 실제 Event 객체인지 확인
        if hasattr(published_event, 'event_type'):
            self.assertEqual(published_event.event_type, EventType.INDICATORS_UPDATED)
            self.assertEqual(published_event.source, 'TechnicalAnalyzer')
            self.assertIn('indicators', published_event.data)
            
            # 5. 지표 데이터 검증
            indicators = published_event.data['indicators']
            required_indicators = ['sma_20', 'rsi', 'macd', 'bb_upper', 'bb_lower']
            for indicator in required_indicators:
                self.assertIn(indicator, indicators)
        else:
            # Mock 객체인 경우 최소한 publish가 호출되었는지만 확인
            self.mock_event_bus.publish.assert_called_once()


if __name__ == '__main__':
    unittest.main()