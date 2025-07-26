import json
import time
import hashlib
from typing import Dict, Any, Optional, List, Union
import logging
from datetime import datetime, timedelta

from qb.utils.redis_manager import RedisManager


class IndicatorCacheManager:
    """Redis 기반 기술적 지표 캐싱 시스템
    
    계산된 지표를 Redis에 캐싱하여 중복 계산을 방지하고 성능을 향상시킵니다.
    """
    
    def __init__(self, redis_manager: RedisManager, default_expiry: int = 3600):
        self.redis_manager = redis_manager
        self.redis = redis_manager.redis
        self.default_expiry = default_expiry  # 기본 1시간 TTL
        self.logger = logging.getLogger(__name__)
        
        # 캐시 히트/미스 통계
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'invalidations': 0
        }
        
    def get_cached_indicator(self, symbol: str, indicator_name: str, 
                           params: Optional[Dict[str, Any]] = None,
                           timeframe: str = '1m') -> Optional[Any]:
        """Redis에서 캐시된 지표 조회"""
        try:
            cache_key = self._build_cache_key(symbol, indicator_name, params, timeframe)
            cached_data = self.redis.hget(f"indicators:{symbol}:{timeframe}", cache_key)
            
            if cached_data:
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode('utf-8')
                
                result = json.loads(cached_data)
                
                # 캐시 만료 시간 확인
                if self._is_cache_valid(result):
                    self.stats['hits'] += 1
                    self.logger.debug(f"Cache hit for {symbol}:{indicator_name}")
                    return result['value']
                else:
                    # 만료된 캐시 삭제
                    self.redis.hdel(f"indicators:{symbol}:{timeframe}", cache_key)
                    self.stats['misses'] += 1
                    return None
            
            self.stats['misses'] += 1
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting cached indicator: {e}")
            self.stats['misses'] += 1
            return None
            
    def cache_indicator(self, symbol: str, indicator_name: str, 
                       value: Any, params: Optional[Dict[str, Any]] = None,
                       timeframe: str = '1m', expiry: Optional[int] = None):
        """지표 계산 결과 Redis에 캐싱"""
        try:
            cache_key = self._build_cache_key(symbol, indicator_name, params, timeframe)
            
            cache_data = {
                'value': value,
                'timestamp': time.time(),
                'expiry': expiry or self.default_expiry,
                'params': params or {}
            }
            
            # Redis Hash에 저장
            self.redis.hset(
                f"indicators:{symbol}:{timeframe}", 
                cache_key, 
                json.dumps(cache_data, default=str)
            )
            
            # 전체 Hash에 TTL 설정
            self.redis.expire(f"indicators:{symbol}:{timeframe}", expiry or self.default_expiry)
            
            self.stats['sets'] += 1
            self.logger.debug(f"Cached indicator {symbol}:{indicator_name}")
            
        except Exception as e:
            self.logger.error(f"Error caching indicator: {e}")
            
    def cache_all_indicators(self, symbol: str, indicators: Dict[str, Any], 
                           timeframe: str = '1m', expiry: Optional[int] = None):
        """모든 지표를 한번에 캐싱"""
        try:
            cache_data = {
                'indicators': indicators,
                'timestamp': time.time(),
                'expiry': expiry or self.default_expiry
            }
            
            # 전체 지표를 하나의 키에 저장
            self.redis.hset(
                f"indicators:{symbol}:{timeframe}", 
                'all_indicators',
                json.dumps(cache_data, default=str)
            )
            
            # TTL 설정
            self.redis.expire(f"indicators:{symbol}:{timeframe}", expiry or self.default_expiry)
            
            self.stats['sets'] += 1
            self.logger.debug(f"Cached all indicators for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error caching all indicators: {e}")
            
    def get_all_cached_indicators(self, symbol: str, timeframe: str = '1m') -> Optional[Dict[str, Any]]:
        """캐시된 모든 지표 조회"""
        try:
            cached_data = self.redis.hget(f"indicators:{symbol}:{timeframe}", 'all_indicators')
            
            if cached_data:
                if isinstance(cached_data, bytes):
                    cached_data = cached_data.decode('utf-8')
                
                result = json.loads(cached_data)
                
                # 캐시 만료 시간 확인
                if self._is_cache_valid(result):
                    self.stats['hits'] += 1
                    self.logger.debug(f"Cache hit for all indicators {symbol}")
                    return result['indicators']
                else:
                    # 만료된 캐시 삭제
                    self.redis.hdel(f"indicators:{symbol}:{timeframe}", 'all_indicators')
                    self.stats['misses'] += 1
                    return None
            
            self.stats['misses'] += 1
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting all cached indicators: {e}")
            self.stats['misses'] += 1
            return None
            
    def _build_cache_key(self, symbol: str, indicator_name: str, 
                        params: Optional[Dict[str, Any]] = None,
                        timeframe: str = '1m') -> str:
        """캐시 키 생성"""
        if not params:
            return f"{indicator_name}"
            
        # 파라미터를 정렬하여 일관된 키 생성
        param_items = sorted(params.items())
        param_str = "_".join([f"{k}:{v}" for k, v in param_items])
        
        # 키가 너무 길면 해시 사용
        full_key = f"{indicator_name}_{param_str}"
        if len(full_key) > 250:  # Redis 키 길이 제한 고려
            hash_obj = hashlib.md5(full_key.encode())
            return f"{indicator_name}_{hash_obj.hexdigest()[:16]}"
            
        return full_key
        
    def _is_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
        """캐시 유효성 검사"""
        try:
            timestamp = cache_data.get('timestamp', 0)
            expiry = cache_data.get('expiry', self.default_expiry)
            
            return (time.time() - timestamp) < expiry
            
        except Exception:
            return False
            
    def invalidate_cache(self, symbol: str, timeframe: str = '1m'):
        """심볼에 대한 모든 캐시 무효화"""
        try:
            deleted_count = self.redis.delete(f"indicators:{symbol}:{timeframe}")
            self.stats['invalidations'] += 1
            self.logger.info(f"Invalidated cache for {symbol}:{timeframe}, deleted {deleted_count} keys")
            
        except Exception as e:
            self.logger.error(f"Error invalidating cache: {e}")
            
    def invalidate_indicator_cache(self, symbol: str, indicator_name: str,
                                 params: Optional[Dict[str, Any]] = None,
                                 timeframe: str = '1m'):
        """특정 지표 캐시만 무효화"""
        try:
            cache_key = self._build_cache_key(symbol, indicator_name, params, timeframe)
            deleted_count = self.redis.hdel(f"indicators:{symbol}:{timeframe}", cache_key)
            
            if deleted_count > 0:
                self.logger.debug(f"Invalidated cache for {symbol}:{indicator_name}")
            
        except Exception as e:
            self.logger.error(f"Error invalidating indicator cache: {e}")
            
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'sets': self.stats['sets'],
            'invalidations': self.stats['invalidations'],
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2)
        }
        
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'invalidations': 0
        }
        self.logger.info("Cache statistics reset")
        
    def get_cache_size_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """캐시 크기 정보 조회"""
        try:
            if symbol:
                # 특정 심볼의 캐시 크기
                pattern = f"indicators:{symbol}:*"
            else:
                # 모든 지표 캐시 크기
                pattern = "indicators:*"
                
            keys = self.redis.keys(pattern)
            total_memory = 0
            
            for key in keys:
                memory_usage = self.redis.memory_usage(key)
                if memory_usage:
                    total_memory += memory_usage
                    
            return {
                'total_keys': len(keys),
                'total_memory_bytes': total_memory,
                'total_memory_mb': round(total_memory / 1024 / 1024, 2),
                'pattern': pattern
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache size info: {e}")
            return {'error': str(e)}
            
    def cleanup_expired_cache(self):
        """만료된 캐시 수동 정리"""
        try:
            cleaned_count = 0
            pattern = "indicators:*"
            
            for key in self.redis.scan_iter(match=pattern):
                # Redis의 자동 만료를 활용하므로 여기서는 통계만 로깅
                ttl = self.redis.ttl(key)
                if ttl == -2:  # 키가 존재하지 않음 (만료됨)
                    cleaned_count += 1
                    
            self.logger.info(f"Cache cleanup completed, {cleaned_count} expired keys found")
            
        except Exception as e:
            self.logger.error(f"Error during cache cleanup: {e}")