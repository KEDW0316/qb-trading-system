# 한국투자증권 API 자동매매 프로그램 MVP 계획서

## 📋 프로젝트 개요

### 목표

한국투자증권 OpenAPI를 활용한 자동매매 프로그램의 MVP 개발 및 검증

### 검증 가설

- KIS API의 실시간 안정성 및 응답속도
- 기본적인 기술적 분석 기반 매매 전략의 유효성
- 수수료 대비 수익성 및 실용성

### 개발 기간

3주 (Phase별 1주씩)

---

## 🔌 KIS API 분석 결과

### 인증 시스템

```
POST /oauth2/tokenP  # 접근토큰 발급 (24시간 유효)
```

- **특징**: 6시간 이내 재발급시 기존 토큰 유지
- **알림**: 발급시 알림톡 자동 발송
- **환경**: 실전투자(`prod`) vs 모의투자(`vps`)
- **발급 제한**: **1분당 1회** 제한

### ⚠️ API 호출 제한 정책

KIS API는 엄격한 호출 제한이 있어 자동매매 시 반드시 고려해야 합니다:

#### 기본 제한 사항

- **REST API**: **1초당 20건** 제한
- **토큰 발급**: **1분당 1회** 제한
- **특정 API**: 1초당 1건 권장 (조회시간이 긴 API)

#### 제한 초과 시 대응

- HTTP 429 Too Many Requests 응답
- 일시적 API 접근 차단 가능
- 심각한 경우 계정 제재 위험

#### 자동매매 설계 시 고려사항

```python
# 필수 구현 요소
- 요청 간 강제 지연 (0.05~0.1초)
- 지수 백오프(Exponential Backoff) 재시도
- 캐싱을 통한 불필요한 호출 최소화
- 배치 처리로 호출 횟수 절약
```

### 핵심 API 엔드포인트

#### 1. REST API - 시세 조회 (Pull 방식)

```python
# 현재가 조회 (과거 시점)
"/uapi/domestic-stock/v1/quotations/inquire-price"

# 일봉 차트 (기술적 분석용)
"/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"

# 호가 조회 (스냅샷)
"/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"

# 분봉 차트 (당일만, 최대 30건)
"/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
```

#### 2. WebSocket API - 실시간 시세 (Push 방식) ⭐

```python
# 실시간 호가 (자동매매 핵심!)
TR_ID: "H0STASP0"  # 매수/매도 호가 실시간 수신

# 실시간 체결가
TR_ID: "H0STCNT0"  # 체결가/거래량 실시간 수신

# WebSocket 인증
ka.auth()     # REST 토큰 발급
ka.auth_ws()  # WebSocket 인증
```

**🔥 자동매매의 핵심**: REST API는 내가 요청할 때만 과거 데이터를 주지만, **WebSocket은 실시간으로 호가/체결 변화를 Push**로 알려줍니다!

#### 2. 계좌 및 잔고 조회 (trading)

```python
# 주식 잔고 조회
"/uapi/domestic-stock/v1/trading/inquire-balance"

# 계좌 평가 잔고
"/uapi/domestic-stock/v1/trading/inquire-account-balance"

# 주문 가능 조회
"/uapi/domestic-stock/v1/trading/inquire-psbl-order"

# 체결 내역 조회
"/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
```

#### 3. 주문 실행 (trading)

```python
# 현금 주문 (매수/매도)
"/uapi/domestic-stock/v1/trading/order-cash"

# 주문 취소/정정
"/uapi/domestic-stock/v1/trading/order-rvsecncl"

# 예약 주문
"/uapi/domestic-stock/v1/trading/order-resv"
```

#### 4. 추가 분석 데이터

```python
# 투자자별 거래 현황
"/uapi/domestic-stock/v1/quotations/inquire-investor"

# 프로그램 매매 추이
"/uapi/domestic-stock/v1/quotations/program-trade-by-stock"

# 거래량 상위 종목
"/uapi/domestic-stock/v1/quotations/volume-rank"
```

---

## 🏗️ 시스템 아키텍처 (수정)

### 전체 구조도 (WebSocket 실시간 처리)

```
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│   Trading Bot    │   │   Data Layer     │   │   KIS OpenAPI    │
│                  │   │                  │   │                  │
│ ┌──────────────┐ │   │ ┌──────────────┐ │   │ ┌──────────────┐ │
│ │Auth Manager  │ │◄──┤ │Token Cache   │ │◄──┤ │OAuth2        │ │
│ │              │ │   │ │              │ │   │ │/tokenP       │ │
│ └──────────────┘ │   │ └──────────────┘ │   │ └──────────────┘ │
│                  │   │                  │   │                  │
│ ┌──────────────┐ │   │ ┌──────────────┐ │   │ ┌──────────────┐ │
│ │WebSocket     │ │◄──┤ │실시간 호가      │ │◄──┤ │WebSocket     │ │
│ │Handler       │ │   │ │실시간 체결      │ │   │ │H0STASP0      │ │
│ │              │ │   │ │Queue         │ │   │ │H0STCNT0      │ │
│ └──────────────┘ │   │ └──────────────┘ │   │ └──────────────┘ │
│        │         │   │        │         │   │                  │
│        ▼         │   │        ▼         │   │ ┌──────────────┐ │
│ ┌──────────────┐ │   │ ┌──────────────┐ │   │ │REST API      │ │
│ │Strategy      │ │◄──┤ │Price Cache   │ │◄──┤ │Quotations    │ │
│ │Engine        │ │   │ │(OHLCV)       │ │   │ │(차트데이터)     │ │
│ │              │ │   │ └──────────────┘ │   │ └──────────────┘ │
│ └──────────────┘ │   │                  │   │                  │
│        │         │   │ ┌──────────────┐ │   │ ┌──────────────┐ │
│        ▼         │   │ │Portfolio     │ │◄──┤ │Trading       │ │
│ ┌──────────────┐ │   │ │Database      │ │───▶│API            │ │
│ │Order         │ │───┼▶│(SQLite)      │ │   │ │              │ │
│ │Manager       │ │   │ └──────────────┘ │   │ └──────────────┘ │
│ └──────────────┘ │   └──────────────────┘   └──────────────────┘
└──────────────────┘              │
          │                       │
          └───────────────────────┼────────────────────────
                                  ▼
                     ┌──────────────────┐
                     │   Monitoring     │
                     │   & Logging      │
                     │   (Telegram)     │
                     └──────────────────┘

🔥 핵심 변화: WebSocket으로 실시간 호가/체결 데이터를 받아서
실시간 매매 의사결정이 가능해짐!
```

### 핵심 컴포넌트 세부 설계

#### 1. Auth Manager

```python
class KISAuthManager:
    """KIS API 인증 및 토큰 관리"""

    def __init__(self, env="prod"):  # prod or vps
        self.env = env
        self.token_file = f"kis_token_{env}.json"

    async def get_access_token(self):
        """토큰 발급/갱신"""
        saved_token = self._read_saved_token()
        if self._is_token_valid(saved_token):
            return saved_token
        return await self._issue_new_token()

    def _is_token_valid(self, token_info):
        """토큰 유효성 검사 (만료시간 확인)"""
        pass
```

#### 2. Market Data Manager (WebSocket + REST 하이브리드)

```python
class MarketDataManager:
    """실시간 + 과거 데이터 통합 관리"""

    def __init__(self):
        self.rate_limiter = RateLimiter(max_calls=20, time_window=1.0)
        self.websocket_handler = WebSocketHandler()
        self.realtime_data = {}  # 실시간 데이터 저장

    async def start_realtime_feed(self, symbols: List[str]):
        """실시간 호가/체결 데이터 구독 시작"""
        for symbol in symbols:
            # 실시간 호가 구독 (H0STASP0)
            await self.websocket_handler.subscribe_ask_bid(symbol)
            # 실시간 체결 구독 (H0STCNT0)
            await self.websocket_handler.subscribe_execution(symbol)

    def get_realtime_price(self, symbol: str) -> float:
        """실시간 현재가 (WebSocket에서 받은 최신 데이터)"""
        return self.realtime_data.get(symbol, {}).get('current_price', 0)

    def get_realtime_ask_bid(self, symbol: str) -> dict:
        """실시간 호가 정보 (매수/매도 1~10호가)"""
        return self.realtime_data.get(symbol, {}).get('ask_bid', {})

    async def get_daily_chart(self, symbol: str, period: int = 20):
        """일봉 데이터 조회 (REST API, 기술적 분석용)"""
        await self.rate_limiter.wait()
        # 차트 데이터는 REST API로만 조회 가능
        
    def get_minute_bars(self, symbol: str, period: int = 60) -> pd.DataFrame:
        """분봉 데이터 조회 (실시간 생성 + DB 결합)"""
        # 1. DB에서 과거 분봉 조회  
        historical = self.db.get_minute_data(symbol, period-1)
        # 2. 현재 분봉 추가 (실시간 WebSocket 데이터로 생성)
        current = self.minute_builder.get_current_minute(symbol)
        return pd.concat([historical, current]) if not historical.empty else current

    def on_realtime_data(self, tr_id: str, data: dict):
        """WebSocket 데이터 수신 콜백"""
        symbol = data.get('stock_code')
        if tr_id == 'H0STASP0':  # 실시간 호가
            self._update_ask_bid_data(symbol, data)
        elif tr_id == 'H0STCNT0':  # 실시간 체결
            self._update_execution_data(symbol, data)
            # 실시간 체결 데이터로 분봉 생성 ⭐
            self.minute_builder.on_execution_data(symbol, data)
```

#### 실시간 분봉 생성기 구현
```python
class RealtimeMinuteDataBuilder:
    """WebSocket 실시간 체결 데이터로 분봉 생성"""
    
    def __init__(self):
        self.current_minute_data = {}  # 현재 진행중인 분봉
        self.db = SQLiteManager()
        
    def on_execution_data(self, symbol: str, execution_data: dict):
        """실시간 체결 데이터로 분봉 업데이트"""
        price = float(execution_data['execution_price'])
        volume = int(execution_data['execution_qty'])
        timestamp = self._get_minute_timestamp()  # 분 단위로 정규화
        
        # 새로운 분봉 시작
        if symbol not in self.current_minute_data:
            self.current_minute_data[symbol] = {
                'open': price, 'high': price, 'low': price, 'close': price,
                'volume': 0, 'start_time': timestamp
            }
            
        # OHLCV 업데이트
        bar = self.current_minute_data[symbol]
        if timestamp > bar['start_time']:  # 새 분봉으로 넘어감
            self._save_completed_minute_bar(symbol, bar)
            # 새 분봉 시작
            self.current_minute_data[symbol] = {
                'open': price, 'high': price, 'low': price, 'close': price,
                'volume': volume, 'start_time': timestamp
            }
        else:
            # 현재 분봉 업데이트
            bar['high'] = max(bar['high'], price)
            bar['low'] = min(bar['low'], price) 
            bar['close'] = price
            bar['volume'] += volume
            
    def _save_completed_minute_bar(self, symbol: str, bar_data: dict):
        """완성된 분봉을 DB에 저장"""
        self.db.insert_minute_data(symbol, bar_data)
        
    def get_current_minute(self, symbol: str) -> dict:
        """현재 진행중인 분봉 데이터 반환"""
        return self.current_minute_data.get(symbol, {})
```

#### Rate Limiter 구현

```python
class RateLimiter:
    """KIS API 호출 제한 관리"""

    def __init__(self, max_calls: int = 20, time_window: float = 1.0):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []

    async def wait(self):
        """호출 전 대기 시간 계산 및 적용"""
        now = time.time()
        # 시간 윈도우 밖의 호출 기록 제거
        self.calls = [call_time for call_time in self.calls
                     if now - call_time < self.time_window]

        if len(self.calls) >= self.max_calls:
            sleep_time = self.time_window - (now - self.calls[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.calls.append(now)
```

#### WebSocket Handler 구현

```python
class WebSocketHandler:
    """KIS WebSocket 실시간 데이터 처리"""

    def __init__(self):
        self.ws = None
        self.subscriptions = set()
        self.data_callback = None

    async def connect(self):
        """WebSocket 연결 및 인증"""
        # WebSocket 인증 (auth_ws() 필요)
        await self.authenticate()
        self.ws = await websockets.connect("wss://ops.koreainvestment.com:31000")

    async def subscribe_ask_bid(self, symbol: str):
        """실시간 호가 구독"""
        message = {
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": "1",   # 구독 등록
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": "H0STASP0",  # 실시간 호가 TR_ID
                    "tr_key": symbol      # 종목코드
                }
            }
        }
        await self.ws.send(json.dumps(message))
        self.subscriptions.add(f"ask_bid_{symbol}")

    async def subscribe_execution(self, symbol: str):
        """실시간 체결 구독"""
        message = {
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNT0",  # 실시간 체결 TR_ID
                    "tr_key": symbol
                }
            }
        }
        await self.ws.send(json.dumps(message))
        self.subscriptions.add(f"execution_{symbol}")

    async def listen(self):
        """실시간 데이터 수신 루프"""
        while True:
            try:
                message = await self.ws.recv()
                data = self.parse_message(message)
                if self.data_callback:
                    await self.data_callback(data['tr_id'], data)
            except websockets.exceptions.ConnectionClosed:
                await self.reconnect()
```

#### 3. Trading Engine

```python
class TradingEngine:
    """주문 실행 및 포지션 관리"""

    async def place_order(self, order: Order):
        """주문 실행 (/uapi/domestic-stock/v1/trading/order-cash)"""

    async def cancel_order(self, order_id: str):
        """주문 취소"""

    async def get_positions(self):
        """현재 포지션 조회"""

    async def get_account_balance(self):
        """계좌 평가 잔고"""
```

---

## 📊 데이터 모델 설계

### SQLite 스키마

```sql
-- 계좌 정보
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    account_number TEXT UNIQUE NOT NULL,
    account_name TEXT NOT NULL,
    account_type TEXT DEFAULT 'stock', -- stock, pension
    is_demo BOOLEAN DEFAULT FALSE,      -- 모의투자 여부
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 종목 정보
CREATE TABLE stocks (
    symbol TEXT PRIMARY KEY,           -- 종목코드 (6자리)
    name TEXT NOT NULL,                -- 종목명
    market TEXT NOT NULL,              -- KOSPI, KOSDAQ, KONEX
    sector TEXT,                       -- 섹터
    industry TEXT,                     -- 업종
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 일봉 차트 데이터 (REST API, 기술적 분석용)
CREATE TABLE daily_chart_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date DATE NOT NULL,                -- 거래일
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    volume INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol),
    UNIQUE(symbol, date)
);

-- 분봉 데이터 (실시간 WebSocket 체결가로 생성) ⭐
CREATE TABLE minute_chart_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    minute_time DATETIME NOT NULL,     -- 분봉 시간 (예: 2024-01-15 09:31:00)
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    volume INTEGER NOT NULL,
    data_source TEXT DEFAULT 'realtime', -- realtime, rest_api
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol),
    UNIQUE(symbol, minute_time)
);

-- 실시간 호가 데이터 (WebSocket H0STASP0)
CREATE TABLE realtime_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    bid_price_1 REAL,                  -- 매수 1호가 가격
    bid_qty_1 INTEGER,                 -- 매수 1호가 잔량
    ask_price_1 REAL,                  -- 매도 1호가 가격
    ask_qty_1 INTEGER,                 -- 매도 1호가 잔량
    bid_price_2 REAL, bid_qty_2 INTEGER,
    ask_price_2 REAL, ask_qty_2 INTEGER,
    -- ... (2~10호가까지 확장 가능)
    total_bid_qty INTEGER,             -- 매수잔량 총합
    total_ask_qty INTEGER,             -- 매도잔량 총합
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

-- 실시간 체결 데이터 (WebSocket H0STCNT0)
CREATE TABLE realtime_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    execution_price REAL NOT NULL,     -- 체결가격
    execution_qty INTEGER NOT NULL,    -- 체결수량
    execution_type TEXT,               -- 매수/매도 구분
    change_price REAL,                 -- 전일대비
    change_rate REAL,                  -- 등락률
    accumulated_volume INTEGER,        -- 누적거래량
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

-- 주문 내역
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    order_id TEXT UNIQUE,              -- KIS 주문번호
    symbol TEXT NOT NULL,
    order_type TEXT NOT NULL,          -- buy, sell
    price_type TEXT NOT NULL,          -- market, limit
    quantity INTEGER NOT NULL,
    order_price REAL,                  -- 주문가격
    executed_price REAL,               -- 체결가격
    executed_quantity INTEGER DEFAULT 0, -- 체결수량
    status TEXT NOT NULL,              -- pending, partial, filled, canceled
    strategy_name TEXT,                -- 매매전략명
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    executed_at DATETIME,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

-- 포지션 (실시간 업데이트)
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    quantity INTEGER NOT NULL,         -- 보유수량
    avg_buy_price REAL NOT NULL,       -- 평균매수가
    current_price REAL,                -- 현재가
    market_value REAL,                 -- 평가금액
    unrealized_pnl REAL,               -- 평가손익
    realized_pnl REAL DEFAULT 0,       -- 실현손익
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (symbol) REFERENCES stocks(symbol),
    UNIQUE(account_id, symbol)
);

-- 매매전략 로그
CREATE TABLE strategy_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    signal TEXT NOT NULL,              -- BUY, SELL, HOLD
    signal_strength REAL,              -- 신호 강도 (0-1)
    indicators JSON,                   -- RSI, MA 등 지표값들
    price REAL NOT NULL,               -- 해당 시점 가격
    reasoning TEXT,                    -- 매매 근거
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (symbol) REFERENCES stocks(symbol)
);

-- API 호출 로그 (모니터링용)
CREATE TABLE api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    response_time REAL,                -- ms
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🤖 매매전략 설계

### 실시간 RSI 기반 매매전략 ⭐

```python
class RealtimeRSIStrategy:
    def __init__(self, data_manager: MarketDataManager):
        self.data_manager = data_manager
        self.rsi_period = 14
        self.oversold_threshold = 30    # 과매도
        self.overbought_threshold = 70  # 과매수
        self.ma_short = 5              # 단기 이동평균
        self.ma_long = 20              # 장기 이동평균

        # 실시간 판단 기준 추가
        self.bid_ask_spread_threshold = 0.01  # 호가창 스프레드 1% 이내
        self.volume_surge_ratio = 1.5         # 평소 거래량 대비 1.5배

    async def analyze(self, symbol: str) -> Signal:
        # 1. 기술적 분석 (REST API - 차트 데이터)
        daily_data = await self.data_manager.get_daily_chart(symbol, 20)
        rsi = self._calculate_rsi(daily_data)
        ma_short = self._calculate_ma(daily_data, self.ma_short)
        ma_long = self._calculate_ma(daily_data, self.ma_long)

        # 2. 실시간 분석 (WebSocket 데이터) ⭐
        realtime_price = self.data_manager.get_realtime_price(symbol)
        ask_bid_data = self.data_manager.get_realtime_ask_bid(symbol)

        # 3. 실시간 호가창 분석
        spread_rate = self._calculate_spread_rate(ask_bid_data)
        volume_pressure = self._analyze_volume_pressure(ask_bid_data)

        # 4. 복합 시그널 생성 (기술적 분석 + 실시간 판단)
        signal = "HOLD"
        strength = 0.0
        reasoning = []

        # 기본 RSI 조건 확인
        if rsi < self.oversold_threshold and ma_short > ma_long:
            # 추가 실시간 조건 확인
            if (spread_rate < self.bid_ask_spread_threshold and
                volume_pressure == "buy_pressure"):

                signal = "BUY"
                strength = (self.oversold_threshold - rsi) / self.oversold_threshold
                strength *= 1.2  # 실시간 조건 만족시 신호 강도 증가

                reasoning.extend([
                    f"RSI 과매도({rsi:.1f})",
                    f"MA 골든크로스(MA5:{ma_short:.0f} > MA20:{ma_long:.0f})",
                    f"호가 스프레드 양호({spread_rate:.2%})",
                    f"매수 물량 우세({volume_pressure})"
                ])

        elif rsi > self.overbought_threshold and ma_short < ma_long:
            if (spread_rate < self.bid_ask_spread_threshold and
                volume_pressure == "sell_pressure"):

                signal = "SELL"
                strength = (rsi - self.overbought_threshold) / (100 - self.overbought_threshold)
                strength *= 1.2

                reasoning.extend([
                    f"RSI 과매수({rsi:.1f})",
                    f"MA 데드크로스(MA5:{ma_short:.0f} < MA20:{ma_long:.0f})",
                    f"호가 스프레드 양호({spread_rate:.2%})",
                    f"매도 물량 우세({volume_pressure})"
                ])

        return Signal(
            symbol=symbol,
            signal=signal,
            strength=strength,
            indicators={
                "rsi": rsi,
                "ma_short": ma_short,
                "ma_long": ma_long,
                "realtime_price": realtime_price,
                "spread_rate": spread_rate,
                "volume_pressure": volume_pressure
            },
            reasoning=" + ".join(reasoning)
        )

    def _calculate_spread_rate(self, ask_bid_data: dict) -> float:
        """호가 스프레드율 계산"""
        ask_price = ask_bid_data.get('ask_price_1', 0)
        bid_price = ask_bid_data.get('bid_price_1', 0)
        if bid_price > 0:
            return (ask_price - bid_price) / bid_price
        return 1.0

    def _analyze_volume_pressure(self, ask_bid_data: dict) -> str:
        """매수/매도 물량 압박 분석"""
        total_bid_qty = ask_bid_data.get('total_bid_qty', 0)
        total_ask_qty = ask_bid_data.get('total_ask_qty', 0)

        if total_bid_qty > total_ask_qty * 1.2:
            return "buy_pressure"   # 매수 우세
        elif total_ask_qty > total_bid_qty * 1.2:
            return "sell_pressure"  # 매도 우세
        else:
            return "balanced"       # 균형
```

**🚀 핵심 개선점**:

1. **실시간 호가창 분석**: 스프레드, 물량 분석으로 진입 타이밍 최적화
2. **이중 검증 시스템**: 기술적 분석 + 실시간 시장 상황 종합 판단
3. **신호 강도 조정**: 실시간 조건 만족시 매매 신호 신뢰도 증가

### 리스크 관리 규칙

```python
class RiskManager:
    def __init__(self):
        self.max_position_size = 0.1    # 종목당 최대 10%
        self.stop_loss_pct = -0.05      # 손절 -5%
        self.take_profit_pct = 0.10     # 익절 +10%
        self.max_daily_loss = -0.03     # 일일 최대 손실 -3%

    async def check_position_limits(self, symbol: str, order_value: float):
        """포지션 한도 체크"""
        current_portfolio_value = await self._get_portfolio_value()
        return order_value <= current_portfolio_value * self.max_position_size

    async def check_stop_loss(self, position: Position):
        """손절 조건 체크"""
        unrealized_pnl_pct = position.unrealized_pnl / position.avg_buy_price
        return unrealized_pnl_pct <= self.stop_loss_pct
```

---

## 🛠️ 기술 스택 최종 확정

### Backend

- **Python 3.11+**
- **aiohttp** - 비동기 HTTP 클라이언트 (KIS REST API 호출)
- **websockets** - WebSocket 클라이언트 (KIS 실시간 API) ⭐
- **asyncio** - 비동기 처리 (REST + WebSocket 동시 처리)
- **APScheduler** - 스케줄링 (시장시간 체크, 주기적 실행)

### 데이터 처리

- **pandas** - 시세 데이터 분석
- **TA-Lib** - 기술적 지표 계산 (RSI, MA, MACD 등)
- **SQLite3** - 로컬 데이터 저장
- **aiosqlite** - 비동기 SQLite 조작

### 설정 및 로깅

- **python-dotenv** - 환경변수 관리 (.env)
- **pydantic** - 설정 및 데이터 검증
- **loguru** - 구조화된 로깅
- **telegram-bot-api** - 알림 발송

### 테스트 및 검증

- **pytest** - 단위 테스트
- **pytest-asyncio** - 비동기 테스트
- **backtrader** - 백테스팅 (전략 검증)

---

## 📅 구현 로드맵

### Phase 1: 기반 인프라 (1주)

**목표**: KIS API 연동 및 기본 데이터 수집

#### Day 1-2: 프로젝트 설정

- [x] 프로젝트 구조 생성 (`/src`, `/tests`, `/config`)
- [x] `requirements.txt` 및 가상환경 설정
- [x] `.env.example` 파일 생성 (API 키 관리)

#### Day 3-4: KIS API 인증

- [ ] `KISAuthManager` 클래스 구현
  - OAuth2 토큰 발급/갱신 (`/oauth2/tokenP`)
  - 토큰 파일 저장/로드 (JSON)
  - 토큰 만료시간 체크 및 자동 갱신
- [ ] 실전/모의투자 환경 분리
- [ ] 단위 테스트 작성

#### Day 5-7: 실시간 데이터 시스템 구축 ⭐

- [ ] **WebSocket Handler 구현** (핵심!)
  - WebSocket 연결 및 인증 (`auth_ws()`)
  - 실시간 호가 구독 (`H0STASP0`)
  - 실시간 체결 구독 (`H0STCNT0`)
- [ ] `MarketDataManager` 구현 (REST + WebSocket 하이브리드)
  - REST: 일봉 차트 조회 (기술적 분석용)
  - WebSocket: 실시간 호가/체결 데이터
- [ ] SQLite 데이터베이스 초기화 (실시간 테이블 포함)
- [ ] 기본 로깅 시스템 구축

### Phase 2: 매매전략 및 주문시스템 (1주)

**목표**: RSI 전략 구현 및 주문 실행 시스템

#### Day 8-10: 실시간 매매전략 엔진

- [ ] TA-Lib 연동 및 지표 계산 함수
  - RSI (14일), 이동평균 (5일, 20일)
  - 데이터 검증 및 예외 처리
- [ ] **실시간 RSIStrategy 클래스 구현** ⭐
  - **실시간 호가 기반 진입점 판단** (WebSocket 데이터 활용)
  - 기술적 분석 + 실시간 호가 잔량 분석
  - 시그널 생성 로직 (차트 분석 + 실시간 판단)
- [ ] 전략 성과 측정 지표
- [ ] **실시간 백테스팅** (과거 데이터 + 실시간 시뮬레이션)

#### Day 11-14: 주문 실행 시스템

- [ ] `TradingEngine` 구현
  - 현금 주문 실행 (`order-cash`)
  - 주문 상태 추적 및 체결 확인
  - 포지션 실시간 업데이트
- [ ] `RiskManager` 구현
  - 포지션 크기 제한, 손익 관리
- [ ] 모의 주문 시스템으로 전략 검증

### Phase 3: 운영 시스템 (1주)

**목표**: 실시간 모니터링 및 안정화

#### Day 15-17: 실시간 운영

- [ ] 스케줄러 설정 (장 운영시간 체크)
- [ ] 실시간 매매 루프 구현
- [ ] 에러 처리 및 복구 로직
- [ ] 텔레그램 봇 알림 시스템

#### Day 18-21: 모니터링 및 최적화

- [ ] 대시보드 구현 (수익률, 거래내역)
- [ ] **API 호출 횟수 최적화** (Rate Limit 모니터링)
- [ ] **캐싱 전략 개선** (불필요한 API 호출 제거)
- [ ] 성능 튜닝 및 안정성 개선
- [ ] 백테스팅 결과와 실제 결과 비교 분석

---

## 🎯 성공 지표 (KPI)

### 기술적 지표

- **API 응답시간**: 평균 < 500ms
- **시스템 가동율**: > 99% (장중 9:00~15:30)
- **데이터 정확도**: 시세 데이터 오차 < 0.1%
- **API 호출 준수율**: 99% (Rate Limit 위반 < 1%)
- **캐시 적중률**: > 80% (불필요한 API 호출 감소)

### 재무적 지표

- **수익률**: 최소 연 5% 목표 (3주 검증기간)
- **최대 손실**: 일일 -3%, 총 -10% 제한
- **거래 비용**: 수수료 + 세금 < 수익의 30%

### 운영 지표

- **매매 빈도**: 주 2-5회 (과도한 매매 방지)
- **신호 정확도**: 매수/매도 신호의 60% 이상 수익
- **에러 발생률**: < 1% (주문 실패, API 오류 등)

---

## 🚨 리스크 관리 계획

### 기술적 리스크

- **API 장애**: KIS API 서버 다운 → 수동 매매 전환 프로세스
- **Rate Limit 초과**: 호출 제한 위반 → 지수 백오프, 캐싱 강화
- **네트워크 지연**: 주문 지연 → 타임아웃 설정 및 재시도 로직
- **데이터 오류**: 잘못된 시세 → 다중 소스 검증
- **토큰 만료**: 갑작스런 인증 실패 → 자동 토큰 갱신 로직

### 재무적 리스크

- **급격한 시장 변동**: → 스톱로스 자동 실행
- **유동성 부족**: → 거래량 체크 후 주문
- **과도한 매매**: → 일일 거래 횟수 제한

### 운영 리스크

- **시스템 다운**: → 헬스체크 및 자동 재시작
- **잘못된 전략**: → 실시간 성과 모니터링 및 중단
- **규정 위반**: → 금융당국 가이드라인 준수

---

## 📈 확장 계획 (Post-MVP)

### Phase 4: 고도화 전략 (4주차~)

1. **다중 전략 지원**

   - MACD, 볼린저밴드, 스토캐스틱 추가
   - 전략 포트폴리오 및 가중치 최적화

2. **머신러닝 도입**

   - 뉴스 감성분석, 기업 펀더멘털 분석
   - 강화학습 기반 전략 자동 최적화

3. **다중 계좌/종목**

   - 여러 계좌 동시 관리
   - 섹터별, 테마별 분산투자

4. **웹 인터페이스**
   - React/FastAPI 기반 대시보드
   - 실시간 모니터링 및 수동 개입

---

## 💡 결론

이 MVP는 **한국투자증권 OpenAPI의 실시간 활용성**과 **WebSocket 기반 자동매매 전략의 유효성**을 검증하는 것이 핵심 목표입니다.

### 🎯 핵심 검증 포인트

1. **실시간 데이터의 위력**:

   - REST API (과거 데이터) vs WebSocket (실시간 데이터)의 매매 성과 차이
   - 실시간 호가창 분석이 진입점 최적화에 미치는 영향

2. **하이브리드 전략의 효과**:

   - 기술적 분석 (RSI, MA) + 실시간 호가 분석 복합 전략
   - 단순 차트 분석 대비 실시간 시장 상황 반영 효과

3. **API 제한 환경에서의 최적화**:
   - Rate Limit (1초당 20건) 하에서 실시간 매매 가능성
   - WebSocket을 활용한 API 호출 최소화 전략

### 3주간의 단계별 개발 목표:

1. **Week 1**: WebSocket 실시간 시스템 구축 + API Rate Limit 관리
2. **Week 2**: 실시간 RSI 전략 구현 + 호가창 분석 엔진
3. **Week 3**: 실운영 검증 + 성과 분석

**🚀 예상 결과**: 실시간 데이터 활용으로 기존 REST API 기반 대비 **20-30% 성과 향상** 목표

성공적인 MVP 검증 후, 머신러닝 기반 호가 예측, 다중 전략 포트폴리오 등으로 확장할 예정입니다.
