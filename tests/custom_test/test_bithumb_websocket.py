import sys
import os
import asyncio
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.api.bithumb_api import BithumbWebSocket


async def test_public_websocket():
    """Public WebSocket 테스트"""
    print("=== 빗썸 Public WebSocket 테스트 ===")
    
    ws = BithumbWebSocket()
    
    # 1. Public WebSocket 연결
    print("\n1. Public WebSocket 연결 중...")
    if not await ws.connect_public():
        print("❌ Public WebSocket 연결 실패")
        return
    
    print("✅ Public WebSocket 연결 성공!")
    
    # 2. BTC 현재가 구독
    print("\n2. BTC 현재가 구독 시작...")
    
    async def ticker_callback(data):
        """현재가 콜백 함수"""
        print(f"🔔 콜백 실행 - 현재가: {data.get('trade_price', 0):,}원")
    
    await ws.subscribe_ticker(["KRW-BTC"], ticker_callback)
    
    # 3. BTC 체결 구독
    print("\n3. BTC 체결 구독 시작...")
    
    async def trade_callback(data):
        """체결 콜백 함수"""
        print(f"🔔 콜백 실행 - 체결: {data.get('trade_price', 0):,}원 x {data.get('trade_volume', 0)} BTC")
    
    await ws.subscribe_trade(["KRW-BTC"], trade_callback)
    
    # 4. BTC 호가 구독
    print("\n4. BTC 호가 구독 시작...")
    
    async def orderbook_callback(data):
        """호가 콜백 함수"""
        print(f"🔔 콜백 실행 - 호가 업데이트")
    
    await ws.subscribe_orderbook(["KRW-BTC"], orderbook_callback)
    
    # 5. 메시지 수신 시작 (10초간)
    print("\n5. 메시지 수신 시작 (10초간)...")
    print("실시간 데이터를 확인하세요!")
    
    try:
        # 10초간 메시지 수신
        await asyncio.wait_for(ws.listen_public(), timeout=10)
    except asyncio.TimeoutError:
        print("⏰ 10초 타임아웃 - 메시지 수신 종료")
    
    # 6. 연결 종료
    print("\n6. WebSocket 연결 종료...")
    await ws.close()
    print("✅ Public WebSocket 테스트 완료!")


async def test_private_websocket():
    """Private WebSocket 테스트 (인증 필요)"""
    print("\n=== 빗썸 Private WebSocket 테스트 ===")
    
    ws = BithumbWebSocket()  # 환경변수에서 API 키 자동 로드
    
    # 1. API 키 상태 확인
    print("\n1. API 키 상태 확인...")
    if not ws.api_key or not ws.secret_key:
        print("❌ API 키가 설정되지 않았습니다")
        print("환경변수 BIT_APP_KEY와 BIT_APP_SECRET을 설정하세요")
        return
    
    print("✅ API 키 확인됨")
    
    # 2. Private WebSocket 연결
    print("\n2. Private WebSocket 연결 중...")
    if not await ws.connect_private():
        print("❌ Private WebSocket 연결 실패")
        return
    
    print("✅ Private WebSocket 연결 성공!")
    
    # 3. 내 주문 구독
    print("\n3. 내 주문 구독 시작...")
    
    async def myorder_callback(data):
        """내 주문 콜백 함수"""
        print(f"🔔 콜백 실행 - 내 주문 업데이트")
    
    await ws.subscribe_my_order(["KRW-BTC"], myorder_callback)
    
    # 4. 내 자산 구독
    print("\n4. 내 자산 구독 시작...")
    
    async def myasset_callback(data):
        """내 자산 콜백 함수"""
        print(f"🔔 콜백 실행 - 내 자산 업데이트")
    
    await ws.subscribe_my_asset(myasset_callback)
    
    # 5. 메시지 수신 시작 (10초간)
    print("\n5. 메시지 수신 시작 (10초간)...")
    print("실시간 개인 데이터를 확인하세요!")
    
    try:
        # 10초간 메시지 수신
        await asyncio.wait_for(ws.listen_private(), timeout=10)
    except asyncio.TimeoutError:
        print("⏰ 10초 타임아웃 - 메시지 수신 종료")
    
    # 6. 연결 종료
    print("\n6. WebSocket 연결 종료...")
    await ws.close()
    print("✅ Private WebSocket 테스트 완료!")


async def test_websocket_connection_status():
    """WebSocket 연결 상태 테스트"""
    print("\n=== WebSocket 연결 상태 테스트 ===")
    
    ws = BithumbWebSocket()
    
    print(f"API 키 존재 여부: {'있음' if ws.api_key else '없음'}")
    print(f"시크릿 키 존재 여부: {'있음' if ws.secret_key else '없음'}")
    
    if ws.api_key and ws.secret_key:
        print("✅ 환경변수에서 API 키를 성공적으로 로드했습니다.")
    else:
        print("❌ 환경변수에서 API 키를 로드하지 못했습니다.")
        print("Private WebSocket 테스트는 건너뜁니다.")


async def main():
    """메인 테스트 함수"""
    print("🚀 Bithumb WebSocket API 테스트 시작!")
    
    # 연결 상태 확인
    await test_websocket_connection_status()
    
    # Public WebSocket 테스트
    await test_public_websocket()
    
    # Private WebSocket 테스트 (API 키가 있는 경우에만)
    ws = BithumbWebSocket()
    if ws.api_key and ws.secret_key:
        await test_private_websocket()
    else:
        print("\n⚠️ Private WebSocket 테스트는 API 키가 설정된 경우에만 실행됩니다.")
    
    print("\n🎉 모든 WebSocket 테스트 완료!")


if __name__ == "__main__":
    # asyncio 이벤트 루프 실행
    asyncio.run(main())
