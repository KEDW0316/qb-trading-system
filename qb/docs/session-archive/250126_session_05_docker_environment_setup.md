# Session Archive: 250126 Session 05 - Docker 개발 환경 구성

## 세션 개요

**날짜**: 2025년 1월 26일  
**세션 목적**: PostgreSQL/TimescaleDB 및 Redis Docker 개발 환경 구성  
**주요 성과**: Docker Compose 환경 구성, 문서화, Task 20 준비 완료

## 작업 컨텍스트

### 시작 상황
- Task 23 (실시간 데이터 수집 엔진) 완료
- GitHub에 커밋 및 푸시 완료
- 다음 Task 확인 중

### Task 현황 분석
- **완료된 HIGH 우선순위**: Task 19, 21, 22, 23, 26 (5개)
- **남은 HIGH 우선순위**: Task 25, 28, 29, 39 (4개)
- **다음 추천 Task**: Task 20 (PostgreSQL/TimescaleDB) - 여러 HIGH Task의 의존성

## 주요 작업 내용

### 1. 개발 환경 고민 및 결정

**고민사항**: 로컬 개발 환경에서 PostgreSQL/TimescaleDB를 어떻게 구성할 것인가?

**검토한 옵션들**:
1. Docker Compose 로컬 환경 (선택됨)
2. 하이브리드 접근 (SQLite → PostgreSQL)
3. 클라우드 개발 DB

**선택 이유**: 
- 배포 환경과 동일한 구성
- TimescaleDB 기능을 처음부터 활용
- 쉬운 초기화/리셋

### 2. 아키텍처 문서 기반 DB 역할 이해

#### Redis (실시간 메모리 DB)
- **용도**: 실시간 데이터 버퍼, 이벤트 버스
- **메모리**: 150MB (시장 데이터 50MB, 지표 30MB, 이벤트 20MB, 캐시 50MB)
- **데이터**: `market:005930`, `candles:005930:1m`, `indicators:005930`
- **특징**: 0.001초 이내 조회, Pub/Sub 이벤트

#### PostgreSQL + TimescaleDB (영구 저장소)
- **용도**: 시계열 데이터 장기 보관, 거래 기록
- **메모리**: 300MB (shared_buffers 128MB, work_mem 4MB)
- **테이블**: market_data, trades, positions, strategy_performance
- **특징**: 하이퍼테이블, 7일 압축, 1년 보존

### 3. Docker Compose 환경 구성

#### 생성된 파일들

**docker-compose.dev.yml**:
```yaml
services:
  postgres:
    image: timescale/timescaledb:latest-pg15
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: qb_trading_dev
      POSTGRES_USER: qb_user
      POSTGRES_PASSWORD: qb_pass
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --maxmemory 150mb --maxmemory-policy allkeys-lru
  
  redis-commander:  # Redis UI
    ports: ["8081:8081"]
  
  adminer:  # PostgreSQL UI
    ports: ["8080:8080"]
```

**scripts/init-db.sql**:
- TimescaleDB 확장 활성화
- 7개 테이블 생성 (market_data, trades, positions 등)
- 하이퍼테이블 설정
- 압축 정책 (7일) 및 보존 정책 (1년)
- 인덱스 생성

### 4. 환경 설정 통합

**.env 파일 업데이트**:
```bash
# 기존 KIS API 설정 유지
# + 추가된 DB 설정
DATABASE_URL=postgresql://qb_user:qb_pass@localhost:5432/qb_trading_dev
REDIS_URL=redis://localhost:6379/0
ENVIRONMENT=development
LOG_LEVEL=DEBUG
MAX_CANDLES_PER_SYMBOL=200
DATA_RETENTION_DAYS=365
POSTGRES_SHARED_BUFFERS=128MB
POSTGRES_WORK_MEM=4MB
REDIS_MAX_MEMORY=150MB
```

**.env.example 업데이트**: DB 설정 추가

### 5. 문서화

**development-environment-setup.md** 작성:
- Docker 환경 상세 설명
- 각 DB의 역할과 메모리 할당
- Docker 명령어 가이드
- 데이터베이스 스키마 설명
- 문제 해결 방법

## 기술적 결정사항

### 1. 메모리 최적화 (1GB RAM 환경)
```
총 1GB 분배:
├── 시스템 + OS: ~200MB
├── PostgreSQL: 300MB
├── Redis: 150MB
├── Python Backend: 250MB
└── 여유 공간: 100MB
```

### 2. 데이터 관리 전략
- **Redis**: Rolling Update로 최근 200개 캔들만 유지
- **PostgreSQL**: TimescaleDB 압축으로 저장 공간 최적화
- **보존 정책**: 시장 데이터 1년, 시스템 로그 30일

### 3. 개발 워크플로우
1. Docker Compose로 로컬 환경 구성
2. 개발 중 관리 UI 활용 (Adminer, Redis Commander)
3. 배포 시 동일한 구성을 GCP에 적용

## 다음 세션을 위한 준비

### 환경 시작 명령어
```bash
# Docker 환경 시작
docker-compose -f docker-compose.dev.yml up -d

# 상태 확인
docker-compose -f docker-compose.dev.yml ps

# DB 접속 확인
psql postgresql://qb_user:qb_pass@localhost:5432/qb_trading_dev
redis-cli ping
```

### Task 20 작업 계획
1. Docker 환경 시작 및 확인
2. SQLAlchemy ORM 모델 구현
   - `qb/database/models.py`
   - 7개 테이블 모델 정의
3. 데이터베이스 연결 관리 클래스
   - `qb/database/connection.py`
   - 연결 풀 관리
4. 테스트 작성

### 현재 프로젝트 상태
- **완료된 엔진**: DataCollector, TechnicalAnalyzer
- **완료된 인프라**: Redis 이벤트 버스, KIS API 통합
- **준비된 환경**: Docker Compose (PostgreSQL + Redis)
- **다음 목표**: 데이터 영속성 레이어 구축

## 참고사항

### 파일 위치
- Docker 설정: `/Users/dongwon/project/QB/docker-compose.dev.yml`
- DB 초기화: `/Users/dongwon/project/QB/scripts/init-db.sql`
- 환경 변수: `/Users/dongwon/project/QB/.env`
- 개발 가이드: `/Users/dongwon/project/QB/qb/docs/development-environment-setup.md`

### 관리 UI 접속
- PostgreSQL: http://localhost:8080 (Adminer)
- Redis: http://localhost:8081 (Redis Commander)

### 주의사항
- `.env` 파일은 `.gitignore`에 포함되어 있음
- 민감한 정보는 절대 커밋하지 않기
- Docker 볼륨은 `docker-compose down -v`로 완전 삭제 가능

## 세션 요약

이번 세션에서는 Task 20 (PostgreSQL/TimescaleDB)을 위한 완벽한 개발 환경을 구성했습니다. Docker Compose를 사용하여 로컬에서 배포 환경과 동일한 구성을 만들었고, 각 DB의 역할과 메모리 할당을 아키텍처 문서 기반으로 최적화했습니다. 

다음 세션에서는 Docker 환경을 시작하고 실제 ORM 모델 구현을 진행하면 됩니다. 모든 준비가 완료되었으므로 바로 개발에 착수할 수 있습니다.