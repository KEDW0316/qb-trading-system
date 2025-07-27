# QB Trading System - 개발 환경 설정 가이드

## 개요

이 문서는 QB Trading System의 로컬 개발 환경 설정 방법과 각 구성 요소의 역할을 설명합니다.

## 아키텍처 개요

### 시스템 구성
- **Redis**: 실시간 데이터 버퍼 및 이벤트 버스
- **PostgreSQL + TimescaleDB**: 시계열 데이터 영구 저장소
- **Python Backend**: FastAPI 기반 트레이딩 엔진
- **8개 마이크로서비스 엔진**: 이벤트 기반 아키텍처

### 데이터 흐름
```
실시간 데이터 → Redis (빠른 읽기/쓰기) → PostgreSQL (영구 저장)
         ↓
    이벤트 발행 → 전략/리스크 엔진이 구독
```

## Docker Compose 환경

### 파일 구조
```
QB/
├── docker-compose.dev.yml    # 개발 환경 Docker 설정
├── scripts/
│   └── init-db.sql          # PostgreSQL 초기화 스크립트
└── .env                     # 환경 변수 설정
```

### 서비스 구성

#### 1. PostgreSQL + TimescaleDB
- **이미지**: `timescale/timescaledb:latest-pg15`
- **포트**: 5432
- **용도**: 
  - 시계열 주가 데이터 장기 보관
  - 거래 기록 및 전략 성과 저장
  - 시스템 로그 및 리스크 지표
- **메모리 할당**: 300MB
  - shared_buffers: 128MB
  - work_mem: 4MB
  - effective_cache_size: 168MB

#### 2. Redis
- **이미지**: `redis:7-alpine`
- **포트**: 6379
- **용도**:
  - 실시간 시장 데이터 버퍼 (0.001초 이내 조회)
  - 최근 200개 캔들 데이터 유지
  - Redis Pub/Sub 이벤트 버스
  - 기술적 지표 캐싱
- **메모리 할당**: 150MB
  - 시장 데이터: 50MB
  - 기술 지표: 30MB
  - 이벤트 큐: 20MB
  - 기타 캐시: 50MB

#### 3. 관리 도구
- **Adminer** (포트: 8080): PostgreSQL 웹 UI
- **Redis Commander** (포트: 8081): Redis 웹 UI

## 환경 설정

### .env 파일 구성
```bash
# Database Configuration
DATABASE_URL=postgresql://qb_user:qb_pass@localhost:5432/qb_trading_dev
REDIS_URL=redis://localhost:6379/0

# Environment
ENVIRONMENT=development

# System Settings
LOG_LEVEL=DEBUG
MAX_CANDLES_PER_SYMBOL=200
DATA_RETENTION_DAYS=365

# Performance Settings (1GB RAM 최적화)
POSTGRES_SHARED_BUFFERS=128MB
POSTGRES_WORK_MEM=4MB
REDIS_MAX_MEMORY=150MB

# KIS API Settings (기존 설정 유지)
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
# ... 기타 KIS 설정
```

## Docker 명령어

### 환경 시작
```bash
# 백그라운드에서 모든 서비스 시작
docker-compose -f docker-compose.dev.yml up -d

# 로그를 보면서 시작
docker-compose -f docker-compose.dev.yml up
```

### 상태 확인
```bash
# 실행 중인 컨테이너 확인
docker-compose -f docker-compose.dev.yml ps

# 서비스 로그 확인
docker-compose -f docker-compose.dev.yml logs -f [service_name]
```

### 데이터베이스 접속
```bash
# PostgreSQL 접속
psql postgresql://qb_user:qb_pass@localhost:5432/qb_trading_dev

# Redis 접속
redis-cli

# 또는 웹 UI 사용
# PostgreSQL: http://localhost:8080
# Redis: http://localhost:8081
```

### 환경 중지 및 정리
```bash
# 컨테이너 중지
docker-compose -f docker-compose.dev.yml down

# 데이터 포함 완전 삭제
docker-compose -f docker-compose.dev.yml down -v
```

## 데이터베이스 스키마

### PostgreSQL 테이블

#### 1. market_data (시계열 데이터)
- TimescaleDB 하이퍼테이블
- 7일 후 자동 압축
- 1년 후 자동 삭제

#### 2. trades (거래 기록)
- 모든 거래 내역 저장
- 전략별 성과 추적

#### 3. positions (포지션 정보)
- 현재 보유 종목
- 실시간 손익 계산

#### 4. strategy_performance (전략 성과)
- 일별 전략 성과 기록
- 백테스팅 결과 저장

#### 5. 기타 테이블
- stocks_metadata: 종목 정보
- risk_metrics: 리스크 지표
- system_logs: 시스템 로그

### Redis 데이터 구조

```
# 실시간 시장 데이터
market:{symbol} → Hash
  - timestamp, open, high, low, close, volume

# 캔들 데이터 (최근 200개)
candles:{symbol}:{interval} → List
  - JSON 형식의 캔들 데이터

# 기술적 지표
indicators:{symbol} → Hash
  - sma_20, rsi, macd, updated_at

# 이벤트 채널
events:market_data_received → Pub/Sub
events:trading_signal → Pub/Sub
events:order_executed → Pub/Sub
events:risk_alert → Pub/Sub
```

## 메모리 최적화 (1GB RAM 환경)

### 전체 메모리 할당
```
총 1GB RAM 분배:
├── 시스템 + OS: ~200MB
├── PostgreSQL: 300MB
├── Redis: 150MB
├── Python Backend: 250MB
├── 여유 공간: 100MB
```

### 최적화 전략
1. Redis에서 오래된 데이터 자동 삭제 (LRU 정책)
2. PostgreSQL 압축 정책으로 디스크 사용량 최소화
3. 연결 풀링으로 메모리 효율성 향상
4. 불필요한 데이터 즉시 정리

## 개발 워크플로우

### 1. 초기 설정
```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 실제 값 입력

# 2. Docker 환경 시작
docker-compose -f docker-compose.dev.yml up -d

# 3. 상태 확인
docker-compose -f docker-compose.dev.yml ps
```

### 2. 개발 중
```bash
# 로그 모니터링
docker-compose -f docker-compose.dev.yml logs -f

# 데이터베이스 확인
# PostgreSQL: http://localhost:8080
# Redis: http://localhost:8081
```

### 3. 테스트
```bash
# Python 환경에서
pytest tests/
```

## 배포 환경과의 차이점

### 개발 환경 (로컬)
- Docker Compose 사용
- 모든 서비스가 한 머신에서 실행
- 관리 UI 포함 (Adminer, Redis Commander)
- 디버그 로깅 활성화

### 운영 환경 (GCP)
- GCP Compute Engine e2-standard-2
- PostgreSQL: Cloud SQL 또는 VM 내 설치
- Redis: VM 내 설치
- 관리 UI 제외 (보안)
- 프로덕션 로깅 레벨

## 문제 해결

### PostgreSQL 연결 실패
```bash
# 컨테이너 상태 확인
docker-compose -f docker-compose.dev.yml ps

# PostgreSQL 로그 확인
docker-compose -f docker-compose.dev.yml logs postgres
```

### Redis 메모리 부족
```bash
# Redis 메모리 사용량 확인
redis-cli info memory

# 메모리 정리
redis-cli FLUSHDB
```

### 디스크 공간 부족
```bash
# Docker 볼륨 정리
docker system prune -a --volumes
```

## 다음 단계

1. Docker 환경 시작 후 애플리케이션 개발
2. Task 20: PostgreSQL 스키마 구현
3. Task 25: 전략 엔진 개발
4. Task 28: 주문 관리 시스템 구현

## 참고 문서

- [아키텍처 설계 문서](../../.taskmaster/docs/architecture_design.md)
- [Task 23: 데이터 수집 엔진](./task-23-data-collector-engine.md)
- [Redis 데이터 구조](./redis-data-structures.md)
- [이벤트 버스 시스템](./event-bus-system.md)