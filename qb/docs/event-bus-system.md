# Redis Pub/Sub 이벤트 버스 시스템

## 개요

이벤트 버스 시스템은 Redis Pub/Sub을 기반으로 구현된 비동기 메시지 전달 시스템입니다. 시스템의 여러 컴포넌트 간 느슨한 결합(loose coupling)을 제공하며, 실시간 이벤트 기반 통신을 가능하게 합니다.

## 주요 기능

### 1. 이벤트 타입 정의

시스템에서 사용되는 모든 이벤트 타입은 `EventType` Enum으로 정의됩니다:

```python
class EventType(Enum):
    # 시장 데이터 관련
    MARKET_DATA_RECEIVED = "market_data_received"
    CANDLE_UPDATED = "candle_updated"
    ORDERBOOK_UPDATED = "orderbook_updated"
    TRADE_EXECUTED = "trade_executed"
    
    # 기술적 분석 관련
    INDICATORS_UPDATED = "indicators_updated"
    SIGNAL_GENERATED = "signal_generated"
    
    # 전략 관련
    STRATEGY_SIGNAL = "strategy_signal"
    TRADING_SIGNAL = "trading_signal"
    
    # 주문 관련
    ORDER_PLACED = "order_placed"
    ORDER_EXECUTED = "order_executed"
    ORDER_FAILED = "order_failed"
    ORDER_CANCELLED = "order_cancelled"
    
    # 리스크 관리 관련
    RISK_ALERT = "risk_alert"
    EMERGENCY_STOP = "emergency_stop"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"
    
    # 시스템 관련
    SYSTEM_STATUS = "system_status"
    ERROR_OCCURRED = "error_occurred"
    HEARTBEAT = "heartbeat"
```

### 2. 이벤트 메시지 구조

모든 이벤트는 `Event` 데이터 클래스로 구조화됩니다:

```python
@dataclass
class Event:
    event_type: EventType
    source: str  # 이벤트 발생 소스 (예: 'DataCollector', 'TechnicalAnalyzer')
    timestamp: datetime
    data: Dict[str, Any]
    correlation_id: Optional[str] = None  # 이벤트 추적용 ID
```

### 3. EventBus 클래스

#### 초기화
```python
from qb.utils import RedisManager, EventBus

redis_manager = RedisManager(host='localhost', port=6379)
event_bus = EventBus(redis_manager, max_workers=10)
```

#### 이벤트 버스 시작/중지
```python
# 시작
event_bus.start()

# 중지
event_bus.stop()
```

#### 이벤트 구독
```python
def market_data_handler(event: Event):
    print(f"Received market data: {event.data}")
    
# 구독 등록
event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, market_data_handler)

# 구독 해제
event_bus.unsubscribe(EventType.MARKET_DATA_RECEIVED, market_data_handler)
```

#### 이벤트 발행
```python
# 이벤트 생성 및 발행
event = event_bus.create_event(
    event_type=EventType.MARKET_DATA_RECEIVED,
    source='DataCollector',
    data={
        'symbol': 'AAPL',
        'price': 150.0,
        'volume': 1000000
    },
    correlation_id='req-123'
)

event_bus.publish(event)
```

### 4. 멀티스레딩 지원

EventBus는 ThreadPoolExecutor를 사용하여 이벤트 핸들러를 비동기적으로 실행합니다:
- 동시에 여러 이벤트 처리 가능
- 핸들러 실행 중 에러가 발생해도 다른 핸들러에 영향 없음
- `max_workers` 파라미터로 동시 처리 스레드 수 조정 가능

### 5. 에러 처리

- 구독자 콜백에서 발생하는 예외는 자동으로 캐치되고 로깅됨
- 에러 발생 시에도 이벤트 버스는 계속 작동
- 에러 통계는 `get_stats()` 메서드로 확인 가능

### 6. 통계 및 모니터링

```python
# 이벤트 처리 통계 조회
stats = event_bus.get_stats()
print(f"Published: {stats['published']}")
print(f"Received: {stats['received']}")
print(f"Processed: {stats['processed']}")
print(f"Failed: {stats['failed']}")
```

### 7. 하트비트 기능

시스템 상태 모니터링을 위한 하트비트 브로드캐스트:

```python
# 60초마다 하트비트 전송
event_bus.broadcast_heartbeat(source='MyService', interval=60)
```

## 사용 예시

### 1. 데이터 수집기에서 시장 데이터 발행

```python
class DataCollector:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        
    def on_price_update(self, symbol: str, price: float):
        event = self.event_bus.create_event(
            event_type=EventType.MARKET_DATA_RECEIVED,
            source='DataCollector',
            data={
                'symbol': symbol,
                'price': price,
                'timestamp': datetime.now().isoformat()
            }
        )
        self.event_bus.publish(event)
```

### 2. 전략 엔진에서 시장 데이터 구독

```python
class StrategyEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        # 시장 데이터 이벤트 구독
        event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, self.on_market_data)
        
    def on_market_data(self, event: Event):
        symbol = event.data['symbol']
        price = event.data['price']
        
        # 전략 로직 실행
        if self.should_trade(symbol, price):
            signal_event = self.event_bus.create_event(
                event_type=EventType.TRADING_SIGNAL,
                source='StrategyEngine',
                data={
                    'symbol': symbol,
                    'action': 'BUY',
                    'price': price,
                    'quantity': 100
                },
                correlation_id=event.correlation_id
            )
            self.event_bus.publish(signal_event)
```

### 3. 주문 엔진에서 거래 신호 처리

```python
class OrderEngine:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        # 거래 신호 구독
        event_bus.subscribe(EventType.TRADING_SIGNAL, self.on_trading_signal)
        
    def on_trading_signal(self, event: Event):
        # 주문 실행
        order_id = self.execute_order(event.data)
        
        # 주문 실행 이벤트 발행
        order_event = self.event_bus.create_event(
            event_type=EventType.ORDER_PLACED,
            source='OrderEngine',
            data={
                'order_id': order_id,
                'symbol': event.data['symbol'],
                'action': event.data['action'],
                'price': event.data['price'],
                'quantity': event.data['quantity']
            },
            correlation_id=event.correlation_id
        )
        self.event_bus.publish(order_event)
```

## 아키텍처 다이어그램

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│   Data      │     │  Technical  │     │   Strategy   │
│ Collector   │     │  Analyzer   │     │    Engine    │
└──────┬──────┘     └──────┬──────┘     └──────┬───────┘
       │                   │                    │
       │ MARKET_DATA      │ INDICATORS         │ TRADING_SIGNAL
       │ RECEIVED         │ UPDATED            │
       ▼                  ▼                    ▼
┌──────────────────────────────────────────────────────┐
│                    Event Bus                         │
│                 (Redis Pub/Sub)                      │
└──────────────────────────────────────────────────────┘
       ▲                  ▲                    ▲
       │ ORDER_PLACED     │ RISK_ALERT        │ SYSTEM_STATUS
       │                  │                    │
┌──────┴──────┐     ┌─────┴──────┐     ┌──────┴───────┐
│    Order    │     │    Risk    │     │  Monitoring  │
│   Engine    │     │  Manager   │     │   System     │
└─────────────┘     └────────────┘     └──────────────┘
```

## 성능 고려사항

1. **메시지 크기**: Redis Pub/Sub은 큰 메시지에 적합하지 않음. 대용량 데이터는 Redis에 저장하고 이벤트에는 참조 키만 포함
2. **구독자 수**: 각 이벤트는 모든 구독자에게 전달되므로 구독자가 많을수록 처리 시간 증가
3. **스레드 풀 크기**: `max_workers` 설정으로 동시 처리 수준 조정
4. **에러 복구**: 핸들러에서 예외 발생 시 자동으로 로깅되지만, 중요한 처리는 재시도 로직 구현 필요

## 테스트

단위 테스트는 `tests/test_event_bus.py`에서 확인할 수 있습니다:
- 이벤트 생성 및 직렬화
- 발행/구독 기본 기능
- 다중 구독자 처리
- 구독 해제
- 에러 처리
- 동시성 테스트
- 통계 기능
- 하트비트 기능