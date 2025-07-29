# 🚀 QB Trading System - Docker 실행 가이드

## 📋 사전 요구사항

1. **Docker 설치**
   - Docker Desktop (Windows/Mac) 또는 Docker Engine (Linux)
   - Docker Compose v2.0 이상

2. **시스템 요구사항**
   - 최소 RAM: 2GB (권장: 4GB)
   - 디스크 공간: 5GB 이상

## 🔧 설정 방법

### 1. 프로젝트 다운로드
```bash
# Git으로 클론 (권장)
git clone https://github.com/your-repo/QB.git
cd QB

# 또는 ZIP 파일로 다운로드 후 압축 해제
```

### 2. 환경 변수 설정
```bash
# .env 파일 수정 (반드시 실제 API 키 입력!)
vim .env

# 필수 항목:
# KIS_APP_KEY=실제_API_키
# KIS_APP_SECRET=실제_API_시크릿
# KIS_ACCOUNT_STOCK=실제_계좌번호
# KIS_MODE=prod  # 실전투자
```

### 3. Docker 이미지 빌드
```bash
# 처음 실행 시 (약 5-10분 소요)
docker-compose build
```

## 🎯 실행 방법

### 실제 거래 시작
```bash
# 1. 전체 시스템 시작 (백그라운드)
docker-compose up -d

# 2. 실시간 로그 확인
docker-compose logs -f qb_trading
```

### 거래 파라미터 변경
```bash
# docker-compose.yml의 command 부분 수정
command: ["uv", "run", "python", "run_live_trading.py", 
          "--symbol", "005930",        # 종목코드
          "--max-amount", "100000",     # 최대거래금액
          "--stop-loss", "3.0"]         # 손절매 %
```

### 시스템 중지
```bash
# 안전하게 거래 중지
docker-compose stop qb_trading

# 전체 시스템 중지
docker-compose down

# 데이터 포함 완전 삭제 (주의!)
docker-compose down -v
```

## 📊 모니터링

### 실시간 로그 확인
```bash
# Trading 앱 로그
docker-compose logs -f qb_trading

# Redis 로그
docker-compose logs -f redis

# PostgreSQL 로그
docker-compose logs -f postgres
```

### 거래 결과 확인
```bash
# 로그 파일 위치
ls -la ./logs/

# 최신 거래 리포트 확인
cat ./logs/live_trading_report_*.json | jq .
```

### 데이터베이스 접속
```bash
# PostgreSQL 접속
docker exec -it qb_postgres psql -U qb_user -d qb_trading_dev

# Redis 접속
docker exec -it qb_redis redis-cli
```

## 🛠️ 문제 해결

### 1. 컨테이너가 시작되지 않을 때
```bash
# 상태 확인
docker-compose ps

# 상세 로그 확인
docker-compose logs qb_trading
```

### 2. API 연결 오류
- `.env` 파일의 KIS API 키가 올바른지 확인
- `KIS_MODE=prod`로 설정되어 있는지 확인
- 네트워크 연결 상태 확인

### 3. 메모리 부족
```bash
# Docker 리소스 정리
docker system prune -a

# Redis 메모리 확인
docker exec qb_redis redis-cli INFO memory
```

## 🔒 보안 주의사항

1. **절대로 .env 파일을 공개 저장소에 업로드하지 마세요!**
2. **실제 거래 전 소액으로 테스트하세요**
3. **손절매 설정을 반드시 확인하세요**

## 💡 실행 예시

### 삼성전자 10만원 거래
```bash
docker-compose up -d
docker-compose logs -f qb_trading
```

### 다른 종목으로 변경
```bash
# docker-compose.yml 수정
vim docker-compose.yml
# command 부분에서 --symbol 값 변경

# 재시작
docker-compose restart qb_trading
```

## 📞 지원

문제 발생 시:
1. 먼저 로그 확인: `docker-compose logs qb_trading`
2. `.env` 설정 재확인
3. Docker 재시작: `docker-compose restart`

## ⏰ 거래 시간

- 한국 주식시장: 09:00 - 15:30 (평일)
- 장 시작 전 미리 실행하여 연결 상태 확인 권장