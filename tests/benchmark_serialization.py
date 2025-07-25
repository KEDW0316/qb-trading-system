import time
import json
import numpy as np
import pandas as pd
from datetime import datetime
import sys
import os
from typing import Dict, List, Any
from dataclasses import dataclass
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qb.utils.serialization import (
    DataSerializer, SerializationFormat, CompressionAlgorithm,
    serialize_for_redis, deserialize_from_redis, get_optimal_compression
)


@dataclass
class BenchmarkResult:
    """벤치마크 결과 데이터 클래스"""
    name: str
    format: str
    compression: str
    serialization_time: float
    deserialization_time: float
    original_size: int
    compressed_size: int
    compression_ratio: float


class SerializationBenchmark:
    """직렬화 성능 벤치마크 클래스"""
    
    def __init__(self, iterations: int = 100):
        """
        초기화
        
        Args:
            iterations: 각 테스트 반복 횟수
        """
        self.iterations = iterations
        self.serializer = DataSerializer()
        self.results: List[BenchmarkResult] = []
    
    def create_test_datasets(self) -> Dict[str, Any]:
        """테스트용 데이터셋 생성"""
        np.random.seed(42)  # 재현 가능한 결과를 위해
        
        datasets = {
            # 1. 시장 데이터 (실시간 거래 데이터)
            'market_data': {
                'symbol': 'BTCUSDT',
                'price': 50000.0,
                'volume': 1234.56,
                'bid': 49999.0,
                'ask': 50001.0,
                'timestamp': datetime.now().isoformat(),
                'order_book': {
                    'bids': [[49999.0, 10.5], [49998.0, 5.2], [49997.0, 8.7]],
                    'asks': [[50001.0, 12.3], [50002.0, 6.8], [50003.0, 9.1]]
                }
            },
            
            # 2. 캔들 데이터 (200개 1분 캔들)
            'candle_data': [
                {
                    'timestamp': int(time.time()) - i * 60,
                    'open': 50000 + np.random.randn() * 100,
                    'high': 50000 + np.random.randn() * 100 + 50,
                    'low': 50000 + np.random.randn() * 100 - 50,
                    'close': 50000 + np.random.randn() * 100,
                    'volume': np.random.rand() * 1000
                }
                for i in range(200)
            ],
            
            # 3. 기술적 지표 데이터
            'indicators': {
                'sma_20': np.random.rand(200) * 50000,
                'sma_50': np.random.rand(200) * 50000,
                'rsi': np.random.rand(200) * 100,
                'macd': {
                    'line': np.random.rand(200) * 1000 - 500,
                    'signal': np.random.rand(200) * 1000 - 500,
                    'histogram': np.random.rand(200) * 200 - 100
                },
                'bollinger_bands': {
                    'upper': np.random.rand(200) * 52000,
                    'middle': np.random.rand(200) * 50000,
                    'lower': np.random.rand(200) * 48000
                }
            },
            
            # 4. 대용량 배열 데이터
            'large_array': np.random.rand(10000).tolist(),
            
            # 5. 복합 DataFrame
            'dataframe': pd.DataFrame({
                'timestamp': pd.date_range('2024-01-01', periods=1000, freq='1min'),
                'price': np.random.rand(1000) * 50000,
                'volume': np.random.rand(1000) * 1000,
                'moving_avg': np.random.rand(1000) * 50000
            }),
            
            # 6. 텍스트 데이터 (반복적)
            'text_repetitive': {
                'logs': ['Trading signal generated for BTCUSDT'] * 1000,
                'messages': ['Order executed successfully'] * 500
            },
            
            # 7. 혼합 타입 복합 데이터
            'mixed_complex': {
                'metadata': {
                    'version': '1.0',
                    'timestamp': datetime.now(),
                    'symbols': ['BTCUSDT', 'ETHUSDT', 'ADAUSDT'] * 100
                },
                'market_data': {
                    symbol: {
                        'prices': np.random.rand(100) * 1000,
                        'volumes': np.random.rand(100) * 10000,
                        'indicators': {
                            'rsi': np.random.rand() * 100,
                            'sma': np.random.rand() * 1000
                        }
                    }
                    for symbol in ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']
                },
                'binary_data': b'binary_content_' * 1000
            }
        }
        
        return datasets
    
    def run_benchmark(self, data: Any, name: str, format: SerializationFormat, 
                     compression: CompressionAlgorithm) -> BenchmarkResult:
        """단일 벤치마크 실행"""
        
        # 직렬화 시간 측정
        serialization_times = []
        for _ in range(self.iterations):
            start_time = time.perf_counter()
            serialized = self.serializer.serialize(data, format=format, compression=compression)
            end_time = time.perf_counter()
            serialization_times.append(end_time - start_time)
        
        # 역직렬화 시간 측정
        deserialization_times = []
        for _ in range(self.iterations):
            start_time = time.perf_counter()
            deserialized = self.serializer.deserialize(serialized)
            end_time = time.perf_counter()
            deserialization_times.append(end_time - start_time)
        
        # 크기 정보
        stats = self.serializer.get_compression_ratio(data, format=format, compression=compression)
        
        return BenchmarkResult(
            name=name,
            format=format.value,
            compression=compression.value,
            serialization_time=np.mean(serialization_times),
            deserialization_time=np.mean(deserialization_times),
            original_size=stats['original_size'],
            compressed_size=stats['compressed_size'],
            compression_ratio=stats['compression_ratio']
        )
    
    def run_all_benchmarks(self):
        """모든 벤치마크 실행"""
        datasets = self.create_test_datasets()
        
        print("Starting serialization benchmarks...")
        print(f"Running {self.iterations} iterations per test...")
        print("-" * 80)
        
        total_tests = len(datasets) * len(SerializationFormat) * len(CompressionAlgorithm)
        current_test = 0
        
        for dataset_name, data in datasets.items():
            print(f"\nTesting dataset: {dataset_name}")
            
            for format in SerializationFormat:
                # msgpack이 없으면 스킵
                if format == SerializationFormat.MSGPACK and not self.serializer.msgpack:
                    continue
                
                for compression in CompressionAlgorithm:
                    current_test += 1
                    progress = (current_test / total_tests) * 100
                    
                    try:
                        result = self.run_benchmark(data, dataset_name, format, compression)
                        self.results.append(result)
                        
                        print(f"  [{progress:5.1f}%] {format.value:8} + {compression.value:8}: "
                              f"{result.serialization_time*1000:6.2f}ms ser, "
                              f"{result.deserialization_time*1000:6.2f}ms deser, "
                              f"{result.compression_ratio:5.1f}% comp")
                        
                    except Exception as e:
                        print(f"  [ERROR] {format.value} + {compression.value}: {e}")
        
        print("\nBenchmark completed!")
        self.analyze_results()
    
    def analyze_results(self):
        """결과 분석 및 리포트 생성"""
        if not self.results:
            print("No results to analyze")
            return
        
        print("\n" + "="*80)
        print("BENCHMARK ANALYSIS REPORT")
        print("="*80)
        
        # 1. 전체 통계
        total_tests = len(self.results)
        avg_ser_time = np.mean([r.serialization_time for r in self.results])
        avg_deser_time = np.mean([r.deserialization_time for r in self.results])
        avg_compression = np.mean([r.compression_ratio for r in self.results])
        
        print(f"\nOverall Statistics:")
        print(f"  Total tests run: {total_tests}")
        print(f"  Average serialization time: {avg_ser_time*1000:.2f}ms")
        print(f"  Average deserialization time: {avg_deser_time*1000:.2f}ms")
        print(f"  Average compression ratio: {avg_compression:.1f}%")
        
        # 2. 포맷별 성능
        print(f"\nPerformance by Format:")
        format_stats = {}
        for format in SerializationFormat:
            format_results = [r for r in self.results if r.format == format.value]
            if format_results:
                format_stats[format.value] = {
                    'ser_time': np.mean([r.serialization_time for r in format_results]),
                    'deser_time': np.mean([r.deserialization_time for r in format_results]),
                    'compression': np.mean([r.compression_ratio for r in format_results])
                }
        
        for format_name, stats in format_stats.items():
            print(f"  {format_name:8}: {stats['ser_time']*1000:6.2f}ms ser, "
                  f"{stats['deser_time']*1000:6.2f}ms deser, "
                  f"{stats['compression']:5.1f}% comp")
        
        # 3. 압축 알고리즘별 성능
        print(f"\nPerformance by Compression:")
        compression_stats = {}
        for compression in CompressionAlgorithm:
            comp_results = [r for r in self.results if r.compression == compression.value]
            if comp_results:
                compression_stats[compression.value] = {
                    'ser_time': np.mean([r.serialization_time for r in comp_results]),
                    'deser_time': np.mean([r.deserialization_time for r in comp_results]),
                    'compression': np.mean([r.compression_ratio for r in comp_results]),
                    'size_reduction': np.mean([r.original_size - r.compressed_size for r in comp_results])
                }
        
        for comp_name, stats in compression_stats.items():
            print(f"  {comp_name:8}: {stats['ser_time']*1000:6.2f}ms ser, "
                  f"{stats['deser_time']*1000:6.2f}ms deser, "
                  f"{stats['compression']:5.1f}% comp, "
                  f"{stats['size_reduction']:8.0f}B saved")
        
        # 4. 최적 설정 추천
        print(f"\nRecommendations:")
        
        # 속도 우선
        fastest_ser = min(self.results, key=lambda r: r.serialization_time)
        fastest_deser = min(self.results, key=lambda r: r.deserialization_time)
        
        print(f"  Fastest serialization: {fastest_ser.format} + {fastest_ser.compression} "
              f"({fastest_ser.serialization_time*1000:.2f}ms)")
        print(f"  Fastest deserialization: {fastest_deser.format} + {fastest_deser.compression} "
              f"({fastest_deser.deserialization_time*1000:.2f}ms)")
        
        # 압축률 우선
        best_compression = max(self.results, key=lambda r: r.compression_ratio)
        print(f"  Best compression: {best_compression.format} + {best_compression.compression} "
              f"({best_compression.compression_ratio:.1f}%)")
        
        # 균형잡힌 설정 (속도와 압축률의 조합)
        balanced_results = [r for r in self.results if r.compression != 'none']
        if balanced_results:
            # 정규화된 점수 계산 (낮은 시간과 높은 압축률이 좋음)
            max_ser_time = max(r.serialization_time for r in balanced_results)
            max_deser_time = max(r.deserialization_time for r in balanced_results)
            max_compression = max(r.compression_ratio for r in balanced_results)
            
            for r in balanced_results:
                r.score = (
                    (1 - r.serialization_time / max_ser_time) * 0.3 +
                    (1 - r.deserialization_time / max_deser_time) * 0.3 +
                    (r.compression_ratio / max_compression) * 0.4
                )
            
            balanced_best = max(balanced_results, key=lambda r: r.score)
            print(f"  Balanced choice: {balanced_best.format} + {balanced_best.compression} "
                  f"(score: {balanced_best.score:.3f})")
        
        # 5. 데이터셋별 최적 설정
        print(f"\nOptimal settings by dataset:")
        datasets = set(r.name for r in self.results)
        for dataset in datasets:
            dataset_results = [r for r in self.results if r.name == dataset]
            if len(dataset_results) > 1:
                # 각 데이터셋에 대해 balanced score 계산
                max_ser = max(r.serialization_time for r in dataset_results)
                max_deser = max(r.deserialization_time for r in dataset_results)
                max_comp = max(r.compression_ratio for r in dataset_results) or 1
                
                for r in dataset_results:
                    r.dataset_score = (
                        (1 - r.serialization_time / max_ser) * 0.4 +
                        (1 - r.deserialization_time / max_deser) * 0.4 +
                        (r.compression_ratio / max_comp) * 0.2
                    )
                
                best_for_dataset = max(dataset_results, key=lambda r: r.dataset_score)
                print(f"  {dataset:15}: {best_for_dataset.format} + {best_for_dataset.compression}")
    
    def save_results_to_csv(self, filename: str = "serialization_benchmark.csv"):
        """결과를 CSV 파일로 저장"""
        if not self.results:
            return
        
        import csv
        
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = [
                'name', 'format', 'compression', 'serialization_time_ms',
                'deserialization_time_ms', 'original_size', 'compressed_size',
                'compression_ratio'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for result in self.results:
                writer.writerow({
                    'name': result.name,
                    'format': result.format,
                    'compression': result.compression,
                    'serialization_time_ms': result.serialization_time * 1000,
                    'deserialization_time_ms': result.deserialization_time * 1000,
                    'original_size': result.original_size,
                    'compressed_size': result.compressed_size,
                    'compression_ratio': result.compression_ratio
                })
        
        print(f"\nResults saved to {filename}")


def run_quick_benchmark():
    """빠른 벤치마크 실행 (적은 반복 횟수)"""
    print("Running quick benchmark...")
    benchmark = SerializationBenchmark(iterations=10)
    benchmark.run_all_benchmarks()
    benchmark.save_results_to_csv("quick_benchmark.csv")


def run_full_benchmark():
    """전체 벤치마크 실행 (많은 반복 횟수)"""
    print("Running full benchmark...")
    benchmark = SerializationBenchmark(iterations=100)
    benchmark.run_all_benchmarks()
    benchmark.save_results_to_csv("full_benchmark.csv")


def test_redis_integration():
    """Redis 통합 테스트"""
    print("\nTesting Redis integration...")
    
    # 테스트 데이터
    test_data = {
        'symbol': 'BTCUSDT',
        'price': 50000.0,
        'volume': np.array([100, 200, 300]),
        'timestamp': datetime.now(),
        'indicators': {
            'rsi': 65.5,
            'sma': np.array([49900, 50000, 50100])
        }
    }
    
    # Redis 헬퍼 함수 테스트
    serialized = serialize_for_redis(test_data, compress=True)
    deserialized = deserialize_from_redis(serialized)
    
    print(f"Original data type: {type(test_data)}")
    print(f"Serialized size: {len(serialized)} bytes")
    print(f"Deserialized successfully: {test_data.keys() == deserialized.keys()}")
    
    # 압축 효과 확인
    uncompressed = serialize_for_redis(test_data, compress=False)
    compression_saved = len(uncompressed) - len(serialized)
    compression_ratio = (compression_saved / len(uncompressed)) * 100
    
    print(f"Compression saved: {compression_saved} bytes ({compression_ratio:.1f}%)")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Serialization Benchmark')
    parser.add_argument('--quick', action='store_true', help='Run quick benchmark')
    parser.add_argument('--full', action='store_true', help='Run full benchmark')
    parser.add_argument('--redis', action='store_true', help='Test Redis integration')
    
    args = parser.parse_args()
    
    if args.quick:
        run_quick_benchmark()
    elif args.full:
        run_full_benchmark()
    elif args.redis:
        test_redis_integration()
    else:
        # 기본값: 빠른 벤치마크 실행
        run_quick_benchmark()
        test_redis_integration()