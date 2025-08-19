#!/usr/bin/env python3
"""
KIS WebSocket Handler 간단 테스트
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
    async def on_quote(data):
        """호가 데이터 콜백 - 실시간 호가 정보"""
        if len(data) > 0:
            row = data.iloc[0]  # 첫 번째 행 데이터 가져오기
            stock_code = row.get('MKSC_SHRN_ISCD', 'N/A')
            bsop_hour = row.get('BSOP_HOUR', 'N/A')  # 영업시간
            askp1 = row.get('ASKP1', 'N/A')  # 매도호가1
            bidp1 = row.get('BIDP1', 'N/A')  # 매수호가1
            askp_rsqn1 = row.get('ASKP_RSQN1', 'N/A')  # 매도호가수량1
            bidp_rsqn1 = row.get('BIDP_RSQN1', 'N/A')  # 매수호가수량1
            total_askp_rsqn = row.get('TOTAL_ASKP_RSQN', 'N/A')  # 총매도호가잔량
            total_bidp_rsqn = row.get('TOTAL_BIDP_RSQN', 'N/A')  # 총매수호가잔량
            antc_cnpr = row.get('ANTC_CNPR', 'N/A')  # 예상체결가
            
            print(f"📊 [호가-UN] {stock_code} ({bsop_hour})")
            print(f"   🔴 매도1: {askp1}원 ({askp_rsqn1}주) | 🔵 매수1: {bidp1}원 ({bidp_rsqn1}주)")
            print(f"   📈 예상체결가: {antc_cnpr}원 | 총잔량 매도:{total_askp_rsqn} / 매수:{total_bidp_rsqn}")
    
    async def on_tick(data):
        """체결 데이터 콜백 - SOR 실시간 체결 정보"""
        if len(data) > 0:
            row = data.iloc[0]  # 첫 번째 행 데이터 가져오기
            stock_code = row.get('MKSC_SHRN_ISCD', 'N/A')
            stck_cntg_hour = row.get('STCK_CNTG_HOUR', 'N/A')  # 체결시간
            stck_prpr = row.get('STCK_PRPR', 'N/A')  # 현재가
            prdy_vrss = row.get('PRDY_VRSS', 'N/A')  # 전일대비
            prdy_vrss_sign = row.get('PRDY_VRSS_SIGN', 'N/A')  # 전일대비부호
            prdy_ctrt = row.get('PRDY_CTRT', 'N/A')  # 전일대비율
            cntg_vol = row.get('CNTG_VOL', 'N/A')  # 체결거래량
            acml_vol = row.get('ACML_VOL', 'N/A')  # 누적거래량
            acml_tr_pbmn = row.get('ACML_TR_PBMN', 'N/A')  # 누적거래대금
            seln_cntg_csnu = row.get('SELN_CNTG_CSNU', 'N/A')  # 매도체결건수
            shnu_cntg_csnu = row.get('SHNU_CNTG_CSNU', 'N/A')  # 매수체결건수
            
            # 부호 처리
            sign_symbol = "🔺" if prdy_vrss_sign == "2" else "🔻" if prdy_vrss_sign == "5" else "⏸️"
            
            print(f"🔥 [체결-SOR] {stock_code} ({stck_cntg_hour})")
            print(f"   💰 현재가: {stck_prpr}원 {sign_symbol} {prdy_vrss}원 ({prdy_ctrt}%)")
            print(f"   📊 체결량: {cntg_vol}주 | 누적: {acml_vol}주 | 대금: {acml_tr_pbmn}원")
            print(f"   ⚖️  매도건수: {seln_cntg_csnu} | 매수건수: {shnu_cntg_csnu}")
            print("   " + "="*50)
    
    async def on_error(error, message=None):
        """에러 콜백"""
        print(f"❌ 에러: {error}")
        if message:
            print(f"   메시지: {message[:100]}...")
    
    # 콜백 설정
    ws_handler.set_callbacks(
        on_quote=on_quote,
        on_tick=on_tick,
        on_error=on_error
    )
    
    try:
        print("\n1. WebSocket 연결")
        success = await ws_handler.connect()
        if not success:
            print("❌ WebSocket 연결 실패")
            return
        print("✅ WebSocket 연결 성공")
        
        print("\n2. 실시간 호가 구독 (삼성전자, SK하이닉스)")
        success = await ws_handler.subscribe_quote(
            stock_codes=["005930", "000660"], 
            exchange="UN"  # 통합거래소
        )
        if success:
            print("✅ 호가 구독 성공")
        else:
            print("❌ 호가 구독 실패")
        
        print("\n3. 실시간 체결 구독 (삼성전자, SK하이닉스)")
        success = await ws_handler.subscribe_tick(
            stock_codes=["005930", "000660"],
            exchange="SOR"  # 스마트라우팅
        )
        if success:
            print("✅ 체결 구독 성공")
        else:
            print("❌ 체결 구독 실패")
        
        print("\n4. 30초간 실시간 데이터 수신 대기...")
        print("   (Ctrl+C로 중단 가능)")
        await asyncio.sleep(30)
        
        print("\n5. 구독 해제")
        await ws_handler.unsubscribe_quote(["005930", "000660"], exchange="UN")
        await ws_handler.unsubscribe_tick(["005930", "000660"], exchange="SOR")
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
    print("🚀 KIS WebSocket Handler 테스트")
    print("삼성전자(005930) 실시간 호가/체결 데이터를 30초간 수신합니다.")
    
    try:
        asyncio.run(test())
    except Exception as e:
        print(f"❌ 실행 중 오류: {e}")