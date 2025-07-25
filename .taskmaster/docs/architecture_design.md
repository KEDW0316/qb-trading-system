# QB Trading System - 아키텍처 설계 문서

**작성일**: 2025년 1월
**버전**: 1.0
**대상**: 개발팀

---

## 1. 아키텍처 개요

### 1.1 설계 철학

- **모듈성**: 각 컴포넌트가 독립적으로 개발/배포/확장 가능
- **확장성**: 새로운 전략, 데이터 소스, 시장 추가가 용이
- **안정성**: 단일 장애점 제거 및 자동 복구 메커니즘
- **성능**: 1GB RAM 환경에서 실시간 거래 지원
- **유지보수성**: 명확한 책임 분리 및 표준화된 인터페이스

### 1.2 핵심 아키텍처 패턴

- **이벤트 기반 아키텍처 (Event-Driven Architecture)**
- **플러그인 아키텍처 (Plugin Architecture)**
- **레이어드 아키텍처 (Layered Architecture)**
- **CQRS (Command Query Responsibility Segregation)**

### 1.3 기술적 결정사항과 근거

#### Redis 선택 이유

- **실시간 성능**: 0.001초 이내 데이터 조회
- **메모리 효율**: 20-25MB로 경량 운영 가능
- **이벤트 지원**: Pub/Sub 기능으로 이벤트 버스 구현
- **데이터 구조**: List, Hash 등 다양한 자료구조 지원

#### 이벤트 기반 통신 선택 이유

- **느슨한 결합**: 각 엔진이 독립적으로 동작
- **확장성**: 새로운 이벤트 구독자 추가 용이
- **비동기 처리**: 높은 처리량과 응답성 확보
- **장애 격리**: 한 엔진 문제가 전체 시스템에 영향 최소화

---

## 2. 시스템 구성 요소

### 2.1 백엔드 디렉토리 구조

```
backend/
├── app/
│   ├── main.py                    # FastAPI 엔트리포인트
│   ├── config/                    # 설정 관리
│   │   ├── settings.py           # 환경별 설정
│   │   ├── database.py           # DB 연결 설정
│   │   └── redis.py              # Redis 연결 설정
│   ├── api/                       # API 레이어
│   │   ├── v1/endpoints/         # REST API 엔드포인트
│   │   └── websocket/            # WebSocket 핸들러
│   ├── core/                      # 핵심 비즈니스 로직
│   │   ├── engines/              # 주요 엔진들
│   │   ├── events/               # 이벤트 시스템
│   │   └── services/             # 공통 서비스
│   ├── strategies/                # 전략 플러그인
│   │   ├── base.py               # 전략 베이스 클래스
│   │   ├── moving_average.py     # 이동평균 전략
│   │   └── custom/               # 사용자 정의 전략
│   ├── data/                      # 데이터 레이어
│   │   ├── models/               # SQLAlchemy 모델
│   │   ├── adapters/             # 외부 API 어댑터
│   │   └── repositories/         # 데이터 접근 계층
│   └── utils/                     # 유틸리티
├── tests/                         # 테스트 코드
├── requirements.txt               # Python 의존성
└── Dockerfile                    # 컨테이너 이미지
```

### 2.2 데이터 모델 설계

#### Redis 데이터 구조

```
# 실시간 시장 데이터 (Hash)
market:SYMBOL -> {
    "timestamp": "2025-01-01T09:00:00",
    "open": 75000,
    "high": 75500,
    "low": 74800,
    "close": 75200,
    "volume": 1500000
}

# 캔들 데이터 (List) - 최근 200개
candles:SYMBOL:1m -> [
    "{timestamp, open, high, low, close, volume}",
    ...
]

# 기술적 지표 (Hash)
indicators:SYMBOL -> {
    "sma_20": 74500,
    "rsi": 65.5,
    "macd": 150.2,
    "updated_at": "2025-01-01T09:00:00"
}

# 이벤트 채널 (Pub/Sub)
events:market_data_received
events:trading_signal
events:order_executed
events:risk_alert
```

#### PostgreSQL 스키마

```sql
-- 시계열 주가 데이터
CREATE TABLE market_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    open DECIMAL(12,2),
    high DECIMAL(12,2),
    low DECIMAL(12,2),
    close DECIMAL(12,2),
    volume BIGINT,
    interval_type VARCHAR(5), -- '1m', '5m', '1d'
    PRIMARY KEY (time, symbol, interval_type)
);

-- TimescaleDB 하이퍼테이블 생성
SELECT create_hypertable('market_data', 'time');

-- 거래 기록
CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) NOT NULL, -- 'BUY', 'SELL'
    quantity INTEGER NOT NULL,
    price DECIMAL(12,2) NOT NULL,
    commission DECIMAL(10,2),
    strategy_name VARCHAR(100),
    order_type VARCHAR(20),
    status VARCHAR(20), -- 'FILLED', 'PARTIAL', 'CANCELLED'
    profit_loss DECIMAL(12,2)
);

-- 포지션 정보
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    average_price DECIMAL(12,2),
    current_price DECIMAL(12,2),
    unrealized_pnl DECIMAL(12,2),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol)
);

-- 전략 성과
CREATE TABLE strategy_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    total_return DECIMAL(8,4),
    trades_count INTEGER,
    win_rate DECIMAL(5,2),
    max_drawdown DECIMAL(8,4),
    sharpe_ratio DECIMAL(6,3)
);
```

---

## 3. 핵심 엔진 상세 설계

### 3.1 이벤트 버스 (Event Bus)

#### 이벤트 타입 정의

```python
# 시장 데이터 관련
MARKET_DATA_RECEIVED = "market_data_received"
INDICATORS_UPDATED = "indicators_updated"

# 거래 관련
TRADING_SIGNAL = "trading_signal"
ORDER_PLACED = "order_placed"
ORDER_EXECUTED = "order_executed"
ORDER_FAILED = "order_failed"

# 리스크 관리
RISK_ALERT = "risk_alert"
POSITION_UPDATED = "position_updated"
STOP_LOSS_TRIGGERED = "stop_loss_triggered"

# 시스템 관리
SYSTEM_ERROR = "system_error"
ENGINE_STARTED = "engine_started"
ENGINE_STOPPED = "engine_stopped"
```

#### 이벤트 데이터 구조

```python
@dataclass
class MarketDataEvent:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str  # 'kis', 'naver', 'yahoo'

@dataclass
class TradingSignalEvent:
    symbol: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float  # 0.0 ~ 1.0
    price: float
    quantity: int
    strategy_name: str
    timestamp: datetime
    metadata: Dict[str, Any]

@dataclass
class RiskAlertEvent:
    alert_type: str  # 'POSITION_LIMIT', 'DAILY_LOSS', 'STOP_LOSS'
    symbol: str
    current_value: float
    limit_value: float
    severity: str  # 'WARNING', 'CRITICAL'
    action_required: bool
    timestamp: datetime
```

### 3.2 전략 엔진 (Strategy Engine)

#### 전략 인터페이스

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseStrategy(ABC):
    def __init__(self, parameters: Dict[str, Any]):
        self.parameters = parameters
        self.name = self.__class__.__name__

    @abstractmethod
    async def analyze(self, market_data: MarketDataEvent,
                     indicators: Dict[str, float]) -> Optional[TradingSignalEvent]:
        """시장 데이터와 지표를 분석하여 거래 신호 생성"""
        pass

    @abstractmethod
    def get_required_indicators(self) -> List[str]:
        """이 전략이 필요로 하는 기술적 지표 목록"""
        pass

    @abstractmethod
    def get_parameter_schema(self) -> Dict[str, Any]:
        """전략 파라미터의 스키마 정보"""
        pass

    def validate_parameters(self) -> bool:
        """파라미터 유효성 검증"""
        schema = self.get_parameter_schema()
        # 검증 로직 구현
        return True
```

#### 전략 로더

```python
class StrategyLoader:
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.strategy_configs = {}

    async def load_strategy(self, strategy_name: str, config: Dict[str, Any]):
        """전략을 동적으로 로드"""
        module_path = f"app.strategies.{strategy_name}"
        module = importlib.import_module(module_path)

        class_name = self._get_strategy_class_name(strategy_name)
        strategy_class = getattr(module, class_name)

        strategy_instance = strategy_class(config.get("parameters", {}))

        if strategy_instance.validate_parameters():
            self.strategies[strategy_name] = strategy_instance
            self.strategy_configs[strategy_name] = config
            return True
        return False

    def _get_strategy_class_name(self, strategy_name: str) -> str:
        """전략명에서 클래스명 생성 (snake_case -> PascalCase)"""
        return ''.join(word.capitalize() for word in strategy_name.split('_')) + 'Strategy'
```

### 3.3 데이터 수집기 (Data Collector)

#### 데이터 소스 어댑터

```python
class BaseDataAdapter(ABC):
    @abstractmethod
    async def connect(self) -> bool:
        """데이터 소스에 연결"""
        pass

    @abstractmethod
    async def subscribe_symbol(self, symbol: str) -> bool:
        """심볼 실시간 구독"""
        pass

    @abstractmethod
    async def get_historical_data(self, symbol: str,
                                interval: str, count: int) -> List[MarketDataEvent]:
        """과거 데이터 조회"""
        pass

    @abstractmethod
    async def disconnect(self):
        """연결 해제"""
        pass

class KISDataAdapter(BaseDataAdapter):
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.websocket = None
        self.access_token = None

    async def connect(self) -> bool:
        # OAuth 인증
        self.access_token = await self._authenticate()

        # WebSocket 연결
        self.websocket = await websockets.connect(self.websocket_url)
        await self._send_auth_message()

        return True

    async def _handle_websocket_message(self, message: str):
        """WebSocket 메시지 처리"""
        try:
            data = self._parse_message(message)
            market_event = MarketDataEvent(
                symbol=data['symbol'],
                timestamp=datetime.fromisoformat(data['timestamp']),
                open=float(data['open']),
                high=float(data['high']),
                low=float(data['low']),
                close=float(data['close']),
                volume=int(data['volume']),
                source='kis'
            )

            # 이벤트 발행
            await self.event_bus.publish(MARKET_DATA_RECEIVED, market_event)

        except Exception as e:
            logger.error(f"Message processing error: {e}")
```

### 3.4 리스크 엔진 (Risk Engine)

#### 리스크 체크 규칙

```python
class RiskRule(ABC):
    @abstractmethod
    async def check(self, order: Order, context: RiskContext) -> RiskCheckResult:
        pass

class PositionSizeRule(RiskRule):
    def __init__(self, max_position_ratio: float = 0.1):
        self.max_position_ratio = max_position_ratio

    async def check(self, order: Order, context: RiskContext) -> RiskCheckResult:
        portfolio_value = context.get_portfolio_value()
        current_position_value = context.get_position_value(order.symbol)
        order_value = order.quantity * order.price

        total_position_value = current_position_value + order_value
        max_allowed = portfolio_value * self.max_position_ratio

        if total_position_value > max_allowed:
            suggested_quantity = max(0, int((max_allowed - current_position_value) / order.price))
            return RiskCheckResult(
                approved=False,
                reason=f"Position size limit exceeded. Max: {max_allowed:,.0f}",
                suggested_quantity=suggested_quantity
            )

        return RiskCheckResult(approved=True)

class DailyLossLimitRule(RiskRule):
    def __init__(self, max_daily_loss_ratio: float = 0.02):
        self.max_daily_loss_ratio = max_daily_loss_ratio

    async def check(self, order: Order, context: RiskContext) -> RiskCheckResult:
        today_pnl = context.get_daily_pnl()
        portfolio_value = context.get_portfolio_value()
        max_loss = portfolio_value * self.max_daily_loss_ratio

        if today_pnl <= -max_loss:
            return RiskCheckResult(
                approved=False,
                reason=f"Daily loss limit reached. Current: {today_pnl:,.0f}, Limit: {max_loss:,.0f}"
            )

        return RiskCheckResult(approved=True)
```

---

## 4. 성능 최적화 전략

### 4.1 메모리 관리 (1GB 환경)

#### 메모리 할당 계획

```
총 1GB RAM 분배:
├── 시스템 + OS: ~200MB
├── PostgreSQL: 300MB
│   ├── shared_buffers: 128MB
│   ├── work_mem: 4MB
│   └── effective_cache_size: 168MB
├── Redis: 150MB
│   ├── 시장 데이터: 50MB
│   ├── 기술 지표: 30MB
│   ├── 이벤트 큐: 20MB
│   └── 기타 캐시: 50MB
├── Python Backend: 250MB
│   ├── FastAPI: 50MB
│   ├── 전략 엔진: 80MB
│   ├── 데이터 처리: 70MB
│   └── 기타 엔진: 50MB
├── Next.js Frontend: 150MB
├── Nginx: 50MB
└── 여유 공간: 100MB
```

#### 메모리 최적화 기법

1. **데이터 순환 관리**: Redis에서 오래된 데이터 자동 삭제
2. **레이지 로딩**: 필요한 시점에만 데이터 로드
3. **압축**: 저장 데이터 압축으로 메모리 절약
4. **풀링**: 연결 풀, 객체 풀 활용

### 4.2 성능 모니터링

#### 모니터링 지표

```python
@dataclass
class PerformanceMetrics:
    # 응답 시간
    api_response_time: float
    websocket_latency: float
    strategy_execution_time: float
    order_execution_time: float

    # 처리량
    events_per_second: int
    orders_per_minute: int
    data_updates_per_second: int

    # 리소스 사용량
    memory_usage_mb: int
    cpu_usage_percent: float
    redis_memory_mb: int
    postgres_connections: int

    # 비즈니스 지표
    strategy_win_rate: float
    average_profit_per_trade: float
    daily_return_percent: float
    max_drawdown_percent: float
```

---

## 5. 확장성 및 확장 계획

### 5.1 수평 확장 (Scale-Out)

#### 컴포넌트별 확장성

```yaml
# 확장 가능한 컴포넌트
scalable_components:
  - api_server: 3 instances # 로드 밸런싱
  - strategy_workers: 2 instances # 전략별 분산
  - data_collectors: 2 instances # 데이터 소스별 분산

# 확장 불가능한 컴포넌트 (단일 인스턴스)
singleton_components:
  - order_engine: 1 instance # 주문 순서 보장
  - risk_engine: 1 instance # 일관된 리스크 체크
  - postgres: 1 instance # 단일 데이터베이스
  - redis: 1 instance # 단일 캐시
```

### 5.2 기능 확장 로드맵

#### Phase 1: 기본 시스템 (현재)

- 한국 주식 시장
- 기본 기술적 분석 전략
- 웹 대시보드

#### Phase 2: 고도화 (6개월)

- 머신러닝 기반 전략
- 모바일 앱
- 고급 리스크 관리

#### Phase 3: 다변화 (1년)

- 해외 주식 (미국, 일본)
- 암호화폐 거래
- 포트폴리오 최적화

#### Phase 4: 플랫폼화 (2년)

- 사용자 커뮤니티
- 전략 마켓플레이스
- API 서비스 제공

---

## 6. 보안 및 안정성

### 6.1 보안 설계

#### API 보안

```python
# JWT 기반 인증
class SecurityManager:
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30

    def create_access_token(self, data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str):
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            return None

# API 키 관리
class APIKeyManager:
    def __init__(self):
        self.kis_api_key = os.getenv("KIS_API_KEY")
        self.kis_secret_key = os.getenv("KIS_SECRET_KEY")

    def encrypt_sensitive_data(self, data: str) -> str:
        # 민감한 데이터 암호화
        pass

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        # 암호화된 데이터 복호화
        pass
```

#### 네트워크 보안

- HTTPS 강제 사용
- CORS 정책 설정
- Rate Limiting 적용
- IP 기반 접근 제한

### 6.2 장애 복구 (Fault Tolerance)

#### 자동 재시작 메커니즘

```python
class AutoRestartManager:
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 5

    async def with_auto_restart(self, func, *args, **kwargs):
        """함수 실행 중 예외 발생 시 자동 재시도"""
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    raise

# 헬스체크
class HealthChecker:
    async def check_database(self) -> bool:
        # PostgreSQL 연결 확인
        pass

    async def check_redis(self) -> bool:
        # Redis 연결 확인
        pass

    async def check_external_apis(self) -> bool:
        # 외부 API 상태 확인
        pass

    async def overall_health(self) -> Dict[str, bool]:
        return {
            "database": await self.check_database(),
            "redis": await self.check_redis(),
            "external_apis": await self.check_external_apis()
        }
```

---

## 7. 개발 가이드라인

### 7.1 코딩 스타일

#### Python 코딩 표준

- **PEP 8** 준수
- **Type Hints** 필수 사용
- **Docstring** 모든 함수/클래스에 작성
- **f-string** 사용 권장
- **Async/Await** 비동기 처리

#### 에러 핸들링

```python
# 커스텀 예외 정의
class TradingSystemError(Exception):
    """거래 시스템 기본 예외"""
    pass

class InsufficientFundsError(TradingSystemError):
    """자금 부족 예외"""
    pass

class RiskLimitExceededError(TradingSystemError):
    """리스크 한도 초과 예외"""
    pass

# 예외 처리 패턴
async def place_order(order: Order) -> OrderResult:
    try:
        # 리스크 체크
        risk_result = await risk_engine.check_order(order)
        if not risk_result.approved:
            raise RiskLimitExceededError(risk_result.reason)

        # 주문 실행
        result = await broker_client.place_order(order)
        return result

    except InsufficientFundsError as e:
        logger.warning(f"Insufficient funds for order {order.id}: {e}")
        await self.event_bus.publish("order_failed", {
            "order_id": order.id,
            "reason": "insufficient_funds",
            "error": str(e)
        })
        raise

    except Exception as e:
        logger.error(f"Unexpected error placing order {order.id}: {e}")
        await self.event_bus.publish("system_error", {
            "component": "order_engine",
            "error": str(e),
            "order_id": order.id
        })
        raise TradingSystemError(f"Order placement failed: {e}")
```

### 7.2 테스트 전략

#### 테스트 레벨

1. **단위 테스트**: 개별 함수/클래스 테스트
2. **통합 테스트**: 컴포넌트 간 상호작용 테스트
3. **시스템 테스트**: 전체 시스템 엔드투엔드 테스트
4. **성능 테스트**: 부하 테스트 및 메모리 사용량 검증

#### 백테스팅 테스트

```python
class BacktestFramework:
    def __init__(self, historical_data: List[MarketDataEvent]):
        self.historical_data = historical_data
        self.portfolio = Portfolio(initial_cash=2_000_000)

    async def run_backtest(self, strategy: BaseStrategy) -> BacktestResult:
        """전략 백테스팅 실행"""
        for data_point in self.historical_data:
            # 기술 지표 계산
            indicators = await self.calculate_indicators(data_point)

            # 전략 실행
            signal = await strategy.analyze(data_point, indicators)

            if signal and signal.action != "HOLD":
                # 가상 주문 실행
                await self.execute_virtual_order(signal)

        return BacktestResult(
            total_return=self.portfolio.get_total_return(),
            max_drawdown=self.portfolio.get_max_drawdown(),
            win_rate=self.portfolio.get_win_rate(),
            sharpe_ratio=self.portfolio.get_sharpe_ratio()
        )
```

---

## 8. 모니터링 및 로깅

### 8.1 구조화된 로깅

```python
import structlog

# 로그 설정
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# 사용 예시
logger = structlog.get_logger()

async def place_order(order: Order):
    logger.info("Order placement started",
                order_id=order.id,
                symbol=order.symbol,
                quantity=order.quantity)

    try:
        result = await broker.place_order(order)
        logger.info("Order placed successfully",
                   order_id=order.id,
                   execution_price=result.price,
                   execution_time=result.timestamp)
    except Exception as e:
        logger.error("Order placement failed",
                    order_id=order.id,
                    error=str(e),
                    exc_info=True)
```

### 8.2 메트릭 수집

```python
from prometheus_client import Counter, Histogram, Gauge

# 메트릭 정의
ORDERS_TOTAL = Counter('trading_orders_total', 'Total orders placed', ['symbol', 'side', 'status'])
ORDER_LATENCY = Histogram('trading_order_latency_seconds', 'Order execution latency')
PORTFOLIO_VALUE = Gauge('portfolio_value_krw', 'Current portfolio value in KRW')
ACTIVE_POSITIONS = Gauge('active_positions_count', 'Number of active positions')

# 메트릭 사용
async def place_order(order: Order):
    start_time = time.time()

    try:
        result = await broker.place_order(order)
        ORDERS_TOTAL.labels(symbol=order.symbol, side=order.side, status='success').inc()
        return result
    except Exception as e:
        ORDERS_TOTAL.labels(symbol=order.symbol, side=order.side, status='failed').inc()
        raise
    finally:
        ORDER_LATENCY.observe(time.time() - start_time)
```

---

## 9. 배포 및 운영

### 9.1 Docker 컨테이너 설계

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드
COPY . .

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 실행 명령
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.2 환경 설정 관리

```python
# app/config/settings.py
from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # 데이터베이스
    database_url: str
    redis_url: str

    # 외부 API
    kis_api_key: str
    kis_secret_key: str
    kis_websocket_url: str

    # 보안
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # 거래 설정
    default_portfolio_value: int = 2_000_000
    max_position_size_ratio: float = 0.1
    stop_loss_percentage: float = 0.05
    daily_loss_limit_ratio: float = 0.02

    # 성능 설정
    redis_max_memory: str = "150mb"
    postgres_shared_buffers: str = "128MB"
    max_workers: int = 4

    # 로깅
    log_level: str = "INFO"
    log_format: str = "json"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

---

이 아키텍처 설계 문서는 QB Trading System의 기술적 토대를 제공합니다. 시스템 구현 시 이 문서를 참조하여 일관성 있고 확장 가능한 코드를 작성할 수 있습니다.
