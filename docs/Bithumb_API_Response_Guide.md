# Bithumb API 응답 데이터 가이드

## 개요
이 문서는 Bithumb API의 각 함수 호출 시 실제로 반환되는 데이터 구조를 정리한 것입니다. 테스트 코드 실행 결과를 바탕으로 작성되었습니다.

## 공개 API 응답 구조

### 1. 마켓 리스트 조회
```python
api.get_market_list()
```

**응답 예시:**
```json
[
  {
    "market": "KRW-BTC",
    "korean_name": "비트코인",
    "english_name": "Bitcoin"
  },
  {
    "market": "KRW-ETH",
    "korean_name": "이더리움",
    "english_name": "Ethereum"
  }
]
```

### 2. 현재가 조회
```python
api.get_ticker("KRW-BTC")
```

**응답 예시:**
```json
[
  {
    "market": "KRW-BTC",
    "trade_date": "20241201",
    "trade_time": "143000",
    "trade_price": 45000000,
    "trade_volume": 0.001,
    "prev_closing_price": 44800000,
    "change": "RISE",
    "change_price": 200000,
    "change_rate": 0.004464,
    "high_price": 45200000,
    "low_price": 44700000,
    "acc_trade_volume_24h": 1234.567,
    "acc_trade_price_24h": 55555555555,
    "acc_trade_volume_24h_change_rate": 0.123,
    "acc_trade_price_24h_change_rate": 0.456
  }
]
```

**주요 필드 설명:**
- `trade_price`: 현재 거래 가격 (원)
- `trade_volume`: 거래량
- `change`: 등락 구분 (RISE, FALL, EVEN)
- `change_price`: 전일 대비 변동 금액
- `change_rate`: 전일 대비 변동률
- `high_price`: 24시간 최고가
- `low_price`: 24시간 최저가

### 3. 호가 정보 조회
```python
api.get_orderbook("KRW-BTC")
```

**응답 예시:**
```json
{
  "market": "KRW-BTC",
  "orderbook_units": [
    {
      "ask_price": 45010000,
      "bid_price": 45000000,
      "ask_size": 0.123,
      "bid_size": 0.456
    },
    {
      "ask_price": 45020000,
      "bid_price": 44990000,
      "ask_size": 0.234,
      "bid_size": 0.567
    }
  ],
  "timestamp": 1701415800000,
  "total_ask_size": 12.345,
  "total_bid_size": 23.456
}
```

**주요 필드 설명:**
- `ask_price`: 매도 호가
- `bid_price`: 매수 호가
- `ask_size`: 매도 잔량
- `bid_size`: 매수 잔량
- `total_ask_size`: 총 매도 잔량
- `total_bid_size`: 총 매수 잔량

### 4. 캔들 데이터 조회
```python
api.get_candles("KRW-BTC", "1m", 5)
```

**응답 예시:**
```json
[
  {
    "market": "KRW-BTC",
    "candle_date_time_utc": "2024-12-01T14:30:00",
    "candle_date_time_kst": "2024-12-01T23:30:00",
    "opening_price": 45000000,
    "high_price": 45050000,
    "low_price": 44980000,
    "trade_price": 45020000,
    "candle_acc_trade_volume": 12.345,
    "candle_acc_trade_price": 555555555555,
    "timestamp": 1701415800000
  }
]
```

**주요 필드 설명:**
- `opening_price`: 시가
- `high_price`: 고가
- `low_price`: 저가
- `trade_price`: 종가
- `candle_acc_trade_volume`: 누적 거래량
- `candle_acc_trade_price`: 누적 거래금액

## 개인 API 응답 구조

### 1. 계좌 정보 조회
```python
api.get_account_info()
```

**응답 예시:**
```json
[
  {
    "currency": "KRW",
    "balance": "1000000.0",
    "locked": "0.0",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  {
    "currency": "BTC",
    "balance": "0.001",
    "locked": "0.0",
    "avg_buy_price": "45000000",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  }
]
```

**주요 필드 설명:**
- `currency`: 화폐 종류
- `balance`: 보유 잔고
- `locked`: 주문 중 잠긴 금액
- `avg_buy_price`: 평균 매수가
- `unit_currency`: 기준 화폐

### 2. 주문 리스트 조회
```python
api.get_order_list()
```

**응답 예시:**
```json
[
  {
    "uuid": "12345678-1234-1234-1234-123456789abc",
    "side": "bid",
    "ord_type": "limit",
    "price": "45000000",
    "state": "wait",
    "market": "KRW-BTC",
    "created_at": "2024-12-01T14:30:00+09:00",
    "volume": "0.001",
    "remaining_volume": "0.001",
    "reserved_fee": "0",
    "remaining_fee": "0",
    "paid_fee": "0",
    "locked": "45000",
    "executed_volume": "0",
    "trades_count": 0
  }
]
```

**주요 필드 설명:**
- `uuid`: 주문 고유 번호
- `side`: 주문 구분 (bid: 매수, ask: 매도)
- `ord_type`: 주문 타입 (limit: 지정가, market: 시장가)
- `price`: 주문 가격
- `state`: 주문 상태 (wait: 대기, done: 완료, cancel: 취소)
- `volume`: 주문 수량
- `remaining_volume`: 미체결 수량

### 3. 주문 가능 정보 조회
```python
api.get_order_chance("KRW-BTC")
```

**응답 예시:**
```json
{
  "bid_fee": "0.0005",
  "ask_fee": "0.0005",
  "bid_account": {
    "currency": "KRW",
    "balance": "1000000.0",
    "locked": "0.0",
    "avg_buy_price": "0",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  "ask_account": {
    "currency": "BTC",
    "balance": "0.001",
    "locked": "0.0",
    "avg_buy_price": "45000000",
    "avg_buy_price_modified": false,
    "unit_currency": "KRW"
  },
  "market": {
    "id": "KRW-BTC",
    "name": "KRW-BTC",
    "order_types": ["limit"],
    "order_sides": ["bid", "ask"],
    "bid": {
      "currency": "KRW",
      "price_unit": null,
      "min_total": 5000
    },
    "ask": {
      "currency": "BTC",
      "price_unit": null,
      "min_total": 0.0001
    },
    "max_total": null,
    "state": "active"
  }
}
```

**주요 필드 설명:**
- `bid_fee`: 매수 수수료율
- `ask_fee`: 매도 수수료율
- `bid_account`: 매수 가능한 계좌 정보
- `ask_account`: 매도 가능한 계좌 정보
- `market.bid.min_total`: 최소 매수 금액
- `market.ask.min_total`: 최소 매도 수량

### 4. 주문 생성
```python
api.place_order(
    market="KRW-BTC",
    side="bid",
    order_type="limit",
    price=45000000,
    volume=0.001
)
```

**응답 예시:**
```json
{
  "uuid": "12345678-1234-1234-1234-123456789abc",
  "side": "bid",
  "ord_type": "limit",
  "price": "45000000",
  "state": "wait",
  "market": "KRW-BTC",
  "created_at": "2024-12-01T14:30:00+09:00",
  "volume": "0.001",
  "remaining_volume": "0.001",
  "reserved_fee": "22.5",
  "remaining_fee": "22.5",
  "paid_fee": "0",
  "locked": "45022.5",
  "executed_volume": "0",
  "trades_count": 0
}
```

## WebSocket 실시간 데이터 구조

### 1. 현재가 구독
```python
await ws.subscribe_ticker(["KRW-BTC"], ticker_callback)
```

**실시간 메시지 예시:**
```json
{
  "type": "ticker",
  "code": "KRW-BTC",
  "opening_price": 45000000,
  "high_price": 45050000,
  "low_price": 44980000,
  "trade_price": 45020000,
  "prev_closing_price": 44800000,
  "change": "RISE",
  "change_price": 200000,
  "change_rate": 0.004464,
  "signed_change_price": 200000,
  "signed_change_rate": 0.004464,
  "trade_volume": 0.001,
  "acc_trade_volume_24h": 1234.567,
  "acc_trade_price_24h": 55555555555,
  "acc_trade_volume_24h_change_rate": 0.123,
  "acc_trade_price_24h_change_rate": 0.456,
  "timestamp": 1701415800000
}
```

### 2. 체결 구독
```python
await ws.subscribe_trade(["KRW-BTC"], trade_callback)
```

**실시간 메시지 예시:**
```json
{
  "type": "trade",
  "code": "KRW-BTC",
  "timestamp": 1701415800000,
  "trade_price": 45020000,
  "trade_volume": 0.001,
  "ask_bid": "ASK",
  "prev_closing_price": 44800000,
  "change": "RISE",
  "change_price": 200000,
  "trade_date": "20241201",
  "trade_time": "143000"
}
```

### 3. 호가 구독
```python
await ws.subscribe_orderbook(["KRW-BTC"], orderbook_callback)
```

**실시간 메시지 예시:**
```json
{
  "type": "orderbook",
  "code": "KRW-BTC",
  "timestamp": 1701415800000,
  "total_ask_size": 12.345,
  "total_bid_size": 23.456,
  "orderbook_units": [
    {
      "ask_price": 45010000,
      "bid_price": 45000000,
      "ask_size": 0.123,
      "bid_size": 0.456
    }
  ]
}
```

## 에러 응답 구조

### 일반적인 에러 응답
```json
{
  "status": "error",
  "error": {
    "message": "에러 메시지",
    "name": "에러 코드",
    "status": 400
  }
}
```

### 주문 관련 에러 예시
```json
{
  "status": "error",
  "error": {
    "message": "Insufficient funds",
    "name": "insufficient_funds",
    "status": 400
  }
}
```

## 주의사항

1. **API 키 설정**: 개인 API 사용 시 환경변수 `BIT_APP_KEY`와 `BIT_APP_SECRET` 설정 필요
2. **최소 주문 단위**: BTC 최소 주문 수량은 0.0001 BTC
3. **최소 주문 금액**: KRW 최소 주문 금액은 5,000원
4. **수수료**: 매수/매도 시 0.05% 수수료 적용
5. **WebSocket 연결**: 실시간 데이터 구독 시 연결 상태 모니터링 필요

## 테스트 실행 방법

```bash
# API 테스트
python tests/custom_test/test_bithumb_api.py

# WebSocket 테스트
python tests/custom_test/test_bithumb_websocket.py
```

이 문서는 테스트 코드 실행 결과를 바탕으로 작성되었으며, 실제 API 응답과 다를 수 있습니다. 최신 정보는 Bithumb 공식 API 문서를 참조하시기 바랍니다.
