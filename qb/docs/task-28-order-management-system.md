# Task 28: 주문 관리 시스템 (Order Management System)

## 개요

QB Trading System의 주문 관리 시스템은 전략 엔진에서 생성된 거래 신호를 실제 주문으로 변환하고 실행하는 핵심 시스템입니다. 이벤트 기반 아키텍처를 통해 주문 생성부터 체결 완료까지의 전체 생명주기를 관리합니다.

## 아키텍처

### 시스템 구성도

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Strategy Engine │────▶│ Order Engine │────▶│ KIS Broker API  │
└─────────────────┘     └──────────────┘     └─────────────────┘
         │                      │                      │
         │                      ▼                      │
         │              ┌──────────────┐               │
         │              │ Order Queue  │               │
         │              └──────────────┘               │
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Event Bus     │────▶│  Position    │────▶│   Execution     │
│                 │     │  Manager     │     │   Manager       │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

### 주요 컴포넌트

#### 1. OrderEngine (주문 엔진)
- **역할**: 메인 주문 처리 엔진
- **기능**:
  - trading_signal 이벤트 구독 및 주문 생성
  - 주문 실행 및 상태 관리
  - 체결 처리 및 포지션 업데이트
  - 주문 관련 이벤트 발행

#### 2. KISBrokerClient (브로커 클라이언트)
- **역할**: 한국투자증권 API 연동
- **기능**:
  - 주문 제출 및 취소
  - 주문 상태 조회
  - 포지션 및 잔고 조회
  - 체결 통지 수신

#### 3. OrderQueue (주문 큐)
- **역할**: 우선순위 기반 주문 처리
- **기능**:
  - 주문 우선순위 계산
  - 동시 주문 수 제한
  - 만료된 주문 정리
  - Redis 기반 영속성

#### 4. PositionManager (포지션 관리자)
- **역할**: 실시간 포지션 추적
- **기능**:
  - 체결 기반 포지션 업데이트
  - 손익 계산 및 관리
  - 포지션 청산 주문 생성
  - 리스크 지표 계산

#### 5. CommissionCalculator (수수료 계산기)
- **역할**: 거래 수수료 계산
- **기능**:
  - 한국 주식 수수료 체계 적용
  - 매도세 및 거래세 계산
  - ETF/해외주식 별도 계산
  - 할인율 적용

#### 6. ExecutionManager (체결 관리자)
- **역할**: 체결 처리 및 추적
- **기능**:
  - 부분/완전 체결 관리
  - 미체결 주문 모니터링
  - 비정상 체결 감지
  - 체결 통계 및 분석

## 주요 기능

### 1. 이벤트 기반 주문 처리

```python
# 거래 신호 수신 → 주문 생성
async def _handle_trading_signal(self, event_data: Dict[str, Any]):
    signal = TradingSignal(**event_data["signal"])
    
    # 신호를 주문으로 변환
    order = await self._signal_to_order(signal)
    
    # 주문 검증
    if await self._validate_order(order):
        # 주문 큐에 추가
        await self.order_queue.add_order(order)
```

### 2. 우선순위 기반 주문 큐

```python
# 주문 우선순위 계산
async def _calculate_priority(self, order: Order) -> int:
    base_priority = 100
    
    # 시장가 주문이 높은 우선순위
    if order.order_type == OrderType.MARKET:
        base_priority -= 20
    
    # 매도 주문이 매수보다 높은 우선순위
    if order.side == OrderSide.SELL:
        base_priority -= 5
    
    return base_priority
```

### 3. 포지션 관리

```python
# 체결 정보로 포지션 업데이트
async def update_position(self, symbol: str, fill: Fill) -> Position:
    position = self._positions.get(symbol) or Position(symbol=symbol)
    
    # 포지션에 체결 정보 반영
    position.add_fill(fill.side, fill.quantity, fill.price, fill.commission)
    
    # Redis에 저장
    await self._save_position_to_redis(position)
    
    return position
```

### 4. 수수료 계산

```python
# 한국 주식 수수료 계산
def calculate_commission(self, order: Order, fill_price: float, fill_quantity: int) -> float:
    trade_amount = Decimal(str(fill_price)) * Decimal(str(fill_quantity))
    
    # 위탁수수료
    brokerage_fee = trade_amount * self.commission_rates["brokerage_rate"]
    brokerage_fee = max(brokerage_fee, self.commission_rates["min_brokerage_fee"])
    
    # 매도시 세금 추가
    if order.side == OrderSide.SELL:
        taxes = self._calculate_taxes(trade_amount)
        total_commission += taxes
    
    return float(total_commission)
```

### 5. 체결 추적

```python
# 체결 추적기
@dataclass
class ExecutionTracker:
    order_id: str
    symbol: str
    total_quantity: int
    filled_quantity: int = 0
    average_fill_price: float = 0.0
    fills: List[Fill] = field(default_factory=list)
    
    @property
    def fill_ratio(self) -> float:
        return self.filled_quantity / self.total_quantity
```

## 데이터 모델

### Order (주문)
```python
@dataclass
class Order:
    symbol: str              # 종목 코드
    side: OrderSide         # 매수/매도
    order_type: OrderType   # 주문 타입
    quantity: int           # 수량
    price: Optional[float]  # 가격 (지정가)
    status: OrderStatus     # 주문 상태
    filled_quantity: int    # 체결 수량
    average_fill_price: Optional[float]  # 평균 체결가
```

### Fill (체결)
```python
@dataclass
class Fill:
    fill_id: str           # 체결 ID
    order_id: str          # 주문 ID
    symbol: str            # 종목 코드
    side: OrderSide        # 매수/매도
    quantity: int          # 체결 수량
    price: float           # 체결 가격
    commission: float      # 수수료
    timestamp: datetime    # 체결 시간
```

### Position (포지션)
```python
@dataclass
class Position:
    symbol: str            # 종목 코드
    quantity: int          # 보유 수량
    average_price: float   # 평균 매입가
    market_price: float    # 현재가
    unrealized_pnl: float  # 미실현 손익
    realized_pnl: float    # 실현 손익
```

## 이벤트 흐름

### 주문 생성 및 실행 흐름

```
1. trading_signal 이벤트 수신
2. 신호를 주문으로 변환
3. 주문 사전 검증 (잔고, 리스크 등)
4. 주문 큐에 추가
5. 브로커 API로 주문 제출
6. order_placed 이벤트 발행
7. 체결 통지 수신
8. order_executed 이벤트 발행
9. 포지션 업데이트
10. 완전 체결시 order_fully_executed 이벤트 발행
```

### 이벤트 타입

#### 수신 이벤트
- `trading_signal`: 전략 엔진의 거래 신호
- `market_data_received`: 시장 데이터 (포지션 평가용)
- `kis_fill_notification`: KIS 체결 통지
- `kis_order_status_change`: KIS 주문 상태 변경

#### 발행 이벤트
- `order_placed`: 주문 제출 완료
- `order_executed`: 주문 체결
- `order_failed`: 주문 실패
- `order_cancelled`: 주문 취소
- `order_fully_executed`: 완전 체결
- `order_partially_executed`: 부분 체결
- `position_updated`: 포지션 업데이트

## 리스크 관리

### 1. 주문 검증
- 계좌 잔고 확인
- 최대 주문 금액 제한
- 최대 포지션 수 제한
- 주문 수량 유효성

### 2. 포지션 관리
- 포지션 크기 제한
- 포트폴리오 집중도 관리
- 일일 손실 한도
- VaR (Value at Risk) 계산

### 3. 체결 모니터링
- 체결 지연 감지
- 비정상적인 가격 체결 감지
- 과도한 체결 분할 감지
- 부분 체결 타임아웃

## 성능 최적화

### 1. 우선순위 큐 사용
- 시장가 주문 우선 처리
- 매도 주문 우선 처리
- 전략별 우선순위 설정

### 2. 캐싱 전략
- 포지션 정보 캐싱
- 계좌 잔고 캐싱 (10초)
- 주문 정보 Redis 저장

### 3. 비동기 처리
- 주문 처리 비동기화
- 이벤트 기반 통신
- 동시 주문 수 제한

## 설정 옵션

```python
# OrderEngine 설정
config = {
    "max_order_value": 10_000_000,      # 최대 주문 금액
    "max_position_count": 10,           # 최대 포지션 수
    "order_timeout": 300,               # 주문 타임아웃 (초)
    "enable_partial_fills": True        # 부분 체결 허용
}

# OrderQueue 설정
queue_config = {
    "max_queue_size": 1000,             # 최대 큐 크기
    "max_concurrent_orders": 10,        # 동시 처리 주문 수
    "priority_timeout": 300             # 우선순위 타임아웃
}

# ExecutionManager 설정
execution_config = {
    "max_partial_fill_time": 300,       # 부분 체결 최대 시간
    "min_fill_size": 1,                 # 최소 체결 크기
    "max_fills_per_order": 100          # 주문당 최대 체결 수
}
```

## 사용 예제

### 기본 사용법

```python
# 주문 엔진 초기화
order_engine = OrderEngine(
    broker_client=kis_broker_client,
    order_queue=order_queue,
    position_manager=position_manager,
    commission_calculator=commission_calculator,
    event_bus=event_bus,
    redis_manager=redis_manager
)

# 엔진 시작
await order_engine.start()

# 상태 조회
status = await order_engine.get_engine_status()
print(f"Active orders: {status['active_orders_count']}")

# 특정 종목의 주문 취소
cancelled = await order_engine.cancel_all_orders_for_symbol("005930")
print(f"Cancelled {cancelled} orders")
```

### 포지션 조회

```python
# 특정 종목 포지션
position = await position_manager.get_position("005930")
if position:
    print(f"Quantity: {position.quantity}")
    print(f"Unrealized P&L: {position.unrealized_pnl:,.0f}")

# 포트폴리오 요약
summary = await position_manager.get_portfolio_summary()
print(f"Total positions: {summary['total_positions']}")
print(f"Total P&L: {summary['total_pnl']:,.0f}")
```

### 체결 상태 조회

```python
# 체결 상태
exec_status = await execution_manager.get_execution_status(order_id)
print(f"Fill ratio: {exec_status['fill_ratio']:.1%}")

# 일일 통계
daily_stats = await execution_manager.get_daily_execution_stats()
print(f"Total fills today: {daily_stats['total_fills']}")
```

## 테스트

### 단위 테스트
- 주문 데이터 클래스 검증
- 우선순위 큐 동작
- 수수료 계산 정확성
- 포지션 업데이트 로직

### 통합 테스트
- 전체 주문 생명주기
- 부분 체결 처리
- 에러 처리 및 복구
- 이벤트 흐름 검증

## 주의사항

1. **실전/모의 모드**: KISBrokerClient는 거래 모드를 확인하여 적절한 API를 호출합니다.

2. **수수료 계산**: 한국 주식 시장의 복잡한 수수료 체계를 정확히 반영합니다.

3. **체결 지연**: 부분 체결이 오래 지속되면 경고를 발생시킵니다.

4. **메모리 관리**: 체결 히스토리와 주문 히스토리는 제한된 수만 메모리에 유지합니다.

5. **동시성**: 주문 큐와 포지션 매니저는 asyncio.Lock을 사용하여 동시성을 제어합니다.

## 다음 단계

Task 28 완료 후 다음 작업:
- Task 29: 리스크 관리 시스템 구현
- Task 30: 백테스팅 엔진 구현
- Task 31: 성과 분석 대시보드 구현