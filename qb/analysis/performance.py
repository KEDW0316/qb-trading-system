import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Dict, Any, List, Optional, Callable, Union
import logging
import numpy as np
import pandas as pd
from functools import wraps
from dataclasses import dataclass
from datetime import datetime

from .cache_manager import IndicatorCacheManager


@dataclass
class PerformanceMetrics:
    """성능 측정 메트릭"""
    function_name: str
    execution_time: float
    cache_hit: bool
    data_size: int
    timestamp: datetime
    memory_usage: Optional[float] = None


class IndicatorPerformanceOptimizer:
    """지표 계산 성능 최적화 클래스
    
    캐싱, 벡터화, 병렬 처리 등을 활용한 지표 계산 성능 최적화
    """
    
    def __init__(self, cache_manager: IndicatorCacheManager, max_workers: int = 4):
        self.cache_manager = cache_manager
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)
        
        # 성능 통계
        self.performance_stats: Dict[str, List[PerformanceMetrics]] = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=max_workers)
        
        # 메모리 사용량 추적
        self._memory_usage = {}
        
    def optimize_calculation(self, symbol: str, indicator_name: str, 
                           data: Union[List[Dict], pd.DataFrame], 
                           calculation_func: Callable, 
                           params: Optional[Dict[str, Any]] = None,
                           timeframe: str = '1m',
                           use_cache: bool = True,
                           use_vectorization: bool = True) -> Any:
        """지표 계산 최적화 (캐싱 및 성능 측정)"""
        
        start_time = time.time()
        cache_hit = False
        data_size = len(data)
        
        try:
            # 1. 캐시 확인 (우선순위 1)
            if use_cache:
                cached_result = self.cache_manager.get_cached_indicator(
                    symbol, indicator_name, params, timeframe
                )
                if cached_result is not None:
                    cache_hit = True
                    calc_time = time.time() - start_time
                    
                    # 성능 통계 기록
                    self._record_performance(
                        indicator_name, calc_time, cache_hit, data_size
                    )
                    
                    return cached_result
                    
            # 2. 데이터 벡터화 (성능 향상)
            if use_vectorization and isinstance(data, list):
                data = self._vectorize_data(data)
                
            # 3. 실제 계산 수행
            if params:
                result = calculation_func(data, **params)
            else:
                result = calculation_func(data)
                
            calc_time = time.time() - start_time
            
            # 4. 결과 캐싱
            if use_cache:
                self.cache_manager.cache_indicator(
                    symbol, indicator_name, result, params, timeframe
                )
                
            # 5. 성능 통계 기록
            self._record_performance(
                indicator_name, calc_time, cache_hit, data_size
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in optimized calculation for {indicator_name}: {e}")
            raise
            
    async def parallel_calculate_indicators(self, symbol: str, 
                                          indicators_config: List[Dict[str, Any]],
                                          data: Union[List[Dict], pd.DataFrame],
                                          timeframe: str = '1m') -> Dict[str, Any]:
        """여러 지표를 병렬로 계산"""
        
        tasks = []
        
        for config in indicators_config:
            indicator_name = config['name']
            calculation_func = config['function']
            params = config.get('params', {})
            
            # 비동기 태스크 생성
            task = asyncio.create_task(
                self._async_calculate_indicator(
                    symbol, indicator_name, data, calculation_func, 
                    params, timeframe
                )
            )
            tasks.append((indicator_name, task))
            
        # 모든 태스크 실행
        results = {}
        for indicator_name, task in tasks:
            try:
                result = await task
                results[indicator_name] = result
            except Exception as e:
                self.logger.error(f"Error calculating {indicator_name}: {e}")
                results[indicator_name] = None
                
        return results
        
    async def _async_calculate_indicator(self, symbol: str, indicator_name: str,
                                       data: Union[List[Dict], pd.DataFrame],
                                       calculation_func: Callable,
                                       params: Dict[str, Any],
                                       timeframe: str) -> Any:
        """비동기 지표 계산"""
        loop = asyncio.get_event_loop()
        
        # CPU 집약적 작업을 별도 스레드에서 실행
        result = await loop.run_in_executor(
            self.thread_pool,
            self.optimize_calculation,
            symbol, indicator_name, data, calculation_func, params, timeframe
        )
        
        return result
        
    def batch_calculate_multiple_symbols(self, symbols_data: Dict[str, Any],
                                       indicator_configs: List[Dict[str, Any]],
                                       use_multiprocessing: bool = False) -> Dict[str, Dict[str, Any]]:
        """여러 심볼에 대한 일괄 지표 계산"""
        
        results = {}
        
        if use_multiprocessing and len(symbols_data) > 1:
            # 멀티프로세싱 사용
            futures = []
            
            for symbol, data in symbols_data.items():
                future = self.process_pool.submit(
                    self._calculate_symbol_indicators,
                    symbol, data, indicator_configs
                )
                futures.append((symbol, future))
                
            # 결과 수집
            for symbol, future in futures:
                try:
                    results[symbol] = future.result(timeout=30)
                except Exception as e:
                    self.logger.error(f"Error calculating indicators for {symbol}: {e}")
                    results[symbol] = {}
                    
        else:
            # 단일 프로세스에서 순차 처리
            for symbol, data in symbols_data.items():
                try:
                    results[symbol] = self._calculate_symbol_indicators(
                        symbol, data, indicator_configs
                    )
                except Exception as e:
                    self.logger.error(f"Error calculating indicators for {symbol}: {e}")
                    results[symbol] = {}
                    
        return results
        
    def _calculate_symbol_indicators(self, symbol: str, data: Any,
                                   indicator_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """단일 심볼의 지표 계산"""
        results = {}
        
        for config in indicator_configs:
            indicator_name = config['name']
            calculation_func = config['function']
            params = config.get('params', {})
            timeframe = config.get('timeframe', '1m')
            
            try:
                result = self.optimize_calculation(
                    symbol, indicator_name, data, calculation_func, 
                    params, timeframe
                )
                results[indicator_name] = result
                
            except Exception as e:
                self.logger.error(f"Error calculating {indicator_name} for {symbol}: {e}")
                results[indicator_name] = None
                
        return results
        
    def _vectorize_data(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        """리스트 데이터를 DataFrame으로 벡터화"""
        try:
            df = pd.DataFrame(data)
            
            # 숫자 컬럼 최적화
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    
            # 시간 컬럼 최적화
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                
            return df
            
        except Exception as e:
            self.logger.error(f"Error vectorizing data: {e}")
            return pd.DataFrame(data)
            
    def _record_performance(self, function_name: str, execution_time: float,
                          cache_hit: bool, data_size: int):
        """성능 통계 기록"""
        
        metric = PerformanceMetrics(
            function_name=function_name,
            execution_time=execution_time,
            cache_hit=cache_hit,
            data_size=data_size,
            timestamp=datetime.now()
        )
        
        if function_name not in self.performance_stats:
            self.performance_stats[function_name] = []
            
        self.performance_stats[function_name].append(metric)
        
        # 최근 1000개 기록만 유지
        if len(self.performance_stats[function_name]) > 1000:
            self.performance_stats[function_name] = self.performance_stats[function_name][-1000:]
            
    def get_performance_stats(self) -> Dict[str, Dict[str, Any]]:
        """지표별 계산 성능 통계 반환"""
        
        stats = {}
        
        for indicator, metrics in self.performance_stats.items():
            if not metrics:
                continue
                
            execution_times = [m.execution_time for m in metrics]
            cache_hits = sum(1 for m in metrics if m.cache_hit)
            total_calls = len(metrics)
            
            stats[indicator] = {
                'avg_time': np.mean(execution_times),
                'min_time': np.min(execution_times),
                'max_time': np.max(execution_times),
                'std_time': np.std(execution_times),
                'total_calls': total_calls,
                'cache_hits': cache_hits,
                'cache_hit_rate': (cache_hits / total_calls * 100) if total_calls > 0 else 0,
                'avg_data_size': np.mean([m.data_size for m in metrics])
            }
            
        return stats
        
    def reset_performance_stats(self):
        """성능 통계 초기화"""
        self.performance_stats.clear()
        self.logger.info("Performance statistics reset")
        
    def optimize_memory_usage(self):
        """메모리 사용량 최적화"""
        try:
            import gc
            
            # 가비지 컬렉션 강제 실행
            collected = gc.collect()
            
            # 오래된 성능 통계 정리
            cutoff_time = datetime.now().timestamp() - 3600  # 1시간 이전
            
            for indicator in self.performance_stats:
                self.performance_stats[indicator] = [
                    m for m in self.performance_stats[indicator]
                    if m.timestamp.timestamp() > cutoff_time
                ]
                
            self.logger.info(f"Memory optimization completed, collected {collected} objects")
            
        except Exception as e:
            self.logger.error(f"Error optimizing memory usage: {e}")
            
    def benchmark_indicator(self, indicator_name: str, calculation_func: Callable,
                          test_data: List[Dict[str, Any]], 
                          iterations: int = 100) -> Dict[str, Any]:
        """지표 성능 벤치마킹"""
        
        times = []
        
        for i in range(iterations):
            start_time = time.time()
            
            try:
                # 캐시를 사용하지 않고 순수 계산 성능 측정
                result = calculation_func(test_data)
                execution_time = time.time() - start_time
                times.append(execution_time)
                
            except Exception as e:
                self.logger.error(f"Error in benchmark iteration {i}: {e}")
                continue
                
        if not times:
            return {'error': 'No successful benchmark iterations'}
            
        return {
            'indicator_name': indicator_name,
            'iterations': len(times),
            'avg_time': np.mean(times),
            'min_time': np.min(times),
            'max_time': np.max(times),
            'std_time': np.std(times),
            'total_time': np.sum(times),
            'data_size': len(test_data)
        }
        
    def get_memory_usage_info(self) -> Dict[str, Any]:
        """메모리 사용량 정보"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            return {
                'rss_mb': memory_info.rss / 1024 / 1024,  # 실제 메모리 사용량
                'vms_mb': memory_info.vms / 1024 / 1024,  # 가상 메모리 사용량
                'percent': process.memory_percent(),
                'available_mb': psutil.virtual_memory().available / 1024 / 1024,
                'cache_stats': self.cache_manager.get_cache_stats()
            }
            
        except ImportError:
            return {'error': 'psutil not available for memory monitoring'}
        except Exception as e:
            return {'error': f'Error getting memory info: {e}'}
            
    def __del__(self):
        """리소스 정리"""
        try:
            self.thread_pool.shutdown(wait=False)
            self.process_pool.shutdown(wait=False)
        except:
            pass


def performance_monitor(func):
    """성능 모니터링 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 로그 기록
            logger = logging.getLogger(func.__module__)
            logger.debug(f"{func.__name__} executed in {execution_time:.4f}s")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger = logging.getLogger(func.__module__)
            logger.error(f"{func.__name__} failed after {execution_time:.4f}s: {e}")
            raise
            
    return wrapper