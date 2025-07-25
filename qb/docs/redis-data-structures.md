# Redis 데이터 구조 설계 문서

## QB Trading System - 실시간 데이터 버퍼링

### 📋 **개요**

QB Trading System은 **실시간 트레이딩**을 위한 이벤트 기반 마이크로서비스 아키텍처에서 Redis를 중앙 데이터 캐시 및 버퍼링 시스템으로 사용합니다.

**목표:**

- 📈 **실시간 시장 데이터** 고속 처리
- 🕯️ **시계열 데이터** 효율적 관리
- 🔄 **이벤트 기반 통신** 지원
- 💾 **메모리 사용량** 최적화

---

## 🏗️ **데이터 구조 아키텍처**

### **1. 📊 시장 데이터 (Market Data)**

**Redis 타입:** Hash  
**키 패턴:** `market:{SYMBOL}`  
**TTL:** 24시간 (86400초)

#### **목적**

실시간 시장 데이터를 빠르게 저장하고 조회하기 위한 구조

#### **데이터 스키마**

```json
{
  "price": "50000.0", // 현재가 (문자열 또는 숫자)
  "volume": "1000.5", // 거래량
  "change": "2.5", // 변동률(%)
  "change_amount": "1200.0", // 변동액
  "high": "51000.0", // 당일 최고가
  "low": "49000.0", // 당일 최저가
  "open": "49800.0", // 시가
  "prev_close": "48800.0", // 전일 종가
  "timestamp": 1700000000, // 업데이트 시간
  "details": {
    // 상세 정보 (JSON 객체)
    "market_cap": "1000000000",
    "pe_ratio": "25.5"
  }
}
```

#### **사용 예시**

```python
# 시장 데이터 저장
redis.set_market_data('BTCUSDT', {
    'price': '50000.0',
    'volume': '1000.5',
    'change': '2.5',
    'details': {'high': 51000, 'low': 49000}
})

# 시장 데이터 조회
data = redis.get_market_data('BTCUSDT')
print(f"현재가: {data['price']}")
```

#### **특징**

- ✅ **JSON 자동 변환**: 복합 데이터 타입 자동 직렬화/역직렬화
- ⏰ **TTL 관리**: 24시간 후 자동 만료
- 🔄 **부분 업데이트**: Hash 구조로 필드별 개별 업데이트 가능

---

### **2. 🕯️ 캔들 데이터 (Candle Data)**

**Redis 타입:** List  
**키 패턴:** `candles:{SYMBOL}:{TIMEFRAME}`  
**TTL:** 무제한 (수동 관리)

#### **목적**

시계열 캔들 데이터를 시간순으로 저장하고 차트 분석에 활용

#### **데이터 스키마**

```json
{
  "timestamp": 1700000000, // 캔들 시작 시간 (Unix timestamp)
  "open": 50000, // 시가
  "high": 50100, // 고가
  "low": 49900, // 저가
  "close": 50050, // 종가
  "volume": 100.5, // 거래량
  "timeframe": "1m" // 시간봉 (1m, 5m, 15m, 1h, 1d)
}
```

#### **시간봉 종류**

- `1m` - 1분봉
- `5m` - 5분봉
- `15m` - 15분봉
- `1h` - 1시간봉
- `1d` - 1일봉

#### **사용 예시**

```python
# 캔들 데이터 추가 (최신이 앞쪽)
redis.add_candle('BTCUSDT', '1m', {
    'timestamp': int(time.time()),
    'open': 50000,
    'high': 50100,
    'low': 49900,
    'close': 50050,
    'volume': 100.5
})

# 최근 200개 캔들 조회
candles = redis.get_candles('BTCUSDT', '1m', limit=200)
print(f"최신 캔들: {candles[0]}")
```

#### **특징**

- 📈 **시간순 정렬**: 최신 데이터가 리스트 앞쪽 (LPUSH 사용)
- 💾 **메모리 효율**: 최대 200개 캔들만 유지 (LTRIM 자동 적용)
- 🔄 **실시간 업데이트**: 새로운 캔들 자동 추가, 오래된 데이터 자동 삭제

---

### **3. 📈 기술적 지표 (Technical Indicators)**

**Redis 타입:** Hash  
**키 패턴:** `indicators:{SYMBOL}`  
**TTL:** 1시간 (3600초)

#### **목적**

기술적 분석 지표를 캐싱하여 반복 계산 비용 절약

#### **데이터 스키마**

```json
{
  "moving_averages": {
    // 이동평균선
    "ma_5": 49800.0,
    "ma_20": 49500.0,
    "ma_50": 48000.0,
    "ma_200": 45000.0
  },
  "oscillators": {
    // 오실레이터 지표
    "rsi": 65.5, // RSI (0-100)
    "stoch_k": 75.2, // 스토캐스틱 %K
    "stoch_d": 72.8, // 스토캐스틱 %D
    "macd": {
      // MACD 지표
      "macd": 120.5,
      "signal": 115.0,
      "histogram": 5.5
    }
  },
  "volume_indicators": {
    // 거래량 지표
    "volume_ma": 85000.0,
    "volume_ratio": 1.25
  },
  "bollinger_bands": {
    // 볼린저 밴드
    "upper": 52000.0,
    "middle": 50000.0,
    "lower": 48000.0
  }
}
```

#### **사용 예시**

```python
# 지표 캐싱
redis.cache_indicator('BTCUSDT', 'moving_averages', {
    'ma_20': 49500,
    'ma_50': 48000,
    'rsi': 65
})

# 특정 지표 조회
ma_data = redis.get_indicator('BTCUSDT', 'moving_averages')
print(f"MA20: {ma_data['ma_20']}")
```

#### **특징**

- ⚡ **빠른 접근**: 복잡한 지표 계산 결과 캐싱
- ⏰ **적절한 TTL**: 1시간 후 자동 만료로 최신성 보장
- 🔧 **유연한 구조**: 새로운 지표 타입 쉽게 추가 가능

---

### **4. 📋 호가 데이터 (Order Book)**

**Redis 타입:** Sorted Set  
**키 패턴:** `orderbook:{SYMBOL}:bids`, `orderbook:{SYMBOL}:asks`  
**TTL:** 5분 (300초)

#### **목적**

실시간 호가창 데이터를 가격순으로 정렬하여 관리

#### **데이터 스키마**

```json
// bids (매수 호가) - 높은 가격 우선
{
  "price": 50000.0,             // 호가 가격
  "quantity": 1.5               // 호가 수량
}

// asks (매도 호가) - 낮은 가격 우선
{
  "price": 50100.0,             // 호가 가격
  "quantity": 1.2               // 호가 수량
}
```

#### **정렬 규칙**

- **매수 호가 (bids)**: 높은 가격 → 낮은 가격 (내림차순)
- **매도 호가 (asks)**: 낮은 가격 → 높은 가격 (오름차순)

#### **사용 예시**

```python
# 호가 업데이트
redis.update_orderbook('BTCUSDT', 50000, 1.5, True)   # 매수 호가
redis.update_orderbook('BTCUSDT', 50100, 1.2, False)  # 매도 호가

# 호가 조회 (상위 10개)
bids = redis.get_orderbook('BTCUSDT', 'bids', limit=10)
asks = redis.get_orderbook('BTCUSDT', 'asks', limit=10)

print(f"최고 매수가: {bids[0]['price']}")
print(f"최저 매도가: {asks[0]['price']}")
```

#### **특징**

- 🎯 **자동 정렬**: Sorted Set의 스코어를 이용한 가격순 자동 정렬
- ⚡ **빠른 조회**: O(log N) 복잡도로 상위 N개 호가 즉시 조회
- 🔄 **실시간 업데이트**: 새로운 호가 추가 시 자동 정렬 유지

---

### **5. 🔄 최근 체결 내역 (Recent Trades)**

**Redis 타입:** List  
**키 패턴:** `trades:{SYMBOL}`  
**TTL:** 무제한 (수동 관리)

#### **목적**

최근 체결된 거래 내역을 시간순으로 관리

#### **데이터 스키마**

```json
{
  "timestamp": 1700000000, // 체결 시간 (Unix timestamp)
  "price": 50000, // 체결 가격
  "quantity": 0.15, // 체결 수량
  "side": "buy", // 거래 방향 ("buy" | "sell")
  "trade_id": "12345678", // 거래 ID (선택사항)
  "buyer_order_id": "B001", // 매수 주문 ID (선택사항)
  "seller_order_id": "S001" // 매도 주문 ID (선택사항)
}
```

#### **사용 예시**

```python
# 체결 내역 추가
redis.add_trade('BTCUSDT', {
    'timestamp': int(time.time()),
    'price': 50000,
    'quantity': 0.15,
    'side': 'buy'
})

# 최근 50개 체결 내역 조회
trades = redis.get_recent_trades('BTCUSDT', limit=50)
print(f"최근 거래: {trades[0]}")
```

#### **특징**

- ⏰ **시간순 정렬**: 최신 거래가 리스트 앞쪽
- 💾 **메모리 효율**: 최대 100개 거래만 유지
- 📊 **거래 분석**: 거래량, 거래 패턴 분석에 활용

---

## 🔧 **기술적 고려사항**

### **메모리 사용량 최적화**

#### **제한 설정**

```python
# 캔들 데이터: 200개 제한
MAX_CANDLES = 200  # 약 3.3시간 분량 (1분봉 기준)

# 체결 내역: 100개 제한
MAX_TRADES = 100   # 최근 100개 거래

# 호가 데이터: 20개 제한 (상위 10매수 + 10매도)
MAX_ORDERBOOK_DEPTH = 10
```

#### **TTL 전략**

```python
# 시장 데이터: 24시간 - 일일 데이터 보관
MARKET_DATA_TTL = 86400

# 지표 데이터: 1시간 - 빈번한 계산으로 적절한 캐시 수명
INDICATOR_TTL = 3600

# 호가 데이터: 5분 - 빠른 변동성으로 짧은 수명
ORDERBOOK_TTL = 300
```

### **성능 최적화**

#### **연결 풀 사용**

```python
# RedisManager에서 연결 풀 자동 관리
redis_manager = RedisManager(host='localhost', port=6379)
```

#### **배치 처리**

```python
# 여러 데이터 동시 처리
pipeline = redis.redis.pipeline()
pipeline.hset('market:BTCUSDT', mapping=market_data)
pipeline.lpush('candles:BTCUSDT:1m', json.dumps(candle))
pipeline.execute()
```

#### **JSON 최적화**

- 🔄 **자동 변환**: 복합 데이터 타입 자동 직렬화
- 📦 **압축**: 필요시 JSON 압축 적용 가능
- ⚡ **빠른 파싱**: orjson 등 고성능 JSON 라이브러리 사용 고려

---

## 📊 **메모리 사용량 예측**

### **예상 메모리 사용량** (심볼 1개당)

| 데이터 구조       | 개수  | 평균 크기 | 총 크기   |
| ----------------- | ----- | --------- | --------- |
| 시장 데이터       | 1개   | 500B      | 500B      |
| 캔들 데이터 (1분) | 200개 | 150B      | 30KB      |
| 캔들 데이터 (5분) | 200개 | 150B      | 30KB      |
| 기술적 지표       | 1개   | 1KB       | 1KB       |
| 호가 데이터       | 20개  | 100B      | 2KB       |
| 체결 내역         | 100개 | 120B      | 12KB      |
| **합계**          |       |           | **~75KB** |

### **전체 시스템 예측** (100개 심볼)

- **총 메모리**: ~7.5MB
- **Redis 오버헤드**: ~2.5MB
- **예상 총 사용량**: **~10MB**

---

## 🔍 **모니터링 및 관리**

### **헬스체크**

```bash
# Redis 연결 테스트 도구 사용
python tools/health_checks/redis_connection_test.py --detailed
```

### **메모리 모니터링**

```python
# 메모리 사용량 확인
redis_manager = RedisManager()
stats = redis_manager.get_memory_stats()
print(f"사용 중인 메모리: {stats['used_memory_human']}")
```

### **키 패턴 분석**

```bash
# 키 개수 확인
redis-cli --scan --pattern "market:*" | wc -l
redis-cli --scan --pattern "candles:*" | wc -l
redis-cli --scan --pattern "indicators:*" | wc -l
```

---

## 🚀 **확장 계획**

### **추가 예정 데이터 구조**

1. **📢 이벤트 큐** (`events:{channel}`) - Redis Pub/Sub
2. **🔐 세션 관리** (`session:{user_id}`) - 사용자 세션
3. **📝 주문 상태** (`orders:{order_id}`) - 주문 추적
4. **⚡ 실시간 알림** (`alerts:{user_id}`) - 사용자별 알림

### **성능 최적화 계획**

1. **Redis Cluster** - 수평 확장
2. **읽기 복제본** - 읽기 성능 향상
3. **데이터 파티셔닝** - 심볼별 샤딩
4. **압축 알고리즘** - 메모리 사용량 최적화

---

## 📚 **관련 문서**

- [Redis Manager API 문서](./redis-manager-api.md)
- [이벤트 버스 아키텍처](./event-bus-architecture.md)
- [성능 테스트 결과](./performance-benchmarks.md)

---

**문서 버전:** 1.0  
**최근 업데이트:** 2025-01-25  
**작성자:** QB Trading System Development Team
