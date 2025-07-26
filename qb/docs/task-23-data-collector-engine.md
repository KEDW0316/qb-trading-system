# Task 23: 실시간 데이터 수집 WebSocket 클라이언트

## 개요

Task 23에서는 실시간 주식 데이터 수집을 위한 이벤트 기반 WebSocket 클라이언트 시스템을 구현했습니다. 이 시스템은 다중 데이터 소스로부터 실시간 데이터를 수집하고, 정규화하여 Redis에 저장하며, 이벤트 버스를 통해 다른 엔진들에게 알림을 전송합니다.

## 아키텍처

### 핵심 컴포넌트

1. **DataCollector**: 메인 엔진 클래스
2. **BaseDataAdapter**: 추상 어댑터 인터페이스
3. **KISDataAdapter**: 한국투자증권 WebSocket 어댑터
4. **NaverDataAdapter**: 네이버 파이낸스 HTTP 폴링 어댑터
5. **YahooDataAdapter**: Yahoo Finance HTTP 폴링 어댑터
6. **DataNormalizer**: 다중 소스 데이터 정규화
7. **ConnectionManager**: 연결 관리 및 자동 재연결
8. **DataQualityChecker**: 데이터 품질 검증 및 이상치 탐지

### 이벤트 기반 아키텍처

```
[Data Sources] → [Adapters] → [DataCollector] → [DataNormalizer] → [QualityChecker] → [Redis + EventBus]
```

## 주요 기능

### 1. 실시간 데이터 수집

- **WebSocket 연결**: KIS API를 통한 실시간 데이터 스트리밍
- **HTTP 폴링**: Naver/Yahoo API를 통한 주기적 데이터 수집
- **자동 재연결**: 연결 실패 시 자동 재시도 메커니즘

### 2. 데이터 정규화

다양한 소스의 데이터를 표준 형식으로 변환:

```python
{
    "symbol": "005930",
    "timestamp": "2025-01-26T15:30:00",
    "open": 74800.0,
    "high": 75200.0,
    "low": 74600.0,
    "close": 75000.0,
    "volume": 1000000,
    "change": 200.0,
    "change_rate": 0.27,
    "source": "kis"
}
```

### 3. 데이터 품질 검증

- **필수 필드 검증**: symbol, timestamp, close 필드 확인
- **데이터 타입 검증**: 숫자 타입 및 범위 검증
- **이상치 탐지**: 통계적 방법을 통한 가격/거래량 이상치 감지
- **중복 데이터 필터링**: 동일한 타임스탬프/가격 데이터 제거
- **오래된 데이터 감지**: 지연된 데이터 식별

### 4. Redis Rolling 업데이트

- **실시간 데이터**: `market_data:{symbol}` 키에 최신 데이터 저장
- **캔들 데이터**: `candles:{symbol}` 리스트에 최대 200개 캔들 유지
- **Rolling 업데이트**: 새 데이터 추가 시 오래된 데이터 자동 제거

### 5. 이벤트 발행

수집된 데이터를 `market_data_received` 이벤트로 발행:

```python
{
    "event_type": "market_data_received",
    "data": {
        "symbol": "005930",
        "price_data": {...},
        "source": "kis",
        "collected_at": "2025-01-26T15:30:00"
    }
}
```

## 구현 세부사항

### DataCollector 클래스

```python
class DataCollector:
    """실시간 데이터 수집 엔진"""
    
    def __init__(self, redis_manager, event_bus, config):
        self.redis_manager = redis_manager
        self.event_bus = event_bus
        self.config = config
        self.status = EngineStatus.STOPPED
        
    async def start(self):
        """데이터 수집 시작"""
        
    async def _process_message(self, adapter_name, raw_data):
        """메시지 처리 파이프라인"""
        # 1. 데이터 정규화
        # 2. 품질 검증
        # 3. Redis 저장
        # 4. 이벤트 발행
```

### 어댑터 구현

#### KISDataAdapter (WebSocket)

```python
class KISDataAdapter(BaseDataAdapter):
    """한국투자증권 WebSocket 어댑터"""
    
    async def connect(self):
        """WebSocket 연결 및 인증"""
        
    async def subscribe_symbol(self, symbol):
        """심볼 구독"""
        
    async def _handle_message(self, message):
        """WebSocket 메시지 처리"""
```

#### NaverDataAdapter (HTTP Polling)

```python
class NaverDataAdapter(BaseDataAdapter):
    """네이버 파이낸스 HTTP 어댑터"""
    
    async def collect_data(self):
        """주기적 데이터 수집"""
        
    def _parse_naver_response(self, response):
        """네이버 응답 파싱"""
```

### 데이터 정규화

```python
class DataNormalizer:
    """데이터 정규화 클래스"""
    
    async def normalize(self, raw_data, source):
        """소스별 데이터 정규화"""
        
    def normalize_symbol(self, symbol, source):
        """심볼 정규화 (KIS: 005930, Yahoo: 005930.KS)"""
```

### 품질 검증

```python
class DataQualityChecker:
    """데이터 품질 검증기"""
    
    async def validate(self, data):
        """종합 데이터 검증"""
        
    def _check_price_outliers(self, data):
        """가격 이상치 검증 (Z-score 기반)"""
        
    def _check_volume_outliers(self, data):
        """거래량 이상치 검증"""
```

## 설정

### CollectionConfig

```python
@dataclass
class CollectionConfig:
    symbols: List[str]              # 수집 대상 심볼
    adapters: List[str]             # 사용할 어댑터
    max_candles: int = 200          # 최대 캔들 수
    collection_interval: float = 1.0  # 수집 간격
    quality_check_enabled: bool = True
    auto_restart: bool = True
    heartbeat_interval: int = 30
```

### 어댑터 설정

```python
# KIS 어댑터
kis_config = {
    'mode': 'real',  # 'real' or 'paper'
    'approval_key': 'your_approval_key',
    'max_retries': 3,
    'reconnect_delay': 5
}

# Naver 어댑터
naver_config = {
    'polling_interval': 10,  # 초
    'timeout': 5
}

# Yahoo 어댑터  
yahoo_config = {
    'polling_interval': 15,  # 초
    'timeout': 10
}
```

## 사용 예제

### 기본 사용법

```python
from qb.engines.data_collector import DataCollector, CollectionConfig
from qb.utils.redis_manager import RedisManager
from qb.utils.event_bus import EventBus

# 설정
config = CollectionConfig(
    symbols=['005930', '000660'],
    adapters=['kis', 'naver'],
    max_candles=200,
    collection_interval=1.0
)

# 초기화
redis_manager = RedisManager()
event_bus = EventBus(redis_manager)
collector = DataCollector(redis_manager, event_bus, config)

# 시작
await collector.start()

# 심볼 추가
await collector.add_symbol('005380')

# 상태 확인
status = await collector.get_status()
print(f"Status: {status['status']}")
print(f"Active symbols: {status['active_symbols']}")
print(f"Messages processed: {status['stats']['messages_processed']}")

# 중지
await collector.stop()
```

### 이벤트 구독

```python
async def handle_market_data(event):
    """시장 데이터 이벤트 핸들러"""
    symbol = event.data['symbol']
    price = event.data['price_data']['close']
    print(f"{symbol}: {price}")

# 이벤트 구독
event_bus.subscribe('market_data_received', handle_market_data)
```

## 모니터링 및 통계

### 수집 통계

```python
stats = await collector.get_stats()
print(f"Messages received: {stats['messages_received']}")
print(f"Messages processed: {stats['messages_processed']}")
print(f"Messages failed: {stats['messages_failed']}")
print(f"Uptime: {stats['uptime_seconds']} seconds")
```

### 품질 검증 통계

```python
quality_stats = collector.quality_checker.get_stats()
print(f"Total checks: {quality_stats['total_checks']}")
print(f"Passed: {quality_stats['passed_checks']}")
print(f"Failed: {quality_stats['failed_checks']}")
print(f"Issues by type: {quality_stats['issues_by_type']}")
```

## 오류 처리 및 복구

### 자동 재연결

- 연결 실패 시 지수 백오프 재시도
- 최대 재시도 횟수 제한
- 재연결 성공 시 심볼 재구독

### 데이터 품질 이슈 처리

- 경고(warning): 로그 기록만
- 높음(high): 로그 기록 + 통계 업데이트
- 치명적(critical): 데이터 처리 중단

### 어댑터 실패 처리

- 개별 어댑터 실패 시 다른 어댑터 계속 동작
- 실패한 어댑터 자동 재시작 시도
- 전체 시스템 안정성 유지

## 성능 최적화

### 메모리 관리

- Rolling 업데이트로 메모리 사용량 제한
- 과거 데이터 자동 정리
- 가비지 컬렉션 최적화

### 처리 성능

- 비동기 처리로 동시성 확보
- 배치 처리를 통한 Redis 쓰기 최적화
- 불필요한 데이터 복사 최소화

## 테스트

### 단위 테스트

- 각 컴포넌트별 독립 테스트
- Mock을 사용한 의존성 격리
- 비동기 테스트 프레임워크 활용

### 통합 테스트

- End-to-End 데이터 흐름 테스트
- 실제 Redis 연동 테스트
- 이벤트 발행/구독 테스트

### 테스트 실행

```bash
# 모든 테스트 실행
python -m pytest tests/test_data_collector_engine.py -v

# 특정 테스트 클래스 실행
python -m pytest tests/test_data_collector_engine.py::TestDataCollectorEngine -v

# 통합 테스트만 실행
python -m pytest tests/test_data_collector_engine.py -m integration -v
```

## 향후 개선 사항

### 단기 개선

1. **추가 데이터 소스**: 더 많은 증권사 API 지원
2. **데이터 압축**: 네트워크 트래픽 최적화
3. **캐시 최적화**: 중복 요청 방지

### 중기 개선

1. **분산 처리**: 다중 인스턴스 지원
2. **백업 전략**: 데이터 손실 방지
3. **알림 시스템**: 시스템 상태 모니터링

### 장기 개선

1. **머신러닝**: 이상치 탐지 정확도 향상
2. **예측 분석**: 데이터 트렌드 예측
3. **국제 시장**: 해외 주식 데이터 지원

## 관련 문서

- [Event Bus System](./event-bus-system.md)
- [Redis Data Structures](./redis-data-structures.md)
- [Technical Analysis Library](./task-26-technical-analysis-library.md)

## 라이센스

이 프로젝트는 MIT 라이센스를 따릅니다.