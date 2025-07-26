# Technical Analysis API Reference

## 📚 클래스 참조

### TechnicalAnalyzer

이벤트 기반 기술적 분석 메인 엔진

#### 초기화
```python
TechnicalAnalyzer(redis_manager: RedisManager, event_bus: EventBus)
```

**Parameters:**
- `redis_manager`: Redis 연결 관리자
- `event_bus`: 이벤트 버스 인스턴스

#### 메서드

##### `async start()`
분석기를 시작하고 이벤트 구독을 설정합니다.

```python
await analyzer.start()
```

##### `async stop()`
분석기를 중지하고 이벤트 구독을 해제합니다.

```python
await analyzer.stop()
```

##### `async calculate_indicators(symbol, candles, timeframe='1m')`
종목의 기술적 지표를 계산합니다.

**Parameters:**
- `symbol` (str): 종목 코드
- `candles` (List[Dict]): 캔들 데이터 리스트
- `timeframe` (str): 시간프레임 (기본값: '1m')

**Returns:**
- `Dict[str, float]`: 계산된 지표 딕셔너리

```python
indicators = await analyzer.calculate_indicators("005930", candles, "1m")
# Returns: {'sma_20': 102.5, 'rsi': 65.2, ...}
```

##### `async get_cached_indicators(symbol)`
캐시된 지표를 조회합니다.

**Parameters:**
- `symbol` (str): 종목 코드

**Returns:**
- `Optional[Dict[str, Any]]`: 캐시된 지표 또는 None

##### `async process_market_data(event)`
시장 데이터 이벤트를 처리합니다. (내부 메서드)

---

### IndicatorCalculator

기술적 지표 계산 엔진

#### 초기화
```python
IndicatorCalculator()
```

#### 개별 지표 메서드

##### `sma(data, period=20)`
단순 이동평균을 계산합니다.

**Parameters:**
- `data` (pd.Series | np.ndarray): 가격 데이터
- `period` (int): 이동평균 기간

**Returns:**
- `pd.Series | np.ndarray`: 계산된 SMA

```python
sma_20 = calculator.sma(close_prices, period=20)
```

##### `ema(data, period=20)`
지수 이동평균을 계산합니다.

**Parameters:**
- `data` (pd.Series | np.ndarray): 가격 데이터
- `period` (int): 이동평균 기간

**Returns:**
- `pd.Series | np.ndarray`: 계산된 EMA

```python
ema_12 = calculator.ema(close_prices, period=12)
```

##### `rsi(data, period=14)`
상대강도지수를 계산합니다.

**Parameters:**
- `data` (pd.Series | np.ndarray): 가격 데이터
- `period` (int): RSI 기간

**Returns:**
- `pd.Series | np.ndarray`: 계산된 RSI (0-100)

```python
rsi = calculator.rsi(close_prices, period=14)
```

##### `macd(data, fast_period=12, slow_period=26, signal_period=9)`
MACD를 계산합니다.

**Parameters:**
- `data` (pd.Series | np.ndarray): 가격 데이터
- `fast_period` (int): 빠른 EMA 기간
- `slow_period` (int): 느린 EMA 기간
- `signal_period` (int): 시그널 EMA 기간

**Returns:**
- `Tuple[np.ndarray, np.ndarray, np.ndarray]`: (MACD, Signal, Histogram)

```python
macd_line, signal_line, histogram = calculator.macd(close_prices)
```

##### `bollinger_bands(data, period=20, std_dev=2)`
볼린저 밴드를 계산합니다.

**Parameters:**
- `data` (pd.Series | np.ndarray): 가격 데이터
- `period` (int): 이동평균 기간
- `std_dev` (float): 표준편차 배수

**Returns:**
- `Tuple[np.ndarray, np.ndarray, np.ndarray]`: (Upper, Middle, Lower)

```python
upper, middle, lower = calculator.bollinger_bands(close_prices)
```

##### `stochastic(high, low, close, k_period=14, d_period=3)`
스토캐스틱 오실레이터를 계산합니다.

**Parameters:**
- `high` (pd.Series | np.ndarray): 고가 데이터
- `low` (pd.Series | np.ndarray): 저가 데이터
- `close` (pd.Series | np.ndarray): 종가 데이터
- `k_period` (int): %K 기간
- `d_period` (int): %D 기간

**Returns:**
- `Tuple[np.ndarray, np.ndarray]`: (%K, %D)

```python
k_percent, d_percent = calculator.stochastic(high, low, close)
```

##### `atr(high, low, close, period=14)`
평균 진정 범위를 계산합니다.

**Parameters:**
- `high` (pd.Series | np.ndarray): 고가 데이터
- `low` (pd.Series | np.ndarray): 저가 데이터
- `close` (pd.Series | np.ndarray): 종가 데이터
- `period` (int): ATR 기간

**Returns:**
- `pd.Series | np.ndarray`: 계산된 ATR

```python
atr = calculator.atr(high, low, close, period=14)
```

#### 종합 계산 메서드

##### `calculate_all_indicators(candles)`
모든 핵심 지표를 한 번에 계산합니다.

**Parameters:**
- `candles` (List[Dict]): 캔들 데이터 리스트

**Returns:**
- `Dict[str, float]`: 모든 지표 값

```python
all_indicators = calculator.calculate_all_indicators(candles)
# Returns: {
#     'sma_20': 102.5,
#     'ema_20': 103.1,
#     'rsi': 65.2,
#     'macd': 0.8,
#     'macd_signal': 0.6,
#     'macd_histogram': 0.2,
#     'bb_upper': 108.5,
#     'bb_middle': 102.0,
#     'bb_lower': 95.5,
#     'stoch_k': 75.3,
#     'stoch_d': 72.1,
#     'atr': 2.5,
#     'current_price': 103.0,
#     'price_change': 1.0,
#     'price_change_pct': 0.98
# }
```

#### 커스텀 지표 메서드

##### `register_custom_indicator(name, calculation_func, description, required_columns, default_params)`
커스텀 지표를 등록합니다.

**Parameters:**
- `name` (str): 지표 이름
- `calculation_func` (Callable): 계산 함수
- `description` (str): 지표 설명
- `required_columns` (List[str]): 필요한 데이터 컬럼
- `default_params` (Dict): 기본 파라미터

**Returns:**
- `bool`: 등록 성공 여부

```python
def volatility_ratio(data, period=10):
    return (data['high'] - data['low']) / data['close'] * 100

success = calculator.register_custom_indicator(
    'volatility_ratio',
    volatility_ratio,
    'Daily Volatility Ratio',
    ['high', 'low', 'close'],
    {'period': 10}
)
```

##### `calculate_custom_indicator(name, candles, **params)`
등록된 커스텀 지표를 계산합니다.

**Parameters:**
- `name` (str): 지표 이름
- `candles` (List[Dict]): 캔들 데이터
- `**params`: 계산 파라미터

**Returns:**
- `Any`: 계산 결과

```python
result = calculator.calculate_custom_indicator(
    'volatility_ratio',
    candles,
    period=5
)
```

---

### IndicatorCacheManager

Redis 기반 지표 캐싱 시스템

#### 초기화
```python
IndicatorCacheManager(redis_manager: RedisManager, default_expiry: int = 3600)
```

**Parameters:**
- `redis_manager`: Redis 연결 관리자
- `default_expiry`: 기본 캐시 만료 시간 (초)

#### 캐싱 메서드

##### `cache_indicator(symbol, indicator_name, value, timeframe='1m', expiry=None, params=None)`
개별 지표를 캐시합니다.

**Parameters:**
- `symbol` (str): 종목 코드
- `indicator_name` (str): 지표 이름
- `value` (Any): 지표 값
- `timeframe` (str): 시간프레임
- `expiry` (int): 만료 시간 (초)
- `params` (Dict): 지표 파라미터

```python
cache_manager.cache_indicator("005930", "rsi", 65.2, "1m")
```

##### `get_cached_indicator(symbol, indicator_name, timeframe='1m', params=None)`
캐시된 개별 지표를 조회합니다.

**Parameters:**
- `symbol` (str): 종목 코드
- `indicator_name` (str): 지표 이름
- `timeframe` (str): 시간프레임
- `params` (Dict): 지표 파라미터

**Returns:**
- `Any | None`: 캐시된 값 또는 None

```python
rsi_value = cache_manager.get_cached_indicator("005930", "rsi", "1m")
```

##### `cache_all_indicators(symbol, indicators, timeframe='1m', expiry=None)`
모든 지표를 한 번에 캐시합니다.

**Parameters:**
- `symbol` (str): 종목 코드
- `indicators` (Dict): 지표 딕셔너리
- `timeframe` (str): 시간프레임
- `expiry` (int): 만료 시간 (초)

```python
cache_manager.cache_all_indicators("005930", all_indicators, "1m")
```

##### `get_all_cached_indicators(symbol, timeframe='1m')`
캐시된 모든 지표를 조회합니다.

**Parameters:**
- `symbol` (str): 종목 코드
- `timeframe` (str): 시간프레임

**Returns:**
- `Dict | None`: 모든 지표 딕셔너리 또는 None

```python
all_cached = cache_manager.get_all_cached_indicators("005930", "1m")
```

#### 관리 메서드

##### `invalidate_cache(symbol, timeframe='1m')`
특정 종목의 캐시를 무효화합니다.

```python
cache_manager.invalidate_cache("005930", "1m")
```

##### `get_cache_stats()`
캐시 통계를 조회합니다.

**Returns:**
- `Dict`: 캐시 통계 정보

```python
stats = cache_manager.get_cache_stats()
# Returns: {
#     'hits': 150,
#     'misses': 20,
#     'sets': 25,
#     'invalidations': 2,
#     'total_requests': 170,
#     'hit_rate_percent': 88.24
# }
```

##### `reset_stats()`
캐시 통계를 초기화합니다.

```python
cache_manager.reset_stats()
```

##### `get_cache_size_info(symbol=None)`
캐시 크기 정보를 조회합니다.

**Parameters:**
- `symbol` (str, optional): 특정 종목 (None시 전체)

**Returns:**
- `Dict`: 캐시 크기 정보

```python
size_info = cache_manager.get_cache_size_info("005930")
# Returns: {
#     'total_keys': 5,
#     'total_memory_bytes': 1024,
#     'total_memory_mb': 0.001
# }
```

---

### CustomIndicatorRegistry

커스텀 지표 관리 시스템

#### 초기화
```python
CustomIndicatorRegistry()
```

#### 메서드

##### `register(name, calculation_func, description='', required_columns=None, default_params=None)`
새로운 커스텀 지표를 등록합니다.

**Parameters:**
- `name` (str): 지표 이름 (고유)
- `calculation_func` (Callable): 계산 함수
- `description` (str): 지표 설명
- `required_columns` (List[str]): 필요한 데이터 컬럼
- `default_params` (Dict): 기본 파라미터

**Returns:**
- `bool`: 등록 성공 여부

**계산 함수 시그니처:**
```python
def calculation_func(data: pd.DataFrame, **params) -> Any:
    # data는 OHLCV 데이터프레임
    # params는 계산 파라미터
    return result
```

**예제:**
```python
def price_momentum(data, period=10):
    return (data['close'] / data['close'].shift(period) - 1) * 100

registry.register(
    'price_momentum',
    price_momentum,
    'Price momentum over specified period',
    ['close'],
    {'period': 10}
)
```

##### `calculate(name, data, **params)`
등록된 커스텀 지표를 계산합니다.

**Parameters:**
- `name` (str): 지표 이름
- `data` (pd.DataFrame): OHLCV 데이터
- `**params`: 계산 파라미터

**Returns:**
- `Any`: 계산 결과

```python
result = registry.calculate('price_momentum', df, period=5)
```

##### `list_indicators()`
등록된 모든 커스텀 지표 목록을 반환합니다.

**Returns:**
- `Dict[str, Dict]`: 지표 정보 딕셔너리

```python
indicators = registry.list_indicators()
# Returns: {
#     'price_momentum': {
#         'description': 'Price momentum over specified period',
#         'required_columns': ['close'],
#         'default_params': {'period': 10}
#     }
# }
```

##### `unregister(name)`
커스텀 지표를 등록 해제합니다.

**Parameters:**
- `name` (str): 지표 이름

**Returns:**
- `bool`: 해제 성공 여부

```python
success = registry.unregister('price_momentum')
```

---

### IndicatorPerformanceOptimizer

성능 최적화 도구

#### 초기화
```python
IndicatorPerformanceOptimizer(cache_manager, max_workers=4)
```

**Parameters:**
- `cache_manager`: 캐시 관리자
- `max_workers`: 최대 워커 스레드 수

#### 메서드

##### `optimize_calculation(symbol, indicator_name, data, calculation_func)`
지표 계산을 최적화합니다.

**Parameters:**
- `symbol` (str): 종목 코드
- `indicator_name` (str): 지표 이름
- `data` (Any): 입력 데이터
- `calculation_func` (Callable): 계산 함수

**Returns:**
- `Any`: 계산 결과

```python
def heavy_calculation(data):
    # 무거운 계산 로직
    return result

optimized_result = optimizer.optimize_calculation(
    "005930",
    "custom_heavy_indicator",
    candles,
    heavy_calculation
)
```

##### `get_performance_stats()`
성능 통계를 조회합니다.

**Returns:**
- `Dict`: 성능 통계

```python
stats = optimizer.get_performance_stats()
# Returns: {
#     'custom_heavy_indicator': {
#         'total_calls': 10,
#         'total_time': 1.5,
#         'avg_time': 0.15,
#         'cache_hits': 7,
#         'cache_misses': 3
#     }
# }
```

---

## 🎯 이벤트 시스템 연동

### 이벤트 타입

#### EventType.MARKET_DATA_RECEIVED
시장 데이터 수신 시 발생하는 이벤트

**Event Data 구조:**
```python
{
    'symbol': str,           # 종목 코드
    'timeframe': str,        # 시간프레임
    'timestamp': str,        # 타임스탬프 (ISO format)
    'open': float,           # 시가
    'high': float,           # 고가
    'low': float,            # 저가
    'close': float,          # 종가
    'volume': int            # 거래량
}
```

#### EventType.INDICATORS_UPDATED
지표 계산 완료 시 발생하는 이벤트

**Event Data 구조:**
```python
{
    'symbol': str,           # 종목 코드
    'timeframe': str,        # 시간프레임
    'indicators': Dict[str, float],  # 계산된 지표들
    'timestamp': str         # 계산 완료 시간
}
```

### 이벤트 사용 예제

```python
# 이벤트 리스너 등록
async def handle_indicators(event):
    data = event.data
    symbol = data['symbol']
    indicators = data['indicators']
    
    # RSI 기반 알림
    if indicators['rsi'] > 70:
        print(f"⚠️ {symbol} 과매수 구간 (RSI: {indicators['rsi']:.1f})")
    elif indicators['rsi'] < 30:
        print(f"💡 {symbol} 과매도 구간 (RSI: {indicators['rsi']:.1f})")

event_bus.subscribe(EventType.INDICATORS_UPDATED, handle_indicators)

# 시장 데이터 이벤트 발행
market_event = event_bus.create_event(
    EventType.MARKET_DATA_RECEIVED,
    'DataCollector',
    {
        'symbol': '005930',
        'timeframe': '1m',
        'timestamp': '2025-01-01T09:00:00',
        'open': 100.0,
        'high': 105.0,
        'low': 98.0,
        'close': 103.0,
        'volume': 1000
    }
)
event_bus.publish(market_event)
```

---

## 🔧 설정 옵션

### 환경 변수
```bash
# Redis 설정
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 캐시 설정
INDICATOR_CACHE_TTL=3600         # 지표 캐시 TTL (초)
INDICATOR_CACHE_MAX_MEMORY=100   # 최대 캐시 메모리 (MB)

# 성능 설정
INDICATOR_MAX_WORKERS=4          # 최대 워커 스레드
INDICATOR_BATCH_SIZE=100         # 배치 처리 크기
```

### 설정 파일 예제
```python
# config/indicators.py
INDICATOR_CONFIG = {
    'cache': {
        'default_expiry': 3600,
        'max_memory_mb': 100,
        'cleanup_interval': 300
    },
    'performance': {
        'max_workers': 4,
        'batch_size': 100,
        'enable_gpu': False
    },
    'indicators': {
        'sma_periods': [5, 10, 20, 50, 200],
        'ema_periods': [12, 26],
        'rsi_period': 14,
        'macd_params': {
            'fast': 12,
            'slow': 26,
            'signal': 9
        },
        'bb_params': {
            'period': 20,
            'std_dev': 2
        }
    }
}
```