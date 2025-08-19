# Phase 1.2: KIS API 인증 시스템 세부 구현 가이드

## 🎯 목표
**KIS OpenAPI 인증 시스템 및 Rate Limiter 구현 완료**

**예상 소요시간**: 3-4시간  
**난이도**: ⭐⭐⭐☆☆ (중급)

---

## 📂 1.2.1 KISAuthManager 클래스 설계 (2시간)

### 핵심 기능 분석
- **OAuth2 토큰 발급/갱신** (`/oauth2/tokenP`)
- **토큰 파일 저장/로드** (JSON 형태)
- **토큰 유효성 검증** (만료시간 체크)
- **실전/모의투자 환경 분리**

### 클래스 구조 설계

```python
# src/auth/kis_auth.py
class KISAuthManager:
    """KIS API 인증 및 토큰 관리 클래스"""
    
    def __init__(self, env: str = "vps"):
        """
        초기화
        Args:
            env: "prod" (실전투자) or "vps" (모의투자)
        """
    
    # === 핵심 공개 메서드 ===
    async def get_access_token(self) -> str:
        """액세스 토큰 조회 (자동 갱신 포함)"""
    
    async def get_websocket_approval_key(self) -> str:
        """WebSocket 인증키 조회"""
    
    def get_headers(self) -> dict:
        """API 호출용 헤더 생성"""
    
    # === 토큰 관리 (내부) ===
    async def _issue_new_token(self) -> TokenInfo:
        """새 토큰 발급 (OAuth2 /tokenP 호출)"""
    
    async def _issue_websocket_key(self) -> str:
        """WebSocket 인증키 발급"""
    
    def _save_token_to_file(self, token_info: TokenInfo) -> None:
        """토큰을 JSON 파일로 저장"""
    
    def _load_token_from_file(self) -> Optional[TokenInfo]:
        """JSON 파일에서 토큰 로드"""
    
    def _is_token_valid(self, token_info: Optional[TokenInfo]) -> bool:
        """토큰 유효성 검증 (만료시간 체크)"""
    
    def _get_token_expiry_time(self, expires_in: int) -> datetime:
        """토큰 만료시간 계산"""
    
    # === 환경 설정 (내부) ===
    def _get_api_base_url(self) -> str:
        """환경별 API Base URL 반환"""
    
    def _get_websocket_url(self) -> str:
        """환경별 WebSocket URL 반환"""
    
    def _get_token_file_path(self) -> str:
        """토큰 파일 경로 생성"""
    
    # === 에러 처리 ===
    def _handle_auth_error(self, response: dict) -> None:
        """인증 에러 처리"""
```

### 데이터 클래스 설계

```python
# src/auth/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class TokenInfo:
    """토큰 정보 데이터 클래스"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400  # 24시간 (초)
    expires_at: Optional[datetime] = None
    created_at: datetime = None
    
    def is_expired(self) -> bool:
        """토큰 만료 여부 확인"""
    
    def time_until_expiry(self) -> int:
        """만료까지 남은 시간 (초)"""

@dataclass
class KISCredentials:
    """KIS API 인증 정보"""
    app_key: str
    app_secret: str
    account_no: str
    account_prod_cd: str = "01"
    
    @classmethod
    def from_env(cls) -> "KISCredentials":
        """환경변수에서 인증정보 로드"""

@dataclass
class APIEndpoints:
    """KIS API 엔드포인트 정의"""
    base_url: str
    token_path: str = "/oauth2/tokenP"
    websocket_auth_path: str = "/oauth2/Approval"
    websocket_url: str = ""
    
    @classmethod
    def get_prod_endpoints(cls) -> "APIEndpoints":
        """실전투자 엔드포인트"""
    
    @classmethod
    def get_vps_endpoints(cls) -> "APIEndpoints":
        """모의투자 엔드포인트"""
```

### 예외 클래스 설계

```python
# src/auth/exceptions.py
class KISAuthError(Exception):
    """KIS 인증 관련 기본 예외"""
    pass

class TokenExpiredError(KISAuthError):
    """토큰 만료 예외"""
    pass

class TokenIssueError(KISAuthError):
    """토큰 발급 실패 예외"""
    pass

class InvalidCredentialsError(KISAuthError):
    """잘못된 인증 정보 예외"""
    pass

class RateLimitExceededError(KISAuthError):
    """Rate Limit 초과 예외"""
    pass
```

---

## 🛡️ 1.2.2 Rate Limiter 구현 (1시간)

### Rate Limiter 설계 목적
- **KIS API 제한**: 초당 20건, 토큰 발급 분당 1회
- **지수 백오프**: 에러 발생시 재시도 간격 증가
- **배치 처리**: 여러 요청을 효율적으로 관리

### 클래스 구조

```python
# src/utils/rate_limiter.py
import asyncio
import time
from collections import deque
from typing import Optional

class RateLimiter:
    """KIS API Rate Limit 관리 클래스"""
    
    def __init__(self, 
                 max_calls: int = 18,      # 안전 마진 (KIS: 20건)
                 time_window: float = 1.0,  # 1초 윈도우
                 burst_limit: int = 5):     # 버스트 제한
        """Rate Limiter 초기화"""
    
    # === 공개 메서드 ===
    async def acquire(self, priority: int = 0) -> None:
        """Rate Limit 체크 및 대기"""
    
    async def wait_if_needed(self) -> float:
        """필요시 대기하고 대기 시간 반환"""
    
    def get_remaining_calls(self) -> int:
        """현재 윈도우에서 남은 호출 횟수"""
    
    def get_reset_time(self) -> float:
        """다음 리셋까지 남은 시간 (초)"""
    
    # === 내부 메서드 ===
    def _cleanup_old_calls(self) -> None:
        """시간 윈도우 밖의 호출 기록 정리"""
    
    def _calculate_wait_time(self) -> float:
        """다음 호출까지 대기 시간 계산"""
    
    def _record_call(self) -> None:
        """호출 기록 추가"""

class ExponentialBackoff:
    """지수 백오프 재시도 관리"""
    
    def __init__(self,
                 initial_delay: float = 0.1,
                 max_delay: float = 60.0,
                 multiplier: float = 2.0,
                 max_retries: int = 5):
        """백오프 설정 초기화"""
    
    async def wait(self, attempt: int) -> float:
        """재시도 대기 (지수적 증가)"""
    
    def calculate_delay(self, attempt: int) -> float:
        """재시도 지연 시간 계산"""
    
    def reset(self) -> None:
        """백오프 상태 리셋"""

class PriorityQueue:
    """우선순위 큐 (중요한 API 호출 우선 처리)"""
    
    def __init__(self):
        """우선순위 큐 초기화"""
    
    async def put(self, item: any, priority: int = 0) -> None:
        """아이템 추가 (낮은 숫자 = 높은 우선순위)"""
    
    async def get(self) -> any:
        """우선순위 순으로 아이템 조회"""
    
    def empty(self) -> bool:
        """큐가 비어있는지 확인"""
```

---

## 🌐 1.2.3 HTTP Client 래퍼 (30분)

### API 호출 래퍼 설계

```python
# src/auth/api_client.py
import aiohttp
from typing import Dict, Optional, Any

class KISAPIClient:
    """KIS API HTTP 클라이언트 래퍼"""
    
    def __init__(self, auth_manager: KISAuthManager, rate_limiter: RateLimiter):
        """클라이언트 초기화"""
    
    # === 공개 메서드 ===
    async def post(self, endpoint: str, data: dict, **kwargs) -> dict:
        """POST 요청"""
    
    async def get(self, endpoint: str, params: Optional[dict] = None, **kwargs) -> dict:
        """GET 요청"""
    
    async def put(self, endpoint: str, data: dict, **kwargs) -> dict:
        """PUT 요청"""
    
    # === 내부 메서드 ===
    async def _make_request(self, 
                          method: str, 
                          endpoint: str, 
                          data: Optional[dict] = None,
                          params: Optional[dict] = None,
                          headers: Optional[dict] = None,
                          **kwargs) -> dict:
        """실제 HTTP 요청 수행"""
    
    def _prepare_headers(self, custom_headers: Optional[dict] = None) -> dict:
        """요청 헤더 준비"""
    
    def _handle_response(self, response: aiohttp.ClientResponse) -> dict:
        """응답 처리 및 에러 체크"""
    
    def _is_retry_needed(self, response: dict, status_code: int) -> bool:
        """재시도 필요 여부 판단"""
    
    async def _retry_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """재시도 로직"""
```

---

## 🧪 1.2.4 단위 테스트 설계 (30분)

### 테스트 구조

```python
# tests/test_auth/test_kis_auth.py
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

class TestKISAuthManager:
    """KISAuthManager 테스트 클래스"""
    
    def setup_method(self):
        """각 테스트 전 초기화"""
    
    def test_init_with_valid_env(self):
        """유효한 환경으로 초기화 테스트"""
    
    def test_init_with_invalid_env(self):
        """잘못된 환경 초기화 테스트"""
    
    @pytest.mark.asyncio
    async def test_get_access_token_success(self):
        """토큰 조회 성공 테스트"""
    
    @pytest.mark.asyncio
    async def test_get_access_token_expired_auto_renew(self):
        """만료된 토큰 자동 갱신 테스트"""
    
    @pytest.mark.asyncio
    async def test_issue_new_token_success(self):
        """새 토큰 발급 성공 테스트"""
    
    @pytest.mark.asyncio
    async def test_issue_new_token_failure(self):
        """토큰 발급 실패 테스트"""
    
    def test_save_and_load_token(self):
        """토큰 저장/로드 테스트"""
    
    def test_is_token_valid(self):
        """토큰 유효성 검증 테스트"""

# tests/test_utils/test_rate_limiter.py
class TestRateLimiter:
    """RateLimiter 테스트 클래스"""
    
    def setup_method(self):
        """테스트 초기화"""
    
    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """제한 내 호출 테스트"""
    
    @pytest.mark.asyncio
    async def test_acquire_exceeds_limit(self):
        """제한 초과시 대기 테스트"""
    
    def test_get_remaining_calls(self):
        """남은 호출 횟수 계산 테스트"""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """지수 백오프 테스트"""
```

---

## 📁 파일 구조

```
src/auth/
├── __init__.py
├── kis_auth.py          # KISAuthManager 메인 클래스
├── models.py            # 데이터 클래스들
├── exceptions.py        # 예외 클래스들
├── api_client.py        # HTTP 클라이언트 래퍼
└── config.py           # 인증 관련 설정

src/utils/
├── __init__.py
├── rate_limiter.py      # RateLimiter 구현
└── logger.py           # 로깅 유틸리티

tests/test_auth/
├── __init__.py
├── test_kis_auth.py     # KISAuthManager 테스트
├── test_models.py       # 데이터 클래스 테스트
├── test_api_client.py   # API 클라이언트 테스트
└── conftest.py         # 테스트 설정

tests/test_utils/
├── __init__.py
├── test_rate_limiter.py # RateLimiter 테스트
└── conftest.py
```

---

## ✅ 구현 순서 및 체크리스트

### Step 1: 기본 구조 생성 (30분)
- [ ] 디렉터리 구조 생성
- [ ] `__init__.py` 파일들 생성
- [ ] 기본 임포트 설정

### Step 2: 데이터 모델 구현 (30분)
- [ ] `TokenInfo` 데이터클래스
- [ ] `KISCredentials` 데이터클래스 
- [ ] `APIEndpoints` 데이터클래스
- [ ] 예외 클래스들 정의

### Step 3: Rate Limiter 구현 (30분)
- [ ] `RateLimiter` 기본 기능
- [ ] `ExponentialBackoff` 구현
- [ ] 우선순위 큐 (선택사항)

### Step 4: KISAuthManager 핵심 기능 (1시간)
- [ ] 초기화 및 설정
- [ ] 토큰 발급 로직 (`_issue_new_token`)
- [ ] 토큰 저장/로드 (`_save_token_to_file`, `_load_token_from_file`)
- [ ] 토큰 유효성 검증 (`_is_token_valid`)

### Step 5: 공개 인터페이스 구현 (30분)
- [ ] `get_access_token` 메서드
- [ ] `get_websocket_approval_key` 메서드
- [ ] `get_headers` 메서드
- [ ] 에러 처리 로직

### Step 6: 단위 테스트 작성 (30분)
- [ ] KISAuthManager 기본 테스트
- [ ] RateLimiter 테스트
- [ ] Mock을 활용한 API 호출 테스트

---

## 🎯 핵심 검증 포인트

### 토큰 관리
- ✅ 24시간 만료 토큰 자동 갱신
- ✅ 6시간 내 재발급시 기존 토큰 유지 (KIS 정책)
- ✅ 실전/모의투자 환경 분리

### Rate Limiting
- ✅ 초당 20건 제한 준수 (안전 마진 18건)
- ✅ 토큰 발급 분당 1회 제한
- ✅ 429 에러시 지수 백오프 적용

### 안정성
- ✅ 네트워크 에러 재시도
- ✅ 토큰 파일 손상 대응
- ✅ 인증 실패 로깅 및 알림

---

## 🔗 다음 단계 연계

완료 후 **Phase 1.3: WebSocket 실시간 데이터 시스템**에서 이 인증 시스템을 활용합니다.

**주요 연계 포인트**:
- `auth_manager.get_websocket_approval_key()` → WebSocket 인증
- `auth_manager.get_headers()` → REST API 호출
- `rate_limiter.acquire()` → 모든 API 호출 전 체크