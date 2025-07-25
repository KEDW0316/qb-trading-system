# QB Trading System 테스트 도구

QB Trading System의 각 컴포넌트 상태를 확인하고 성능을 테스트하는 도구 모음입니다.

## 📁 디렉토리 구조

```
tools/
├── health_checks/      # 헬스체크 도구들
├── performance/        # 성능 테스트 도구들
├── data_validation/    # 데이터 검증 도구들
└── README.md          # 이 문서
```

## 🔍 헬스체크 도구 (health_checks/)

### Redis 연결 테스트

**파일**: `health_checks/redis_connection_test.py`

Redis 서버의 연결 상태, 메모리 사용량, 기본 기능을 확인합니다.

#### 기본 사용법

```bash
# 기본 테스트 (localhost:6379)
python tools/health_checks/redis_connection_test.py

# 다른 서버 테스트
python tools/health_checks/redis_connection_test.py --host 192.168.1.100 --port 6380

# 상세 테스트 (Pub/Sub, 성능 측정 포함)
python tools/health_checks/redis_connection_test.py --detailed

# 상세 로그와 함께
python tools/health_checks/redis_connection_test.py --detailed --verbose
```

#### 테스트 항목

- ✅ **기본 테스트 (4개 항목)**:

  - Redis 서버 연결 확인
  - 서버 정보 조회 (버전, 가동시간, 클라이언트 수)
  - 메모리 사용량 확인
  - 데이터 저장/조회/TTL/삭제

- ✅ **상세 테스트 (추가 3개 항목)**:
  - Pub/Sub 기능 확인
  - 키 공간 통계
  - 성능 측정 (ops/sec)

#### 종료 코드

- `0`: 모든 테스트 성공
- `1`: 일부 또는 전체 테스트 실패

### 향후 추가 예정 도구들

- `postgres_connection_test.py` - PostgreSQL/TimescaleDB 연결 테스트
- `kis_api_test.py` - 한국투자증권 API 연결 테스트
- `system_health_check.py` - 전체 시스템 상태 종합 확인

## 🚀 성능 테스트 도구 (performance/)

### 향후 추가 예정

- `redis_benchmark.py` - Redis 성능 벤치마크
- `data_processing_benchmark.py` - 데이터 처리 성능 측정

## ✅ 데이터 검증 도구 (data_validation/)

### 향후 추가 예정

- `market_data_validator.py` - 시장 데이터 유효성 검증
- `trading_signal_validator.py` - 트레이딩 신호 검증

## 🔧 CI/CD 통합

이 도구들은 다음과 같이 CI/CD 파이프라인에서 활용할 수 있습니다:

```bash
# 헬스체크를 통한 배포 전 확인
python tools/health_checks/redis_connection_test.py || exit 1
python tools/health_checks/postgres_connection_test.py || exit 1

# 성능 회귀 테스트
python tools/performance/redis_benchmark.py --duration 30s --threshold 10000
```

## 📝 새로운 도구 추가 가이드

### 네이밍 컨벤션

- **연결 테스트**: `{component}_connection_test.py`
- **성능 테스트**: `{component}_benchmark.py`
- **데이터 검증**: `{data_type}_validator.py`
- **모니터링 도구**: `{component}_monitor.py`

### 기본 구조

```python
#!/usr/bin/env python3
"""
{컴포넌트} 테스트 도구
QB Trading System용 {목적} 유틸리티
"""

import sys
import os
import argparse
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'qb'))

def main():
    parser = argparse.ArgumentParser(description='{설명}')
    # 인자 정의...

    args = parser.parse_args()

    # 테스트 실행...
    success = run_tests(args)

    # 종료 코드: 성공(0), 실패(1)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
```

## 🎯 사용 시나리오

### 개발 중 빠른 확인

```bash
# Redis 상태 확인
python tools/health_checks/redis_connection_test.py

# 성능이 느려졌는지 확인
python tools/health_checks/redis_connection_test.py --detailed
```

### 배포 전 검증

```bash
# 모든 컴포넌트 헬스체크
for test in tools/health_checks/*_test.py; do
    python "$test" || echo "❌ $test failed"
done
```

### 문제 진단

```bash
# 상세 로그와 함께 문제 분석
python tools/health_checks/redis_connection_test.py --detailed --verbose
```
