# Phase 1.1: 프로젝트 설정 세부 구현 가이드

## 🎯 목표
**KIS 자동매매 프로그램의 기반 프로젝트 구조 및 환경 설정 완료**

**예상 소요시간**: 4-6시간  
**난이도**: ⭐⭐☆☆☆ (초급-중급)

---

## 📂 1.1.1 프로젝트 디렉터리 구조 생성 (1시간)

### 기본 디렉터리 구조
```
qb_project/
├── src/                          # 소스 코드
│   ├── __init__.py
│   ├── auth/                     # 인증 관련
│   │   ├── __init__.py
│   │   └── kis_auth.py
│   ├── data/                     # 데이터 처리
│   │   ├── __init__.py
│   │   ├── market_data.py
│   │   └── websocket_handler.py
│   ├── strategy/                 # 매매 전략
│   │   ├── __init__.py
│   │   └── rsi_strategy.py
│   ├── trading/                  # 주문 처리
│   │   ├── __init__.py
│   │   ├── trading_engine.py
│   │   └── risk_manager.py
│   ├── utils/                    # 유틸리티
│   │   ├── __init__.py
│   │   ├── rate_limiter.py
│   │   └── logger.py
│   └── main.py                   # 메인 실행 파일
├── tests/                        # 테스트 코드
│   ├── __init__.py
│   ├── test_auth/
│   ├── test_data/
│   ├── test_strategy/
│   └── test_trading/
├── config/                       # 설정 파일
│   ├── config.yaml
│   └── logging.yaml
├── data/                         # 데이터 저장소
│   ├── db/                       # SQLite 파일들
│   └── cache/                    # 캐시 파일들
├── logs/                         # 로그 파일들
├── docs/                         # 문서
├── requirements.txt              # Python 패키지 의존성
├── .env.example                  # 환경변수 예시
├── .gitignore                    # Git 무시 파일
├── README.md                     # 프로젝트 설명
└── run.py                        # 실행 스크립트
```

### 작업 단계:
1. **터미널에서 디렉터리 생성**:
   ```bash
   mkdir -p src/{auth,data,strategy,trading,utils}
   mkdir -p tests/{test_auth,test_data,test_strategy,test_trading}
   mkdir -p config data/{db,cache} logs docs
   ```

2. **`__init__.py` 파일 생성**:
   ```bash
   touch src/__init__.py
   touch src/{auth,data,strategy,trading,utils}/__init__.py
   touch tests/__init__.py
   touch tests/{test_auth,test_data,test_strategy,test_trading}/__init__.py
   ```

---

## 🐍 1.1.2 uv 설정 및 의존성 관리 (30분)

### uv 설치 및 프로젝트 초기화
```bash
# uv 설치 (macOS/Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# uv 설치 (Windows - PowerShell)
# powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# uv 설치 (Homebrew - macOS)
brew install uv

# Python 3.11+ 설치 및 확인
uv python install 3.11
uv python pin 3.11  # 프로젝트에 Python 버전 고정

# 프로젝트 초기화
uv init --name kis-trading --package
```

### pyproject.toml 작성 (uv로 관리)
```toml
[project]
name = "kis-trading"
version = "0.1.0"
description = "KIS OpenAPI 자동매매 프로그램"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    # === 핵심 의존성 ===
    "aiohttp>=3.9.1",
    "aiofiles>=23.2.0",
    "websockets>=12.0",
    "asyncio-throttle>=1.0.2",
    
    # === 데이터 처리 ===
    "pandas>=2.1.4",
    "numpy>=1.26.2",
    "talib-binary>=0.4.19",  # TA-Lib 바이너리 (크로스 플랫폼)
    "aiosqlite>=0.19.0",
    
    # === 설정 및 검증 ===
    "pydantic>=2.5.2",
    "pydantic-settings>=2.1.0",
    "python-dotenv>=1.0.0",
    "PyYAML>=6.0.1",
    
    # === 스케줄링 ===
    "APScheduler>=3.10.4",
    
    # === 로깅 및 모니터링 ===
    "loguru>=0.7.2",
    "python-telegram-bot>=20.7",
]

[project.optional-dependencies]
dev = [
    # === 테스팅 ===
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "pytest-cov>=4.1.0",
    "faker>=21.0.0",
    "aioresponses>=0.7.4",
    
    # === 개발 도구 ===
    "black>=23.11.0",
    "isort>=5.13.2",
    "flake8>=6.1.0",
    "mypy>=1.7.1",
    
    # === 타입 힌트 ===
    "types-PyYAML>=6.0.12.12",
]

backtest = [
    # === 백테스팅 (선택사항) ===
    "backtrader>=1.9.78.123",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=7.4.3",
    "pytest-asyncio>=0.21.1",
    "pytest-cov>=4.1.0",
    "black>=23.11.0",
    "isort>=5.13.2",
    "flake8>=6.1.0",
    "mypy>=1.7.1",
]

[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
strict = true
```

### uv 명령어로 의존성 설치
```bash
# 가상환경 생성 및 의존성 설치 (한 번에!)
uv sync

# 개발 의존성까지 모두 설치
uv sync --extra dev

# 백테스팅 의존성 추가 설치
uv sync --extra dev --extra backtest

# 새로운 패키지 추가
uv add requests

# 개발 의존성으로 패키지 추가
uv add --dev pytest-mock

# 특정 버전 설치
uv add "pandas>=2.1.0,<3.0.0"

# TA-Lib 시스템 의존성 설치 (필요시)
# macOS
brew install ta-lib

# Ubuntu/Debian
sudo apt-get install libta-lib-dev

# 그 후 TA-Lib Python 바인딩 설치
uv add TA-Lib  # 시스템에 ta-lib 설치 후
# 또는 바이너리 버전 사용 (이미 pyproject.toml에 포함됨)
```

### uv 가상환경 사용
```bash
# uv로 명령어 실행 (가상환경 자동 활성화)
uv run python -m src.main

# uv shell로 가상환경 진입
uv shell

# 가상환경에서 나가기 (uv shell 사용시)
exit

# 의존성 업데이트
uv lock --upgrade

# lock 파일로 정확한 버전 재현
uv sync --frozen
```

---

## 🔐 1.1.3 환경변수 설정 (.env.example) (30분)

### .env.example 파일 생성
```bash
# ===========================================
# KIS API 설정
# ===========================================

# 한국투자증권 API 인증 정보
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here

# 계좌 정보
KIS_ACCOUNT_NO=your_account_number
KIS_ACCOUNT_PROD_CD=01  # 01: 종합계좌, 06: 펀드전용

# API 환경 설정
KIS_ENV=vps  # prod: 실전투자, vps: 모의투자
KIS_BASE_URL_PROD=https://openapi.koreainvestment.com:9443
KIS_BASE_URL_VPS=https://openapivts.koreainvestment.com:29443

# WebSocket 설정
KIS_WS_URL_PROD=wss://ops.koreainvestment.com:21000
KIS_WS_URL_VPS=wss://ops.koreainvestment.com:31000

# ===========================================
# 매매 전략 설정
# ===========================================

# RSI 전략 파라미터
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70
MA_SHORT_PERIOD=5
MA_LONG_PERIOD=20

# 리스크 관리
MAX_POSITION_SIZE=0.1  # 종목당 최대 10%
STOP_LOSS_PCT=-0.05    # 손절 -5%
TAKE_PROFIT_PCT=0.10   # 익절 +10%
MAX_DAILY_LOSS=-0.03   # 일일 최대 손실 -3%

# 매매 대상 종목 (쉼표로 구분)
TARGET_SYMBOLS=005930,000660,035420  # 삼성전자, SK하이닉스, NAVER

# ===========================================
# 시스템 설정
# ===========================================

# 데이터베이스
DATABASE_PATH=data/db/kis_trading.db

# 로깅 설정
LOG_LEVEL=INFO
LOG_FILE=logs/kis_trading.log
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=5

# API Rate Limiting (KIS 제한: 초당 20건)
API_MAX_CALLS_PER_SECOND=18  # 안전 마진
API_RATE_LIMIT_WINDOW=1.0

# 캐시 설정
CACHE_TTL_SECONDS=60
CACHE_CLEANUP_INTERVAL=300

# ===========================================
# 알림 설정
# ===========================================

# 텔레그램 봇
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# 알림 레벨 (INFO, WARNING, ERROR, CRITICAL)
NOTIFICATION_LEVEL=INFO

# ===========================================
# 개발/테스트 설정
# ===========================================

# 테스트 모드 (True: 실제 주문 없이 시뮬레이션)
TEST_MODE=True

# 백테스팅 기간 설정
BACKTEST_START_DATE=2024-01-01
BACKTEST_END_DATE=2024-12-31
BACKTEST_INITIAL_CASH=10000000  # 초기 자금 1천만원

# 개발 모드 (상세 디버그 로깅)
DEBUG_MODE=False
```

### 실제 .env 파일 생성 안내
```bash
# .env.example을 복사하여 실제 설정 파일 생성
cp .env.example .env

# .env 파일을 편집하여 실제 값 입력
# - KIS API 키와 계정 정보 입력
# - 텔레그램 봇 토큰 설정 (선택사항)
# - 기타 개인화 설정 조정
```

**⚠️ 보안 주의사항**:
- `.env` 파일은 절대 Git에 커밋하지 않기
- API 키는 안전한 곳에 별도 보관
- 실전 계정 정보는 신중하게 관리

---

## ⚙️ 1.1.4 기본 설정 파일 구성 (30분)

### config/config.yaml
```yaml
# KIS 자동매매 프로그램 기본 설정

# 시장 시간 설정
market:
  # 장 운영시간 (KST)
  trading_hours:
    start: "09:00:00"
    end: "15:30:00"
    lunch_start: "12:00:00"  # 점심시간 시작 (선택사항)
    lunch_end: "13:00:00"    # 점심시간 종료
  
  # 휴장일 체크
  exclude_weekends: true
  exclude_holidays: true
  holiday_api: "한국거래소"  # 공휴일 API 연동 (추후 구현)

# 데이터 처리 설정
data:
  # 차트 데이터 요청 설정
  daily_chart_period: 100      # 일봉 조회 기간 (일)
  minute_chart_period: 60      # 분봉 조회 기간 (분)
  
  # 실시간 데이터 버퍼 크기
  realtime_buffer_size: 1000   # 실시간 데이터 메모리 버퍼
  
  # 데이터 정리 주기
  data_cleanup_interval: 3600  # 1시간마다 오래된 데이터 정리

# 매매 전략 설정
strategy:
  # 기본 전략 타입
  default_strategy: "realtime_rsi"
  
  # 전략별 설정
  realtime_rsi:
    # 기술적 지표
    rsi_period: 14
    rsi_oversold: 30
    rsi_overbought: 70
    ma_short: 5
    ma_long: 20
    
    # 실시간 판단 기준
    bid_ask_spread_threshold: 0.01  # 호가 스프레드 1% 이내
    volume_surge_ratio: 1.5         # 평소 거래량 대비 1.5배
    
    # 신호 강도 기준
    min_signal_strength: 0.6        # 최소 신호 강도
    signal_timeout: 300             # 신호 유효시간 (초)

# 리스크 관리 설정
risk:
  # 포지션 관리
  max_positions: 3                 # 최대 동시 보유 종목 수
  max_position_size: 0.1           # 종목당 최대 10%
  
  # 손익 관리
  stop_loss_pct: -0.05            # 손절 -5%
  take_profit_pct: 0.10           # 익절 +10%
  trailing_stop_pct: 0.02         # 추적 손절 2%
  
  # 일일 제한
  max_daily_loss: -0.03           # 일일 최대 손실 -3%
  max_daily_trades: 10            # 일일 최대 거래 횟수
  
  # 거래량 체크
  min_volume_ratio: 0.5           # 최소 거래량 (평균 대비)

# 모니터링 설정
monitoring:
  # 헬스체크 간격
  health_check_interval: 60       # 1분마다 시스템 상태 체크
  
  # 성과 측정
  performance_report_interval: 3600  # 1시간마다 성과 리포트
  
  # 알림 설정
  notifications:
    trade_execution: true         # 매매 실행 알림
    error_events: true            # 에러 발생 알림
    daily_summary: true           # 일일 요약 알림
    system_alerts: true           # 시스템 경고 알림

# API 설정
api:
  # 요청 제한 설정 (KIS 제한 대응)
  rate_limit:
    max_calls_per_second: 18      # 안전 마진을 둔 초당 호출 제한
    burst_limit: 50               # 버스트 제한
    backoff_multiplier: 1.5       # 백오프 배수
    max_retry_attempts: 3         # 최대 재시도 횟수
  
  # 타임아웃 설정
  timeouts:
    connect_timeout: 10           # 연결 타임아웃 (초)
    read_timeout: 30              # 읽기 타임아웃 (초)
    total_timeout: 60             # 전체 타임아웃 (초)
  
  # WebSocket 설정
  websocket:
    reconnect_interval: 5         # 재연결 시도 간격 (초)
    ping_interval: 30             # 핑 간격 (초)
    max_reconnect_attempts: 10    # 최대 재연결 시도

# 로깅 설정
logging:
  # 로그 레벨별 설정
  levels:
    root: INFO
    kis_auth: DEBUG
    market_data: INFO
    strategy: INFO
    trading: INFO
  
  # 파일 로테이션
  rotation:
    max_size: "10 MB"
    backup_count: 10
    compression: "gz"
  
  # 로그 포맷
  format: "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"

# 개발/디버깅 설정
development:
  # 디버그 모드
  debug_mode: false
  
  # 테스트 설정
  test_mode: true                 # 실제 주문 없이 시뮬레이션
  mock_data: false                # 가짜 데이터 사용 여부
  
  # 성능 프로파일링
  profiling_enabled: false
  profile_output_dir: "logs/profiles"
```

### config/logging.yaml
```yaml
# 로깅 설정 세부 구성

version: 1
disable_existing_loggers: false

formatters:
  default:
    format: "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"
  
  simple:
    format: "{time:HH:mm:ss} | {level} | {message}"
  
  detailed:
    format: "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {process}:{thread} | {message}"

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: simple
    stream: ext://sys.stdout
  
  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: default
    filename: logs/kis_trading.log
    maxBytes: 10485760  # 10MB
    backupCount: 10
  
  error_file:
    class: logging.handlers.RotatingFileHandler
    level: ERROR
    formatter: detailed
    filename: logs/errors.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

loggers:
  kis_trading:
    level: INFO
    handlers: [console, file]
    propagate: false
  
  kis_trading.auth:
    level: DEBUG
    handlers: [file]
    propagate: true
  
  kis_trading.data:
    level: INFO
    handlers: [file]
    propagate: true
  
  kis_trading.strategy:
    level: INFO
    handlers: [console, file]
    propagate: true
  
  kis_trading.trading:
    level: INFO
    handlers: [console, file, error_file]
    propagate: true

root:
  level: WARNING
  handlers: [console, file]
```

---

## 📝 1.1.5 기본 파일 생성 (1시간)

### .gitignore 파일
```gitignore
# === Python ===
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# === uv 가상환경 ===
.venv/
venv/
ENV/
env/

# === 환경변수 및 설정 ===
.env
.env.local
.env.*.local
config/local_config.yaml

# === KIS API 관련 보안 파일 ===
kis_token_*.json
*.pem
*.key
*.crt
api_keys.txt
secrets/

# === 데이터베이스 및 데이터 ===
data/db/*.db
data/db/*.sqlite3
data/cache/
*.db
*.sqlite
*.sqlite3

# === 로그 파일 ===
logs/
*.log
*.log.*

# === 테스트 결과 ===
.coverage
htmlcov/
.pytest_cache/
.tox/
coverage.xml
*.cover
.hypothesis/

# === IDE 설정 ===
.vscode/
.idea/
*.swp
*.swo
*~

# === 백테스팅 결과 ===
backtest_results/
reports/
*.png
*.pdf
*.xlsx

# === 운영체제 ===
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# === 임시 파일 ===
tmp/
temp/
*.tmp
*.temp
```

### README.md 파일
```markdown
# 한국투자증권 API 자동매매 프로그램

**KIS OpenAPI**를 활용한 실시간 자동매매 시스템 MVP

## 🎯 프로젝트 개요

### 핵심 목표
- WebSocket 실시간 데이터 + RSI 기반 매매전략 검증
- API Rate Limit 환경에서 안정적인 자동매매 시스템 구축
- 3주 MVP 개발로 시스템 유효성 검증

### 주요 기능
- ✅ **실시간 데이터 수집**: WebSocket (호가/체결) + REST (차트)
- ✅ **매매전략**: RSI + 실시간 호가 분석 복합 전략
- ✅ **리스크 관리**: 포지션/손익/거래빈도 제한
- ✅ **모니터링**: 텔레그램 알림, 실시간 대시보드

## 🏗️ 시스템 아키텍처

```
Trading Bot → Data Layer → KIS OpenAPI
     ↓           ↓            ↓
Strategy    WebSocket    실시간 호가/체결
Engine   →  REST API  →  차트 데이터
     ↓           ↓            ↓
Order       SQLite      주문 실행
Manager  →  Database →  계좌 관리
```

## 🚀 빠른 시작

### 1. 환경 설정
```bash
# 저장소 클론
git clone <repository_url>
cd qb_project

# uv로 프로젝트 설정 및 의존성 설치
uv sync --extra dev

# 또는 개발 환경 + 백테스팅 환경
uv sync --extra dev --extra backtest
```

### 2. 설정 파일 구성
```bash
# 환경변수 설정
cp .env.example .env
# .env 파일에 KIS API 키 등 설정 입력

# 데이터베이스 초기화 (추후 구현)
python -m src.utils.db_init
```

### 3. 실행
```bash
# uv를 통한 메인 프로그램 실행
uv run python run.py

# 또는 개발 모드
uv run python -m src.main --dev

# uv shell로 가상환경 진입 후 실행
uv shell
python run.py
```

## 📁 프로젝트 구조

```
qb_project/
├── src/                    # 소스 코드
│   ├── auth/              # KIS API 인증
│   ├── data/              # 데이터 수집/처리
│   ├── strategy/          # 매매 전략
│   ├── trading/           # 주문 실행
│   └── utils/             # 유틸리티
├── tests/                 # 테스트 코드
├── config/                # 설정 파일
├── data/                  # 데이터 저장소
├── logs/                  # 로그 파일
└── docs/                  # 문서
```

## 🔧 개발 로드맵

### Phase 1: 기반 인프라 (Week 1) ✅
- [x] 프로젝트 설정
- [x] KIS API 인증
- [ ] WebSocket 실시간 데이터 수집

### Phase 2: 매매전략 (Week 2)
- [ ] RSI + 실시간 호가 분석 전략
- [ ] 주문 실행 시스템
- [ ] 리스크 관리 시스템

### Phase 3: 운영시스템 (Week 3)
- [ ] 실시간 모니터링
- [ ] 성과 분석
- [ ] 시스템 최적화

## 📊 성공 지표

### 기술적 지표
- API 응답시간 < 500ms
- 시스템 가동율 > 99%
- Rate Limit 위반 < 1%

### 재무적 지표
- 최소 연 5% 수익률 목표
- 일일 최대 손실 -3% 제한

## ⚠️ 주의사항

### 보안
- `.env` 파일과 API 키는 절대 Git에 커밋하지 않기
- 실전 계정 사용 시 충분한 테스트 후 소액으로 시작

### 법적 고지
- 본 프로그램은 교육/연구 목적으로 개발됨
- 실제 투자 시 발생하는 손실에 대해서는 사용자 책임
- 관련 법규 및 증권사 약관 준수 필요

## 📚 참고 자료

- [한국투자증권 OpenAPI 가이드](https://apiportal.koreainvestment.com/)
- [KIS 개발자 센터](https://apiportal.koreainvestment.com/howto)
- [프로젝트 기술 문서](docs/)

## 🤝 기여

이슈 리포트, 기능 제안, 코드 기여 환영합니다.

## 📄 라이선스

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조
```

### run.py 실행 스크립트
```python
#!/usr/bin/env python3
"""
KIS 자동매매 프로그램 실행 스크립트
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def parse_arguments():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="한국투자증권 API 자동매매 프로그램"
    )
    
    parser.add_argument(
        "--env", 
        choices=["prod", "vps"], 
        default="vps",
        help="실행 환경 (prod: 실전투자, vps: 모의투자)"
    )
    
    parser.add_argument(
        "--strategy", 
        default="realtime_rsi",
        help="사용할 매매 전략"
    )
    
    parser.add_argument(
        "--test-mode", 
        action="store_true",
        help="테스트 모드 (실제 주문 없이 시뮬레이션)"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="디버그 모드"
    )
    
    parser.add_argument(
        "--config", 
        default="config/config.yaml",
        help="설정 파일 경로"
    )
    
    return parser.parse_args()


async def main():
    """메인 실행 함수"""
    args = parse_arguments()
    
    print("🚀 KIS 자동매매 프로그램 시작")
    print(f"환경: {args.env}")
    print(f"전략: {args.strategy}")
    print(f"테스트 모드: {args.test_mode}")
    print("-" * 50)
    
    try:
        # TODO: 실제 메인 로직은 Phase 1.2 이후에 구현
        # from src.main import TradingSystem
        # system = TradingSystem(args)
        # await system.start()
        
        print("⚠️ 아직 메인 로직이 구현되지 않았습니다.")
        print("Phase 1.2 (KIS API 인증) 완료 후 사용 가능합니다.")
        
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Python 3.11+ 체크
    if sys.version_info < (3, 11):
        print("❌ Python 3.11 이상이 필요합니다.")
        sys.exit(1)
    
    # 비동기 메인 실행
    asyncio.run(main())
```

---

## ✅ 완료 체크리스트

### 1.1.1 디렉터리 구조 ✅
- [ ] 기본 디렉터리 생성
- [ ] `__init__.py` 파일 생성
- [ ] 구조 검증

### 1.1.2 uv 설정 & 의존성 ✅  
- [ ] uv 설치
- [ ] Python 3.11+ 설정 (`uv python pin 3.11`)
- [ ] `pyproject.toml` 작성
- [ ] `uv sync --extra dev` 실행
- [ ] TA-Lib 시스템 의존성 (선택사항)

### 1.1.3 환경변수 설정 ✅
- [ ] `.env.example` 작성
- [ ] 실제 `.env` 파일 생성
- [ ] KIS API 키 설정 (나중에)
- [ ] 보안 설정 확인

### 1.1.4 설정 파일 ✅
- [ ] `config/config.yaml` 작성
- [ ] `config/logging.yaml` 작성
- [ ] 설정 값 검증

### 1.1.5 기본 파일 ✅
- [ ] `.gitignore` 작성
- [ ] `README.md` 작성
- [ ] `run.py` 실행 스크립트 작성

---

## 🎯 다음 단계
완료 후 **Phase 1.2: KIS API 인증 시스템**으로 진행합니다.

**예상 소요시간**: Phase 1.2는 3-4시간 정도 소요될 예정입니다.