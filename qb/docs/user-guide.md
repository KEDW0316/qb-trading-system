# QB Trading System 사용자 가이드

**버전**: 1.0  
**최종 업데이트**: 2025년 1월 27일  

---

## 📋 개요

QB Trading System은 한국투자증권(KIS) API를 활용한 자동 거래 시스템입니다. 실시간 시장 데이터 수집, 기술적 분석, 전략 기반 자동 거래를 지원합니다.

### 주요 기능
- 🔄 **실시간 데이터 수집**: KIS API를 통한 실시간 시장 데이터
- 📊 **기술적 분석**: 20+ 종류의 기술적 지표 자동 계산
- 🎯 **전략 엔진**: 플러그인 방식의 다양한 거래 전략
- 💰 **자동 거래**: 전략 신호 기반 자동 주문 실행
- 📈 **성과 추적**: 실시간 수익률 및 리스크 분석
- 🔒 **리스크 관리**: 손실 제한 및 포지션 크기 관리

---

## 🚀 빠른 시작

### 1. 시스템 요구사항
- **Python**: 3.11 이상
- **Docker**: 20.0 이상
- **메모리**: 최소 8GB 권장
- **저장공간**: 최소 10GB

### 2. 설치 및 설정

#### 환경 설정
```bash
# 프로젝트 클론
git clone https://github.com/your-repo/QB.git
cd QB

# Python 환경 생성
conda create -n qb python=3.11
conda activate qb

# 의존성 설치
pip install -r requirements.txt

# Docker 서비스 시작
docker-compose -f docker-compose.dev.yml up -d
```

#### API 키 설정
`.env` 파일을 생성하고 KIS API 키를 설정:

```env
# KIS API 설정
KIS_APPKEY=your_app_key
KIS_APPSECRET=your_app_secret
KIS_ACCOUNT_NUMBER=your_account_number

# 거래 환경 (real/virtual)
KIS_TRADE_TYPE=virtual

# Redis 설정
REDIS_HOST=localhost
REDIS_PORT=6379

# PostgreSQL 설정
DB_HOST=localhost
DB_PORT=5432
DB_NAME=qb_trading
DB_USER=qb_user
DB_PASSWORD=qb_password
```

### 3. 시스템 시작

```bash
# 전체 시스템 시작
python -m qb.main

# 또는 개별 컴포넌트 시작
python -m qb.engines.data_collector    # 데이터 수집기
python -m qb.engines.strategy_engine    # 전략 엔진
python -m qb.engines.order_engine       # 주문 엔진
```

---

## 💡 기본 사용법

### 1. 전략 설정 및 활성화

#### 내장 전략 사용
```python
from qb.engines.strategy_engine import StrategyEngine

# 전략 엔진 초기화
strategy_engine = StrategyEngine()
await strategy_engine.start()

# 1분봉_5분봉 전략 활성화
await strategy_engine.activate_strategy(
    "MovingAverage1M5MStrategy",
    params={
        "ma_period": 5,
        "confidence_threshold": 0.7,
        "market_close_time": "15:20"
    },
    symbols=["005930", "000660", "035420"]  # 삼성전자, SK하이닉스, NAVER
)
```

#### 전략 상태 확인
```python
# 활성 전략 목록
active_strategies = strategy_engine.get_active_strategies()
print("활성 전략:", active_strategies)

# 전략 성과 조회
performance = await strategy_engine.get_strategy_performance("MovingAverage1M5MStrategy")
print(f"총 수익률: {performance.total_return:.2%}")
print(f"승률: {performance.win_rate:.2%}")
```

### 2. 실시간 모니터링

#### 시장 데이터 모니터링
```python
from qb.engines.data_collector import DataCollector

# 데이터 수집기 시작
data_collector = DataCollector()
await data_collector.start()

# 특정 종목 구독
await data_collector.subscribe_symbols(["005930", "000660"])
```

#### 포지션 및 주문 상태
```python
from qb.engines.order_engine import OrderEngine

order_engine = OrderEngine()

# 현재 포지션 조회
positions = await order_engine.get_current_positions()
for symbol, position in positions.items():
    print(f"{symbol}: {position.quantity}주 (평균단가: {position.avg_price:,}원)")

# 대기 중인 주문 조회
pending_orders = await order_engine.get_pending_orders()
print(f"대기 주문: {len(pending_orders)}건")
```

### 3. 전략 관리

#### 전략 파라미터 변경
```python
# 실시간 파라미터 업데이트
await strategy_engine.update_strategy_parameters(
    "MovingAverage1M5MStrategy",
    {"ma_period": 10, "confidence_threshold": 0.8}
)
```

#### 전략 비활성화
```python
# 특정 전략 중지
await strategy_engine.deactivate_strategy("MovingAverage1M5MStrategy")

# 모든 전략 중지
await strategy_engine.deactivate_all_strategies()
```

---

## 📊 내장 전략 소개

### 1. MovingAverage1M5MStrategy (1분봉_5분봉 전략)

**개념**: 1분봉 종가와 5분 이동평균을 비교하여 매매

**매매 규칙**:
- 매수: 1분봉 종가 > 5분 이동평균
- 매도: 1분봉 종가 ≤ 5분 이동평균
- 강제매도: 15:20 장마감시 시장가 매도

**파라미터**:
```python
{
    "ma_period": 5,                    # 이동평균 기간
    "confidence_threshold": 0.7,       # 신호 신뢰도 임계값
    "market_close_time": "15:20",       # 장마감 시간
    "min_volume_threshold": 30_000_000_000,  # 최소 거래대금
    "enable_volume_filter": True        # 거래대금 필터
}
```

**적합한 종목**: 거래대금 300억원 이상, 변동성이 큰 성장주

---

## ⚙️ 고급 설정

### 1. 리스크 관리 설정

```python
from qb.engines.risk_manager import RiskManager

risk_manager = RiskManager()

# 일일 손실 한도 설정
await risk_manager.set_daily_loss_limit(1_000_000)  # 100만원

# 포지션 크기 한도 설정
await risk_manager.set_position_size_limit("005930", 10_000_000)  # 1천만원

# 전략별 할당 자금 설정
await risk_manager.set_strategy_allocation("MovingAverage1M5MStrategy", 50_000_000)  # 5천만원
```

### 2. 알림 설정

```python
from qb.utils.notification import NotificationManager

notification = NotificationManager()

# 텔레그램 봇 설정
await notification.setup_telegram("your_bot_token", "your_chat_id")

# 이메일 설정
await notification.setup_email("smtp.gmail.com", "your_email@gmail.com", "password")

# 알림 이벤트 구독
await notification.subscribe_to_events([
    "trading_signal",      # 거래 신호
    "order_filled",        # 체결 완료
    "daily_pnl_report",    # 일일 손익 보고서
    "risk_alert"           # 리스크 경고
])
```

### 3. 백테스팅

```python
from qb.engines.backtest_engine import BacktestEngine

backtest = BacktestEngine()

# 백테스트 설정
await backtest.setup(
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100_000_000,  # 1억원
    commission_rate=0.00015       # 0.015%
)

# 전략 테스트
result = await backtest.run_strategy(
    "MovingAverage1M5MStrategy",
    symbols=["005930", "000660"],
    params={"ma_period": 5}
)

print(f"백테스트 수익률: {result.total_return:.2%}")
print(f"최대낙폭: {result.max_drawdown:.2%}")
print(f"샤프 비율: {result.sharpe_ratio:.2f}")
```

---

## 📱 웹 대시보드

### 접속 방법
```bash
# 웹 서버 시작
python -m qb.web.app

# 브라우저에서 접속
# http://localhost:8080
```

### 주요 기능
- **실시간 차트**: 가격 움직임 및 기술적 지표
- **포지션 현황**: 보유 종목 및 손익 상황
- **주문 내역**: 체결/미체결 주문 현황
- **성과 분석**: 전략별 수익률 및 통계
- **설정 관리**: 전략 파라미터 실시간 조정

---

## 🚨 주의사항 및 제한사항

### 1. 거래 리스크
- **가상 거래 권장**: 처음에는 반드시 가상 계좌로 테스트
- **손실 위험**: 자동 거래는 큰 손실을 초래할 수 있음
- **시장 변화**: 과거 성과가 미래 수익을 보장하지 않음

### 2. 시스템 제한사항
- **API 호출 한도**: KIS API 일일 호출 제한 (20,000회)
- **동시 접속**: 하나의 API 키로는 동시 접속 불가
- **장중 시간**: 09:00~15:30 한국시장 개장시간만 거래

### 3. 기술적 제한
- **인터넷 연결**: 안정적인 네트워크 환경 필수
- **서버 안정성**: 24시간 운영을 위한 안정적인 서버 필요
- **데이터 품질**: 실시간 데이터 지연 또는 오류 가능성

---

## ❓ 자주 묻는 질문 (FAQ)

### Q1: 가상 계좌와 실제 계좌의 차이는?
**A**: 가상 계좌는 실제 돈을 사용하지 않는 테스트 환경입니다. 전략 검증 후 실제 계좌로 전환하세요.

### Q2: 여러 전략을 동시에 실행할 수 있나요?
**A**: 네, 가능합니다. 각 전략에 다른 종목을 할당하거나 같은 종목에 다른 파라미터로 실행할 수 있습니다.

### Q3: 시스템이 다운되면 어떻게 되나요?
**A**: 모든 주문과 포지션 정보는 데이터베이스에 저장되므로 재시작 시 복구됩니다.

### Q4: 수수료는 어떻게 계산되나요?
**A**: KIS 증권사 수수료율 (매매금액의 0.015%)이 자동으로 계산됩니다.

### Q5: 새로운 전략을 추가하려면?
**A**: 개발자 가이드를 참고하여 BaseStrategy를 상속받는 클래스를 구현하면 됩니다.

---

## 📞 지원 및 문의

### 개발팀 연락처
- **이메일**: qb-trading@example.com
- **텔레그램**: @qb_trading_support
- **GitHub**: https://github.com/your-repo/QB/issues

### 문서 및 리소스
- **개발자 가이드**: `/docs/developer-guide.md`
- **API 문서**: `/docs/api-reference.md`
- **아키텍처 문서**: `/docs/architecture/`
- **예제 코드**: `/examples/`

---

**⚠️ 면책조항**: 본 시스템은 교육 및 연구 목적으로 제공됩니다. 실제 거래에서 발생하는 손실에 대해 개발팀은 책임지지 않습니다. 투자는 본인의 판단과 책임 하에 진행하시기 바랍니다.

---

*Generated by QB Trading System Development Team*  
*Version 1.0 - 2025.01.27*