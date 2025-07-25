import unittest
import json
import numpy as np
import pandas as pd
from datetime import datetime, date
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qb.utils.serialization import (
    DataSerializer, SerializationFormat, CompressionAlgorithm,
    serialize_for_redis, deserialize_from_redis, get_optimal_compression
)


class TestDataSerializer(unittest.TestCase):
    """DataSerializer 클래스 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.serializer = DataSerializer()
    
    def test_json_serialization_basic_types(self):
        """기본 타입 JSON 직렬화/역직렬화 테스트"""
        test_data = {
            'string': 'hello world',
            'number': 42,
            'float': 3.14159,
            'boolean': True,
            'null': None,
            'list': [1, 2, 3],
            'dict': {'nested': 'value'}
        }
        
        serialized = self.serializer.serialize(test_data, format=SerializationFormat.JSON)
        deserialized = self.serializer.deserialize(serialized)
        
        self.assertEqual(test_data, deserialized)
    
    def test_numpy_serialization(self):
        """NumPy 배열 직렬화/역직렬화 테스트"""
        # 1D 배열
        arr1d = np.array([1, 2, 3, 4, 5])
        serialized = self.serializer.serialize(arr1d, format=SerializationFormat.JSON)
        deserialized = self.serializer.deserialize(serialized)
        np.testing.assert_array_equal(arr1d, deserialized)
        
        # 2D 배열
        arr2d = np.array([[1, 2, 3], [4, 5, 6]])
        serialized = self.serializer.serialize(arr2d, format=SerializationFormat.JSON)
        deserialized = self.serializer.deserialize(serialized)
        np.testing.assert_array_equal(arr2d, deserialized)
        
        # 다양한 dtype
        arr_float = np.array([1.1, 2.2, 3.3], dtype=np.float32)
        serialized = self.serializer.serialize(arr_float, format=SerializationFormat.JSON)
        deserialized = self.serializer.deserialize(serialized)
        np.testing.assert_array_equal(arr_float, deserialized)
    
    def test_pandas_serialization(self):
        """Pandas DataFrame/Series 직렬화/역직렬화 테스트"""
        # DataFrame
        df = pd.DataFrame({
            'A': [1, 2, 3],
            'B': [4.0, 5.0, 6.0],
            'C': ['x', 'y', 'z']
        })
        serialized = self.serializer.serialize(df, format=SerializationFormat.JSON)
        deserialized = self.serializer.deserialize(serialized)
        pd.testing.assert_frame_equal(df, deserialized)
        
        # Series
        series = pd.Series([1, 2, 3], index=['a', 'b', 'c'], name='test_series')
        serialized = self.serializer.serialize(series, format=SerializationFormat.JSON)
        deserialized = self.serializer.deserialize(serialized)
        pd.testing.assert_series_equal(series, deserialized)
    
    def test_datetime_serialization(self):
        """날짜/시간 타입 직렬화/역직렬화 테스트"""
        now = datetime.now()
        today = date.today()
        
        test_data = {
            'datetime': now,
            'date': today
        }
        
        serialized = self.serializer.serialize(test_data, format=SerializationFormat.JSON)
        deserialized = self.serializer.deserialize(serialized)
        
        self.assertEqual(test_data['datetime'].isoformat(), deserialized['datetime'].isoformat())
        self.assertEqual(test_data['date'], deserialized['date'])
    
    def test_bytes_serialization(self):
        """바이트 데이터 직렬화/역직렬화 테스트"""
        test_bytes = b'hello world in bytes'
        
        serialized = self.serializer.serialize(test_bytes, format=SerializationFormat.JSON)
        deserialized = self.serializer.deserialize(serialized)
        
        self.assertEqual(test_bytes, deserialized)
    
    def test_compression_algorithms(self):
        """다양한 압축 알고리즘 테스트"""
        test_data = {
            'data': ['item'] * 1000,  # 반복 데이터로 압축 효과 극대화
            'numbers': list(range(1000))
        }
        
        for algo in [CompressionAlgorithm.ZLIB, CompressionAlgorithm.LZ4, CompressionAlgorithm.SNAPPY]:
            with self.subTest(algorithm=algo):
                serialized = self.serializer.serialize(
                    test_data, 
                    format=SerializationFormat.JSON,
                    compression=algo
                )
                deserialized = self.serializer.deserialize(serialized)
                self.assertEqual(test_data, deserialized)
    
    def test_pickle_serialization(self):
        """Pickle 직렬화 테스트"""
        # Pickle은 복잡한 객체를 지원하므로 딕셔너리와 리스트로 테스트
        complex_data = {
            'value': 42,
            'arr': np.array([1, 2, 3]),
            'nested': {
                'list': [1, 2, 3, 4, 5],
                'tuple': (10, 20, 30),
                'set': {100, 200, 300}
            }
        }
        
        serialized = self.serializer.serialize(complex_data, format=SerializationFormat.PICKLE)
        deserialized = self.serializer.deserialize(serialized)
        
        self.assertEqual(complex_data['value'], deserialized['value'])
        np.testing.assert_array_equal(complex_data['arr'], deserialized['arr'])
        self.assertEqual(complex_data['nested']['list'], deserialized['nested']['list'])
        self.assertEqual(complex_data['nested']['tuple'], deserialized['nested']['tuple'])
        self.assertEqual(complex_data['nested']['set'], deserialized['nested']['set'])
    
    def test_compression_ratio(self):
        """압축률 계산 테스트"""
        # 반복적인 데이터 (높은 압축률)
        repetitive_data = {'data': ['same_value'] * 1000}
        
        stats = self.serializer.get_compression_ratio(
            repetitive_data,
            format=SerializationFormat.JSON,
            compression=CompressionAlgorithm.ZLIB
        )
        
        self.assertIn('original_size', stats)
        self.assertIn('compressed_size', stats)
        self.assertIn('compression_ratio', stats)
        self.assertGreater(stats['compression_ratio'], 80)  # 80% 이상 압축
    
    def test_mixed_data_types(self):
        """혼합 데이터 타입 직렬화 테스트"""
        mixed_data = {
            'market_data': {
                'symbol': 'BTCUSDT',
                'prices': np.array([50000, 50100, 50200]),
                'timestamps': [datetime.now() for _ in range(3)],
                'volume': pd.Series([100, 200, 300])
            },
            'indicators': {
                'sma': np.array([50050, 50100, 50150]),
                'rsi': 65.5,
                'macd': {'line': 100, 'signal': 95, 'histogram': 5}
            },
            'metadata': {
                'updated_at': datetime.now(),
                'version': 1,
                'raw_data': b'binary_data_here'
            }
        }
        
        # 모든 압축 알고리즘으로 테스트
        for compression in CompressionAlgorithm:
            with self.subTest(compression=compression):
                serialized = self.serializer.serialize(
                    mixed_data, 
                    compression=compression
                )
                deserialized = self.serializer.deserialize(serialized)
                
                # 각 요소별 검증
                self.assertEqual(
                    mixed_data['market_data']['symbol'], 
                    deserialized['market_data']['symbol']
                )
                np.testing.assert_array_equal(
                    mixed_data['market_data']['prices'],
                    deserialized['market_data']['prices']
                )
                pd.testing.assert_series_equal(
                    mixed_data['market_data']['volume'],
                    deserialized['market_data']['volume']
                )
                self.assertEqual(
                    mixed_data['metadata']['raw_data'],
                    deserialized['metadata']['raw_data']
                )
    
    def test_helper_functions(self):
        """헬퍼 함수 테스트"""
        # 압축 효과가 있는 충분히 큰 데이터 사용
        test_data = {'key': 'value', 'numbers': list(range(1000)), 'text': 'hello world! ' * 100}
        
        # serialize_for_redis / deserialize_from_redis
        redis_data = serialize_for_redis(test_data, compress=True)
        restored = deserialize_from_redis(redis_data)
        self.assertEqual(test_data, restored)
        
        # 압축 없이
        redis_data_no_compress = serialize_for_redis(test_data, compress=False)
        restored_no_compress = deserialize_from_redis(redis_data_no_compress)
        self.assertEqual(test_data, restored_no_compress)
        
        # 압축된 데이터가 더 작은지 확인
        self.assertLess(len(redis_data), len(redis_data_no_compress))
    
    def test_get_optimal_compression(self):
        """최적 압축 알고리즘 찾기 테스트"""
        # 텍스트 데이터
        text_data = {'content': 'Lorem ipsum dolor sit amet ' * 100}
        optimal = get_optimal_compression(text_data)
        
        self.assertIsNotNone(optimal)
        self.assertIn('algorithm', optimal)
        self.assertIn('compression_ratio', optimal)
        self.assertGreater(optimal['compression_ratio'], 0)
    
    def test_edge_cases(self):
        """엣지 케이스 테스트"""
        # 빈 데이터
        empty_data = {}
        serialized = self.serializer.serialize(empty_data)
        deserialized = self.serializer.deserialize(serialized)
        self.assertEqual(empty_data, deserialized)
        
        # None 값
        none_data = None
        serialized = self.serializer.serialize(none_data)
        deserialized = self.serializer.deserialize(serialized)
        self.assertIsNone(deserialized)
        
        # 큰 데이터
        large_data = {'data': 'x' * 1000000}  # 1MB 문자열
        serialized = self.serializer.serialize(
            large_data, 
            compression=CompressionAlgorithm.LZ4
        )
        deserialized = self.serializer.deserialize(serialized)
        self.assertEqual(large_data, deserialized)
    
    def test_error_handling(self):
        """에러 처리 테스트"""
        # 잘못된 데이터로 역직렬화 시도
        with self.assertRaises(Exception):
            self.serializer.deserialize(b'invalid data')
        
        # 잘못된 메타데이터
        with self.assertRaises(Exception):
            self.serializer.deserialize(b'invalid:metadata:corrupted_data')


class TestCompressionPerformance(unittest.TestCase):
    """압축 성능 비교 테스트"""
    
    def setUp(self):
        self.serializer = DataSerializer()
        # 다양한 테스트 데이터 준비
        self.test_datasets = {
            'repetitive': {'data': ['same'] * 10000},
            'sequential': {'data': list(range(10000))},
            'random': {'data': np.random.rand(1000).tolist()},
            'mixed': {
                'text': 'Hello World! ' * 1000,
                'numbers': list(range(1000)),
                'floats': np.random.rand(100).tolist()
            }
        }
    
    def test_compression_comparison(self):
        """각 데이터셋에 대한 압축 알고리즘 비교"""
        results = {}
        
        for dataset_name, data in self.test_datasets.items():
            results[dataset_name] = {}
            
            for algo in CompressionAlgorithm:
                if algo == CompressionAlgorithm.NONE:
                    continue
                
                try:
                    stats = self.serializer.get_compression_ratio(
                        data,
                        format=SerializationFormat.JSON,
                        compression=algo
                    )
                    results[dataset_name][algo.value] = stats
                except Exception as e:
                    print(f"Error with {algo} on {dataset_name}: {e}")
        
        # 결과 출력 (디버깅용)
        for dataset_name, algo_results in results.items():
            print(f"\n{dataset_name} dataset:")
            for algo_name, stats in algo_results.items():
                print(f"  {algo_name}: {stats['compression_ratio']}% "
                      f"({stats['compressed_size']} bytes)")


if __name__ == '__main__':
    unittest.main()