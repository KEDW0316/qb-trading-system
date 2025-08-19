#!/usr/bin/env python3
"""
KIS WebSocket Handler 미국 주식 실시간 테스트
실시간 호가 정보 수신 및 파싱 테스트
"""

import asyncio
import logging
from dotenv import load_dotenv
from src.auth.kis_auth import KISAuthManager
from src.api.websocket_handler import KISWebSocketHandler

load_dotenv()

# 로깅 설정 - DEBUG로 변경하여 상세 로그 확인
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test():
    # 초기화
    import os
    env = os.getenv("KIS_ENV", "vps")
    auth = KISAuthManager(env=env)
    ws_handler = KISWebSocketHandler(auth)
    print(f"환경: {env}")
    
    # 콜백 함수 정의
    async def on_us_quote(data):
        """미국 주식 호가 데이터 콜백 - 실시간 호가 정보"""
        if len(data) > 0:
            row = data.iloc[0]  # 첫 번째 행 데이터 가져오기
            symb = row.get('symb', 'N/A')  # 종목코드
            xymd = row.get('xymd', 'N/A')  # 현지일자
            xhms = row.get('xhms', 'N/A')  # 현지시간
            kymd = row.get('kymd', 'N/A')  # 한국일자
            khms = row.get('khms', 'N/A')  # 한국시간
            pbid1 = row.get('pbid1', 'N/A')  # 매수호가1
            pask1 = row.get('pask1', 'N/A')  # 매도호가1
            vbid1 = row.get('vbid1', 'N/A')  # 매수잔량1
            vask1 = row.get('vask1', 'N/A')  # 매도잔량1
            
            print(f"📊 [미국-호가] {symb}")
            print(f"   🕐 현지시간: {xymd} {xhms} | 한국시간: {kymd} {khms}")
            print(f"   🔴 매도1: ${pask1} ({vask1}주) | 🔵 매수1: ${pbid1} ({vbid1}주)")
            print(f"   📈 스프레드: ${float(pask1) - float(pbid1) if pask1 != 'N/A' and pbid1 != 'N/A' else 'N/A'}")
    
    async def on_us_tick(data):
        """미국 주식 체결 데이터 콜백 - 실시간 체결 정보"""
        if len(data) > 0:
            row = data.iloc[0]  # 첫 번째 행 데이터 가져오기
            symb = row.get('symb', 'N/A')  # 종목코드 (소문자)
            xymd = row.get('xymd', 'N/A')  # 현지일자
            xhms = row.get('xhms', 'N/A')  # 현지시간
            kymd = row.get('kymd', 'N/A')  # 한국일자
            khms = row.get('khms', 'N/A')  # 한국시간
            last = row.get('last', 'N/A')  # 현재가
            diff = row.get('diff', 'N/A')  # 전일대비
            rate = row.get('rate', 'N/A')  # 등락률
            sign = row.get('sign', 'N/A')  # 등락부호
            tvol = row.get('tvol', 'N/A')  # 거래량
            tamt = row.get('tamt', 'N/A')  # 거래대금
            
            # 부호 처리
            sign_symbol = "🔺" if sign == "2" else "🔻" if sign == "5" else "⏸️"
            
            print(f"🔥 [미국-체결] {symb}")
            print(f"   🕐 현지시간: {xymd} {xhms} | 한국시간: {kymd} {khms}")
            print(f"   💰 현재가: ${last} {sign_symbol} ${diff} ({rate}%)")
            print(f"   📊 거래량: {tvol}주 | 거래대금: ${tamt}")
            print("   " + "="*50)
    
    async def on_error(error, message=None):
        """에러 콜백"""
        print(f"❌ 에러: {error}")
        if message:
            print(f"   메시지: {message[:100]}...")
    
    # 콜백 설정
    ws_handler.set_callbacks(
        on_quote=on_us_quote,
        on_tick=on_us_tick,
        on_error=on_error
    )
    
    try:
        print("\n1. WebSocket 연결")
        success = await ws_handler.connect()
        if not success:
            print("❌ WebSocket 연결 실패")
            return
        print("✅ WebSocket 연결 성공")
        
        print("\n2. 미국 실시간 호가 구독 (AAPL, F)")
        success = await ws_handler.subscribe_us_quote(
            symbols=["AAPL", "F"],
            exchange="NASD"  # 나스닥
        )
        if success:
            print("✅ 미국 호가 구독 성공")
        else:
            print("❌ 미국 호가 구독 실패")
        
        print("\n3. 미국 실시간 체결 구독 (AAPL, F)")
        success = await ws_handler.subscribe_us_tick(
            symbols=["AAPL", "F"],
            exchange="NASD"  # 나스닥
        )
        if success:
            print("✅ 미국 체결 구독 성공")
        else:
            print("❌ 미국 체결 구독 실패")
        
        print("\n4. 30초간 실시간 데이터 수신 대기...")
        print("   (Ctrl+C로 중단 가능)")
        print("   💡 미국 시장 시간 확인:")
        print("      - 정규시간: 한국시간 23:30~06:00 (서머타임 22:30~05:00)")
        print("      - 프리마켓: 한국시간 17:00~23:30 (서머타임 16:00~22:30)")
        await asyncio.sleep(30)
        
        print("\n5. 구독 해제")
        for symbol in ["AAPL", "F"]:
            await ws_handler.unsubscribe_us_stock(symbol, data_type="all", exchange="NASD")
        print("✅ 구독 해제 완료")
        
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다.")
    except Exception as e:
        print(f"❌ 테스트 중 오류: {e}")
    finally:
        print("\n6. WebSocket 연결 종료")
        await ws_handler.disconnect()
        print("✅ 연결 종료 완료")


if __name__ == "__main__":
    print("🚀 KIS WebSocket Handler 미국 주식 테스트")
    print("AAPL(Apple), F(Ford) 실시간 호가/체결 데이터를 30초간 수신합니다.")
    print("=== 미국 주식 실시간 데이터 파싱 테스트 ===")
    
    try:
        asyncio.run(test())
    except Exception as e:
        print(f"❌ 실행 중 오류: {e}")