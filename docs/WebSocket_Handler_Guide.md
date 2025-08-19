# KIS WebSocket Handler 사용 가이드

한국투자증권 OpenAPI WebSocket을 위한 래퍼 클래스 사용법

## 🚀 주요 기능

- **실시간 호가 데이터 수신** (H0STASP0)
- **실시간 체결 데이터 수신** (H0STCNT0) 
- **다중 종목 구독 지원**
- **거래소 선택 지원** (KRX, NXT, UN, SOR)
- **자동 재연결 기능**
- **에러 처리 및 복구**

## 📋 기본 사용법

### 1. 초기화

```python
from src.auth.kis_auth import KISAuthManager
from src.api.websocket_handler import KISWebSocketHandler

# 인증 관리자 생성
auth_manager = KISAuthManager()

# WebSocket 핸들러 생성
ws_handler = KISWebSocketHandler(
    auth_manager=auth_manager,
    max_retries=3  # 최대 재시도 횟수
)
```

### 2. 콜백 함수 설정

```python
async def on_quote_received(df):
    """실시간 호가 데이터 수신"""
    stock_code = df.iloc[0]['MKSC_SHRN_ISCD']
    bid_price = df.iloc[0]['BIDP1']  # 매수 1호가
    ask_price = df.iloc[0]['ASKP1']  # 매도 1호가
    print(f"[{stock_code}] 매수: {bid_price}, 매도: {ask_price}")

async def on_tick_received(df):
    """실시간 체결 데이터 수신"""
    stock_code = df.iloc[0]['MKSC_SHRN_ISCD']
    price = df.iloc[0]['STCK_PRPR']      # 현재가
    volume = df.iloc[0]['CNTG_VOL']      # 거래량
    print(f"[{stock_code}] 가격: {price}, 거래량: {volume}")

async def on_error_occurred(error, message=None):
    """에러 발생 처리"""
    print(f"WebSocket 에러: {error}")

# 콜백 함수 등록
ws_handler.set_callbacks(
    on_quote=on_quote_received,
    on_tick=on_tick_received, 
    on_error=on_error_occurred
)
```

### 3. 연결 및 구독

```python
# WebSocket 연결
await ws_handler.connect()

# 실시간 호가 구독
await ws_handler.subscribe_quote(
    stock_codes=["005930", "000660"],  # 삼성전자, SK하이닉스
    exchange="UN"  # 통합거래소
)

# 실시간 체결 구독  
await ws_handler.subscribe_tick(
    stock_codes=["005930", "000660"],
    exchange="UN"  # 통합거래소
)
```

### 4. 구독 해제 및 연결 종료

```python
# 특정 종목 구독 해제
await ws_handler.unsubscribe(
    stock_code="005930",
    data_type="all",  # "quote", "tick", "all"
    exchange="UN"
)

# WebSocket 연결 해제
await ws_handler.disconnect()
```

## 🏛️ 거래소 구분 코드

| 코드 | 설명 | 사용 시점 |
|------|------|----------|
| **UN** | 통합거래소 (기본값 권장) | 일반적인 실시간 데이터 |
| **SOR** | 스마트라우팅 | 최적 체결 경로 |  
| **KRX** | 정규장 | 정규 거래시간 |
| **NXT** | 야간거래 | 시간외 거래 |

## 📊 데이터 구조

### 실시간 호가 데이터 (H0STASP0)

주요 컬럼:
- `MKSC_SHRN_ISCD`: 종목코드
- `BIDP1~10`: 매수 호가 1~10단계
- `ASKP1~10`: 매도 호가 1~10단계  
- `BIDP_RSQN1~10`: 매수 호가 잔량 1~10단계
- `ASKP_RSQN1~10`: 매도 호가 잔량 1~10단계
- `TOTAL_BIDP_RSQN`: 매수 호가 총 잔량
- `TOTAL_ASKP_RSQN`: 매도 호가 총 잔량

### 실시간 체결 데이터 (H0STCNT0) 

주요 컬럼:
- `MKSC_SHRN_ISCD`: 종목코드
- `STCK_PRPR`: 현재가
- `PRDY_VRSS`: 전일대비
- `PRDY_CTRT`: 등락률
- `CNTG_VOL`: 체결거래량
- `ACML_VOL`: 누적거래량
- `ACML_TR_PBMN`: 누적거래대금

## 🔧 고급 사용법

### 다중 거래소 구독

```python
# KRX 정규장 구독
await ws_handler.subscribe_quote(["005930"], exchange="KRX")

# NXT 야간거래 구독  
await ws_handler.subscribe_quote(["005930"], exchange="NXT")

# 통합거래소 구독 (권장)
await ws_handler.subscribe_quote(["005930"], exchange="UN")
```

### 구독 상태 모니터링

```python
# 현재 구독 목록 확인
subscriptions = ws_handler.get_subscriptions()
print(f"구독 종목 수: {len(subscriptions)}")

# 연결 상태 확인
status = ws_handler.get_connection_status()
print(f"연결 상태: {status['is_connected']}")
print(f"재시도 횟수: {status['retry_count']}")
```

### 에러 처리 및 재연결

```python
async def on_error_occurred(error, message=None):
    """에러 발생 시 처리"""
    if "connection" in str(error).lower():
        print("연결 오류 발생 - 자동 재연결 시도 중...")
    else:
        print(f"시스템 오류: {error}")
        # 필요시 알림 발송, 로그 기록 등
```

## 📝 완전한 예제

```python
import asyncio
import logging
from src.auth.kis_auth import KISAuthManager
from src.api.websocket_handler import KISWebSocketHandler

async def main():
    # 초기화
    auth_manager = KISAuthManager()
    ws_handler = KISWebSocketHandler(auth_manager)
    
    # 콜백 설정
    async def on_quote(df):
        stock_code = df.iloc[0]['MKSC_SHRN_ISCD']
        bid = df.iloc[0]['BIDP1']
        ask = df.iloc[0]['ASKP1']
        print(f"[호가] {stock_code}: {bid} / {ask}")
    
    async def on_tick(df):
        stock_code = df.iloc[0]['MKSC_SHRN_ISCD']
        price = df.iloc[0]['STCK_PRPR']
        print(f"[체결] {stock_code}: {price}")
    
    ws_handler.set_callbacks(on_quote=on_quote, on_tick=on_tick)
    
    try:
        # 연결 및 구독
        await ws_handler.connect()
        await ws_handler.subscribe_quote(["005930", "000660"], exchange="UN")
        await ws_handler.subscribe_tick(["005930", "000660"], exchange="UN")
        
        # 30초간 데이터 수신
        await asyncio.sleep(30)
        
    finally:
        # 정리
        await ws_handler.disconnect()

# 실행
asyncio.run(main())
```

## ⚠️ 주의사항

1. **구독 제한**: 최대 40개 종목까지 동시 구독 가능
2. **Rate Limit**: 연속 구독 요청 시 0.1초 간격 권장  
3. **재연결**: 네트워크 단절 시 자동 재연결 및 구독 복원
4. **메모리 관리**: 장시간 운용 시 메모리 사용량 모니터링 필요
5. **거래소 선택**: 특별한 이유가 없다면 **UN(통합)**이나 **SOR(스마트)** 사용 권장

## 🔗 관련 문서

- [KIS OpenAPI 가이드](https://apiportal.koreainvestment.com/apiservice)
- [실시간 데이터 명세서](https://apiportal.koreainvestment.com/apiservice/apiservice-domestic-stock-realtime)
- [WebSocket 연결 가이드](https://apiportal.koreainvestment.com/intro/websocket)