import redis
import json
import logging
import time
from typing import Dict, Any, List, Optional
from .serialization import (
    DataSerializer, SerializationFormat, CompressionAlgorithm,
    serialize_for_redis, deserialize_from_redis
)

class RedisManager:
    """Redis 연결 풀 관리 및 기본 작업을 위한 클래스"""
    
    def __init__(self, host='localhost', port=6379, db=0, password=None, 
                 use_compression=True, serialization_format=SerializationFormat.JSON):
        self.logger = logging.getLogger(__name__)
        self.pool = redis.ConnectionPool(
            host=host, 
            port=port, 
            db=db,
            password=password,
            decode_responses=False  # 바이너리 데이터 지원을 위해 False로 변경
        )
        self.redis = redis.Redis(connection_pool=self.pool)
        self.logger.info(f"Redis connection pool initialized: {host}:{port} DB:{db}")
        
        # 직렬화 설정
        self.use_compression = use_compression
        self.serializer = DataSerializer(
            default_format=serialization_format,
            default_compression=CompressionAlgorithm.LZ4 if use_compression else CompressionAlgorithm.NONE
        )
        
    def ping(self) -> bool:
        """Redis 서버 연결 확인"""
        try:
            return self.redis.ping()
        except Exception as e:
            self.logger.error(f"Redis connection error: {e}")
            return False
            
    def get(self, key: str) -> Optional[str]:
        """기본 GET 연산"""
        try:
            result = self.redis.get(key)
            return result.decode() if result else None
        except Exception as e:
            self.logger.error(f"Failed to get key {key}: {e}")
            return None
            
    def set(self, key: str, value: str, ttl: int = None) -> bool:
        """기본 SET 연산"""
        try:
            if ttl:
                return self.redis.setex(key, ttl, value)
            else:
                return self.redis.set(key, value)
        except Exception as e:
            self.logger.error(f"Failed to set key {key}: {e}")
            return False
            
    def get_info(self) -> Dict[str, Any]:
        """Redis 서버 정보 조회"""
        try:
            return self.redis.info()
        except Exception as e:
            self.logger.error(f"Failed to get Redis info: {e}")
            return {}
            
    def get_memory_stats(self) -> Dict[str, Any]:
        """Redis 메모리 사용량 통계 조회"""
        try:
            info = self.redis.info('memory')
            return {
                'used_memory_human': info.get('used_memory_human'),
                'used_memory_peak_human': info.get('used_memory_peak_human'),
                'maxmemory_human': info.get('maxmemory_human'),
                'maxmemory_policy': info.get('maxmemory_policy')
            }
        except Exception as e:
            self.logger.error(f"Failed to get memory stats: {e}")
            return {}

    # ==================== 시장 데이터 관련 메서드 ====================
    
    def set_market_data(self, symbol: str, market_data: Dict[str, Any], ttl: int = 86400) -> bool:
        """실시간 시장 데이터 저장"""
        try:
            # 문자열 값으로 변환 필요한 경우 처리
            processed_data = {k.encode(): (json.dumps(v) if isinstance(v, (dict, list)) else str(v)).encode() 
                             for k, v in market_data.items()}
            self.redis.hset(f"market:{symbol}".encode(), mapping=processed_data)
            if ttl > 0:
                self.redis.expire(f"market:{symbol}".encode(), ttl)  # TTL 설정
            return True
        except Exception as e:
            self.logger.error(f"Failed to set market data for {symbol}: {e}")
            return False

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """실시간 시장 데이터 조회"""
        try:
            data = self.redis.hgetall(f"market:{symbol}".encode())
            # 바이트를 문자열로 변환하고 JSON 파싱 시도
            decoded_data = {}
            for k, v in data.items():
                key = k.decode() if isinstance(k, bytes) else k
                val_str = v.decode() if isinstance(v, bytes) else v
                try:
                    decoded_data[key] = json.loads(val_str)
                except (json.JSONDecodeError, TypeError):
                    decoded_data[key] = val_str  # 일반 문자열은 그대로 유지
            return decoded_data
        except Exception as e:
            self.logger.error(f"Failed to get market data for {symbol}: {e}")
            return {}

    def set_orderbook_data(self, symbol: str, orderbook_data: Dict[str, Any], ttl: int = 60) -> bool:
        """실시간 호가 데이터 저장"""
        try:
            # 호가 데이터 처리
            processed_data = {k.encode(): (json.dumps(v) if isinstance(v, (dict, list)) else str(v)).encode() 
                             for k, v in orderbook_data.items()}
            self.redis.hset(f"orderbook:{symbol}".encode(), mapping=processed_data)
            if ttl > 0:
                self.redis.expire(f"orderbook:{symbol}".encode(), ttl)  # 짧은 TTL (1분)
            return True
        except Exception as e:
            self.logger.error(f"Failed to set orderbook data for {symbol}: {e}")
            return False

    def get_orderbook_data(self, symbol: str) -> Dict[str, Any]:
        """실시간 호가 데이터 조회"""
        try:
            data = self.redis.hgetall(f"orderbook:{symbol}".encode())
            # 바이트를 문자열로 변환하고 JSON 파싱 시도
            decoded_data = {}
            for k, v in data.items():
                key = k.decode() if isinstance(k, bytes) else k
                val_str = v.decode() if isinstance(v, bytes) else v
                try:
                    decoded_data[key] = json.loads(val_str)
                except (json.JSONDecodeError, TypeError):
                    decoded_data[key] = val_str
            return decoded_data
        except Exception as e:
            self.logger.error(f"Failed to get orderbook data for {symbol}: {e}")
            return {}

    def get_best_bid_price(self, symbol: str) -> float:
        """최우선 매수호가 조회 (매도 시 사용)"""
        try:
            orderbook = self.get_orderbook_data(symbol)
            bid_price = orderbook.get('bid_price', 0)
            return float(bid_price) if bid_price else 0.0
        except Exception as e:
            self.logger.error(f"Failed to get best bid price for {symbol}: {e}")
            return 0.0

    # ==================== 캔들 데이터 관련 메서드 ====================
    
    def add_candle(self, symbol: str, timeframe: str, candle_data: Dict[str, Any], 
                  max_candles: int = 200) -> bool:
        """캔들 데이터 추가 (최대 개수 제한)"""
        try:
            key = f"candles:{symbol}:{timeframe}".encode()
            self.redis.lpush(key, json.dumps(candle_data).encode())
            self.redis.ltrim(key, 0, max_candles - 1)  # 최근 max_candles개만 유지
            return True
        except Exception as e:
            self.logger.error(f"Failed to add candle for {symbol}:{timeframe}: {e}")
            return False

    def get_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Dict[str, Any]]:
        """캔들 데이터 조회"""
        try:
            candles = self.redis.lrange(f"candles:{symbol}:{timeframe}".encode(), 0, limit - 1)
            return [json.loads(candle.decode() if isinstance(candle, bytes) else candle) for candle in candles]
        except Exception as e:
            self.logger.error(f"Failed to get candles for {symbol}:{timeframe}: {e}")
            return []

    # ==================== 기술적 지표 관련 메서드 ====================
    
    def cache_indicator(self, symbol: str, indicator_name: str, value: Any, ttl: int = 3600) -> bool:
        """기술적 지표 캐싱"""
        try:
            self.redis.hset(f"indicators:{symbol}", indicator_name, json.dumps(value))
            if ttl > 0:
                self.redis.expire(f"indicators:{symbol}", ttl)
            return True
        except Exception as e:
            self.logger.error(f"Failed to cache indicator {indicator_name} for {symbol}: {e}")
            return False

    def get_indicator(self, symbol: str, indicator_name: str) -> Any:
        """기술적 지표 조회"""
        try:
            value = self.redis.hget(f"indicators:{symbol}", indicator_name)
            return json.loads(value) if value else None
        except Exception as e:
            self.logger.error(f"Failed to get indicator {indicator_name} for {symbol}: {e}")
            return None

    # ==================== 호가 데이터 관련 메서드 ====================
    
    def update_orderbook(self, symbol: str, price: float, quantity: float, 
                       is_bid: bool, ttl: int = 300) -> bool:
        """호가 데이터 업데이트 (Sorted Set 사용)"""
        try:
            key = f"orderbook:{symbol}:{'bids' if is_bid else 'asks'}"
            # 가격을 점수로 사용 (매수는 높은 가격이 우선, 매도는 낮은 가격이 우선)
            # 매도의 경우 음수로 저장하여 낮은 가격이 우선되도록 함
            score = price if is_bid else price  # 매도도 양수로 저장
            self.redis.zadd(key, {json.dumps({'price': price, 'quantity': quantity}): score})
            if ttl > 0:
                self.redis.expire(key, ttl)
            return True
        except Exception as e:
            self.logger.error(f"Failed to update orderbook for {symbol}: {e}")
            return False

    def get_orderbook(self, symbol: str, side: str, limit: int = 10) -> List[Dict[str, float]]:
        """호가 데이터 조회"""
        try:
            if side not in ['bids', 'asks']:
                raise ValueError("Side must be 'bids' or 'asks'")
                
            key = f"orderbook:{symbol}:{side}"
            # 매수는 내림차순 (높은 가격 우선), 매도는 오름차순 (낮은 가격 우선)
            if side == 'bids':
                items = self.redis.zrevrange(key, 0, limit - 1, withscores=True)  # 내림차순
            else:
                items = self.redis.zrange(key, 0, limit - 1, withscores=True)  # 오름차순
                
            result = []
            for item, score in items:
                order = json.loads(item)
                result.append(order)
            return result
        except Exception as e:
            self.logger.error(f"Failed to get orderbook for {symbol}: {e}")
            return []

    # ==================== 최근 체결 내역 관련 메서드 ====================
    
    def add_trade(self, symbol: str, trade_data: Dict[str, Any], max_trades: int = 100) -> bool:
        """최근 체결 내역 추가"""
        try:
            key = f"trades:{symbol}"
            self.redis.lpush(key, json.dumps(trade_data))
            self.redis.ltrim(key, 0, max_trades - 1)  # 최근 max_trades개만 유지
            return True
        except Exception as e:
            self.logger.error(f"Failed to add trade for {symbol}: {e}")
            return False

    def get_recent_trades(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """최근 체결 내역 조회"""
        try:
            trades = self.redis.lrange(f"trades:{symbol}", 0, limit - 1)
            return [json.loads(trade) for trade in trades]
        except Exception as e:
            self.logger.error(f"Failed to get recent trades for {symbol}: {e}")
            return []

    # ==================== 고급 직렬화 메서드 ====================
    
    def set_complex_data(self, key: str, data: Any, ttl: int = 0, 
                        compression: Optional[CompressionAlgorithm] = None) -> bool:
        """복합 데이터를 직렬화하여 저장"""
        try:
            serialized = self.serializer.serialize(data, compression=compression)
            self.redis.set(key, serialized)
            if ttl > 0:
                self.redis.expire(key, ttl)
            return True
        except Exception as e:
            self.logger.error(f"Failed to set complex data for key {key}: {e}")
            return False
    
    def get_complex_data(self, key: str) -> Any:
        """직렬화된 복합 데이터를 조회하여 역직렬화"""
        try:
            serialized = self.redis.get(key)
            if serialized is None:
                return None
            return self.serializer.deserialize(serialized)
        except Exception as e:
            self.logger.error(f"Failed to get complex data for key {key}: {e}")
            return None
    
    def set_multiple_complex(self, data_dict: Dict[str, Any], ttl: int = 0) -> bool:
        """여러 복합 데이터를 배치로 저장"""
        try:
            pipe = self.redis.pipeline()
            for key, data in data_dict.items():
                serialized = self.serializer.serialize(data)
                pipe.set(key, serialized)
                if ttl > 0:
                    pipe.expire(key, ttl)
            pipe.execute()
            return True
        except Exception as e:
            self.logger.error(f"Failed to set multiple complex data: {e}")
            return False
    
    def get_multiple_complex(self, keys: List[str]) -> Dict[str, Any]:
        """여러 복합 데이터를 배치로 조회"""
        try:
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)
            results = pipe.execute()
            
            data_dict = {}
            for key, serialized in zip(keys, results):
                if serialized is not None:
                    try:
                        data_dict[key] = self.serializer.deserialize(serialized)
                    except Exception as e:
                        self.logger.warning(f"Failed to deserialize data for key {key}: {e}")
                        data_dict[key] = None
                else:
                    data_dict[key] = None
                    
            return data_dict
        except Exception as e:
            self.logger.error(f"Failed to get multiple complex data: {e}")
            return {key: None for key in keys}
    
    def add_to_compressed_list(self, key: str, data: Any, max_items: int = 1000) -> bool:
        """압축된 리스트에 항목 추가"""
        try:
            serialized = self.serializer.serialize(data)
            self.redis.lpush(key, serialized)
            self.redis.ltrim(key, 0, max_items - 1)
            return True
        except Exception as e:
            self.logger.error(f"Failed to add to compressed list {key}: {e}")
            return False
    
    def get_from_compressed_list(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """압축된 리스트에서 항목 조회"""
        try:
            serialized_items = self.redis.lrange(key, start, end)
            return [self.serializer.deserialize(item) for item in serialized_items]
        except Exception as e:
            self.logger.error(f"Failed to get from compressed list {key}: {e}")
            return []
    
    def set_compressed_hash(self, key: str, data_dict: Dict[str, Any], ttl: int = 0) -> bool:
        """해시에 압축된 데이터 저장"""
        try:
            serialized_dict = {}
            for field, data in data_dict.items():
                serialized_dict[field] = self.serializer.serialize(data)
            
            self.redis.hset(key, mapping=serialized_dict)
            if ttl > 0:
                self.redis.expire(key, ttl)
            return True
        except Exception as e:
            self.logger.error(f"Failed to set compressed hash {key}: {e}")
            return False
    
    def get_compressed_hash(self, key: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """해시에서 압축된 데이터 조회"""
        try:
            if fields:
                serialized_data = self.redis.hmget(key, fields)
                result = {}
                for field, serialized in zip(fields, serialized_data):
                    if serialized is not None:
                        result[field] = self.serializer.deserialize(serialized)
                    else:
                        result[field] = None
            else:
                serialized_data = self.redis.hgetall(key)
                result = {}
                for field, serialized in serialized_data.items():
                    result[field.decode() if isinstance(field, bytes) else field] = \
                        self.serializer.deserialize(serialized)
            
            return result
        except Exception as e:
            self.logger.error(f"Failed to get compressed hash {key}: {e}")
            return {}
    
    # ==================== 성능 및 통계 메서드 ====================
    
    def get_compression_stats(self, sample_data: Any) -> Dict[str, Any]:
        """주어진 데이터에 대한 압축 통계 조회"""
        try:
            return self.serializer.get_compression_ratio(sample_data)
        except Exception as e:
            self.logger.error(f"Failed to get compression stats: {e}")
            return {}
    
    def optimize_memory_usage(self) -> Dict[str, Any]:
        """메모리 사용량 최적화 및 통계 반환"""
        try:
            before_stats = self.get_memory_stats()
            
            # Redis 메모리 최적화 명령 실행
            self.redis.memory_purge()  # 메모리 정리
            
            # 짧은 지연 후 통계 다시 측정
            time.sleep(0.1)
            after_stats = self.get_memory_stats()
            
            return {
                'before': before_stats,
                'after': after_stats,
                'optimized': True
            }
        except Exception as e:
            self.logger.error(f"Failed to optimize memory usage: {e}")
            return {'optimized': False, 'error': str(e)}
    
    def optimize_memory(self, target_mb: int = 20) -> bool:
        """메모리 사용량 최적화 (target_mb 목표)"""
        try:
            result = self.optimize_memory_usage()
            return result.get('optimized', False)
        except Exception as e:
            self.logger.error(f"Memory optimization failed: {e}")
            return False
    
    def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """패턴에 일치하는 키 목록 조회"""
        try:
            keys = self.redis.keys(pattern.encode())
            return [key.decode() if isinstance(key, bytes) else key for key in keys]
        except Exception as e:
            self.logger.error(f"Failed to get keys by pattern {pattern}: {e}")
            return []
    
    def get_pattern_memory_usage(self, pattern: str) -> Dict[str, int]:
        """특정 패턴의 키들의 메모리 사용량"""
        try:
            keys = self.get_keys_by_pattern(pattern)
            result = {}
            for key in keys:
                try:
                    # MEMORY USAGE 명령으로 키별 메모리 사용량 조회
                    usage = self.redis.memory_usage(key.encode())
                    result[key] = usage if usage is not None else 0
                except:
                    result[key] = 0
            return result
        except Exception as e:
            self.logger.error(f"Failed to get pattern memory usage for {pattern}: {e}")
            return {}
    
    # ==================== OrderEngine에서 필요한 메서드들 ====================
    
    def list_push(self, key: str, data: Dict[str, Any], max_items: int = None) -> bool:
        """리스트에 데이터 추가"""
        try:
            serialized_data = json.dumps(data)
            self.redis.lpush(key, serialized_data)
            # max_items가 지정된 경우 리스트 크기 제한
            if max_items:
                self.redis.ltrim(key, 0, max_items - 1)
            return True
        except Exception as e:
            self.logger.error(f"Failed to push to list {key}: {e}")
            return False
    
    def set_hash(self, key: str, data: Dict[str, Any], ttl: int = None) -> bool:
        """해시에 데이터 설정"""
        try:
            # 모든 값을 문자열로 변환
            string_data = {}
            for field, value in data.items():
                if isinstance(value, (dict, list)):
                    string_data[field] = json.dumps(value)
                else:
                    string_data[field] = str(value)
            
            self.redis.hset(key, mapping=string_data)
            
            # TTL 설정
            if ttl:
                self.redis.expire(key, ttl)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to set hash {key}: {e}")
            return False
    
    def get_hash(self, key: str) -> Optional[Dict[str, Any]]:
        """해시 데이터 조회"""
        try:
            data = self.redis.hgetall(key)
            if not data:
                return None
            
            # bytes를 문자열로 변환
            result = {}
            for field, value in data.items():
                field_str = field.decode() if isinstance(field, bytes) else field
                value_str = value.decode() if isinstance(value, bytes) else value
                
                # JSON 파싱 시도
                try:
                    result[field_str] = json.loads(value_str)
                except (json.JSONDecodeError, TypeError):
                    result[field_str] = value_str
                    
            return result
        except Exception as e:
            self.logger.error(f"Failed to get hash {key}: {e}")
            return None
    
    def hash_increment(self, key: str, field: str, increment: int = 1) -> int:
        """해시 필드 값 증가"""
        try:
            return self.redis.hincrby(key, field, increment)
        except Exception as e:
            self.logger.error(f"Failed to increment hash field {key}:{field}: {e}")
            return 0
    
    # ==================== Strategy Engine 호환성 메서드 ====================
    
    def get_data(self, key: str) -> Optional[Dict[str, Any]]:
        """기존 StrategyEngine 호환성을 위한 메서드"""
        try:
            data = self.redis.get(key)
            if data:
                return json.loads(data.decode() if isinstance(data, bytes) else data)
            return None
        except Exception as e:
            self.logger.error(f"Failed to get data for key {key}: {e}")
            return None
    
    def generate_mock_indicators(self, symbol: str, price: float) -> Dict[str, float]:
        """테스트용 Mock 기술 지표 생성 (MovingAverage1M5M 전략 호환)"""
        try:
            import random
            
            # 현재 가격 기준으로 Mock 지표 생성
            base_price = price
            
            # 전략에서 신호 생성 가능하도록 조건 설정
            # 현재가가 SMA보다 높거나 낮게 랜덤 설정 (신호 생성 확률 50%)
            signal_bias = random.choice([0.98, 1.02])  # 매수 or 매도 신호 유도
            
            mock_indicators = {
                # MovingAverage1M5M 전략 필수 지표들
                'sma_3': base_price * signal_bias,  # 3분 이동평균 (신호생성용) - 전략에서 필요
                'sma_5': base_price * signal_bias,  # 5분 이동평균 (신호생성용)
                'avg_volume_5d': random.randint(50_000_000_000, 100_000_000_000),  # 5일 평균 거래대금 (500~1000억, 필터 통과)
                'price_change_6m_max': base_price * 1.20,  # 6개월 최고가 (20% 상승, "끼"있는 종목 조건)
                
                # 추가 기술 지표들
                'sma_20': base_price * (1 + random.uniform(-0.05, 0.05)),  # ±5% 변동
                'ema_12': base_price * (1 + random.uniform(-0.03, 0.03)),  # ±3% 변동
                'ema_26': base_price * (1 + random.uniform(-0.04, 0.04)),  # ±4% 변동
                'rsi_14': random.uniform(30, 70),  # RSI는 30-70 사이
                'macd': random.uniform(-500, 500),  # MACD
                'macd_signal': random.uniform(-300, 300),  # MACD Signal
                'bb_upper': base_price * 1.02,  # 볼린저 밴드 상단
                'bb_lower': base_price * 0.98,  # 볼린저 밴드 하단
                'volume_sma_20': random.randint(50000, 200000),  # 거래량 이평
                'price_change_6m_min': base_price * 0.85,  # 6개월 최저가
                'volatility_20d': random.uniform(0.15, 0.35),  # 20일 변동성
                'atr_14': base_price * random.uniform(0.01, 0.03),  # ATR
            }
            
            # get_data 방식과 호환되도록 JSON으로 저장 
            indicators_key = f"indicators:{symbol}"
            indicators_json = json.dumps(mock_indicators)
            self.redis.set(indicators_key, indicators_json, ex=3600)  # 1시간 TTL
            
            signal_type = "BUY" if signal_bias > 1.0 else "SELL"
            self.logger.info(f"🎭 Generated mock indicators for {symbol} (Signal: {signal_type}): SMA5=₩{mock_indicators['sma_5']:,.0f}, Current=₩{price:,.0f}, Volume={mock_indicators['avg_volume_5d']/1e9:.1f}B")
            
            return mock_indicators
            
        except Exception as e:
            self.logger.error(f"Failed to generate mock indicators for {symbol}: {e}")
            return {} 