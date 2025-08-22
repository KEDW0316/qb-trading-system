#!/usr/bin/env python3
"""
미국 주식 WebSocket 테스트
기존 us_stock_websocket_test.py를 새 구조로 마이그레이션
"""

import asyncio
import logging
from dotenv import load_dotenv
from src.auth.kis_auth import KISAuthManager
from src.api import UnifiedWebSocket  # 새로운 통합 WebSocket 사용

load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test():
    # 초기화
    import os
    env = os.getenv("KIS_ENV", "vps")
    auth = KISAuthManager(env=env)
    
    # 새로운 통합 WebSocket 사용
    ws_handler = UnifiedWebSocket(auth)
    print(f"환경: {env}")
    
    # 콜백 함수 정의
    async def on_us_quote(data, market):
        """미국 주식 호가 데이터 콜백 - 실시간 호가 정보"""
        if len(data) > 0:
            row = data.iloc[0]
            symb = row.get('symb', 'N/A')
            xymd = row.get('xymd', 'N/A')
            xhms = row.get('xhms', 'N/A')
            kymd = row.get('kymd', 'N/A')
            khms = row.get('khms', 'N/A')
            pbid1 = row.get('pbid1', 'N/A')
            pask1 = row.get('pask1', 'N/A')
            vbid1 = row.get('vbid1', 'N/A')
            vask1 = row.get('vask1', 'N/A')
            
            print(f"📊 [{market}-호가] {symb}")
            print(f"   🕐 현지시간: {xymd} {xhms} | 한국시간: {kymd} {khms}")
            print(f"   🔴 매도1: ${pask1} ({vask1}주) | 🔵 매수1: ${pbid1} ({vbid1}주)")
            try:
                spread = float(pask1) - float(pbid1)
                print(f"   📈 스프레드: ${spread:.2f}")
            except:
                print(f"   📈 스프레드: N/A")
    
    async def on_us_tick(data, market):
        """미국 주식 체결 데이터 콜백 - 실시간 체결 정보"""
        if len(data) > 0:
            row = data.iloc[0]
            symb = row.get('symb', 'N/A')
            xymd = row.get('xymd', 'N/A')
            xhms = row.get('xhms', 'N/A')
            kymd = row.get('kymd', 'N/A')
            khms = row.get('khms', 'N/A')
            last = row.get('last', 'N/A')
            diff = row.get('diff', 'N/A')
            rate = row.get('rate', 'N/A')
            sign = row.get('sign', 'N/A')
            tvol = row.get('tvol', 'N/A')
            tamt = row.get('tamt', 'N/A')
            
            # 부호 처리
            sign_symbol = "🔺" if sign == "2" else "🔻" if sign == "5" else "⏸️"
            
            print(f"🔥 [{market}-체결] {symb}")
            print(f"   🕐 현지시간: {xymd} {xhms} | 한국시간: {kymd} {khms}")
            print(f"   💰 현재가: ${last} {sign_symbol} ${diff} ({rate}%)")
            print(f"   📊 거래량: {tvol}주 | 거래대금: ${tamt}")
            print("   " + "="*50)
    
    async def on_error(error, message=None, market=None):
        """에러 콜백"""
        print(f"❌ [{market}] 에러: {error}")
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
        results = await ws_handler.connect(markets="US")  # 미국 시장만 연결
        if results.get("US"):
            print("✅ 미국 WebSocket 연결 성공")
        else:
            print("❌ 미국 WebSocket 연결 실패")
            return
        
        print("\n2. 미국 실시간 호가 구독 (AAPL, F)")
        quote_results = await ws_handler.subscribe_quote(
            codes=["AAPL", "F"],
            market="US",  # 명시적으로 미국 시장 지정
            exchange="NASD"  # 나스닥
        )
        if quote_results.get("US"):
            print("✅ 미국 호가 구독 성공")
        else:
            print("❌ 미국 호가 구독 실패")
        
        print("\n3. 미국 실시간 체결 구독 (AAPL, F)")
        tick_results = await ws_handler.subscribe_tick(
            codes=["AAPL", "F"],
            market="US",  # 명시적으로 미국 시장 지정
            exchange="NASD"  # 나스닥
        )
        if tick_results.get("US"):
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
        await ws_handler.unsubscribe(["AAPL", "F"], data_type="all", market="US")
        print("✅ 구독 해제 완료")
        
    except KeyboardInterrupt:
        print("\n사용자가 중단했습니다.")
    except Exception as e:
        print(f"❌ 테스트 중 오류: {e}")
    finally:
        print("\n6. WebSocket 연결 종료")
        await ws_handler.disconnect(markets="US")
        print("✅ 연결 종료 완료")


if __name__ == "__main__":
    print("🚀 미국 주식 WebSocket 테스트")
    print("AAPL(Apple), F(Ford) 실시간 호가/체결 데이터를 30초간 수신합니다.")
    print("=== 미국 주식 실시간 데이터 파싱 테스트 ===")
    
    try:
        asyncio.run(test())
    except Exception as e:
        print(f"❌ 실행 중 오류: {e}")