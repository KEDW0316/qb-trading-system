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
uv run python -m src.utils.db_init
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
- [ ] KIS API 인증
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