#!/usr/bin/env python3
"""
한국 주식 WebSocket 테스트
기존 websocket_test.py를 새 구조로 마이그레이션
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
    env = os.getenv("KIS_ENV", "prod")
    auth = KISAuthManager(env=env)
    
    # 새로운 통합 WebSocket 사용
    ws_handler = UnifiedWebSocket(auth)
    print(f"환경: {env}")
    
    # 콜백 함수 정의
    async def on_quote(data, market):
        """호가 데이터 콜백 - 실시간 호가 정보"""
        if len(data) > 0:
            row = data.iloc[0]
            stock_code = row.get('MKSC_SHRN_ISCD', 'N/A')
            bsop_hour = row.get('BSOP_HOUR', 'N/A')
            askp1 = row.get('ASKP1', 'N/A')
            bidp1 = row.get('BIDP1', 'N/A')
            askp_rsqn1 = row.get('ASKP_RSQN1', 'N/A')
            bidp_rsqn1 = row.get('BIDP_RSQN1', 'N/A')
            total_askp_rsqn = row.get('TOTAL_ASKP_RSQN', 'N/A')
            total_bidp_rsqn = row.get('TOTAL_BIDP_RSQN', 'N/A')
            antc_cnpr = row.get('ANTC_CNPR', 'N/A')
            
            print(f"📊 [{market}-호가] {stock_code} ({bsop_hour})")
            print(f"   🔴 매도1: {askp1}원 ({askp_rsqn1}주) | 🔵 매수1: {bidp1}원 ({bidp_rsqn1}주)")
            print(f"   📈 예상체결가: {antc_cnpr}원 | 총잔량 매도:{total_askp_rsqn} / 매수:{total_bidp_rsqn}")
    
    async def on_tick(data, market):
        """체결 데이터 콜백 - 실시간 체결 정보"""
        if len(data) > 0:
            row = data.iloc[0]
            stock_code = row.get('MKSC_SHRN_ISCD', 'N/A')
            stck_cntg_hour = row.get('STCK_CNTG_HOUR', 'N/A')
            stck_prpr = row.get('STCK_PRPR', 'N/A')
            prdy_vrss = row.get('PRDY_VRSS', 'N/A')
            prdy_vrss_sign = row.get('PRDY_VRSS_SIGN', 'N/A')
            prdy_ctrt = row.get('PRDY_CTRT', 'N/A')
            cntg_vol = row.get('CNTG_VOL', 'N/A')
            acml_vol = row.get('ACML_VOL', 'N/A')
            acml_tr_pbmn = row.get('ACML_TR_PBMN', 'N/A')
            seln_cntg_csnu = row.get('SELN_CNTG_CSNU', 'N/A')
            shnu_cntg_csnu = row.get('SHNU_CNTG_CSNU', 'N/A')
            
            # 부호 처리
            sign_symbol = "🔺" if prdy_vrss_sign == "2" else "🔻" if prdy_vrss_sign == "5" else "⏸️"
            
            print(f"🔥 [{market}-체결] {stock_code} ({stck_cntg_hour})")
            print(f"   💰 현재가: {stck_prpr}원 {sign_symbol} {prdy_vrss}원 ({prdy_ctrt}%)")
            print(f"   📊 체결량: {cntg_vol}주 | 누적: {acml_vol}주 | 대금: {acml_tr_pbmn}원")
            print(f"   ⚖️  매도건수: {seln_cntg_csnu} | 매수건수: {shnu_cntg_csnu}")
            print("   " + "="*50)
    
    async def on_error(error, message=None, market=None):
        """에러 콜백"""
        print(f"❌ [{market}] 에러: {error}")
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
        results = await ws_handler.connect(markets="KR")  # 한국 시장만 연결
        if results.get("KR"):
            print("✅ 한국 WebSocket 연결 성공")
        else:
            print("❌ 한국 WebSocket 연결 실패")
            return
        
        print("\n2. 실시간 호가 구독 (삼성전자, SK하이닉스)")
        quote_results = await ws_handler.subscribe_quote(
            codes=["005930", "000660"],
            exchange="UN"  # 통합거래소
        )
        if quote_results.get("KR"):
            print("✅ 호가 구독 성공")
        else:
            print("❌ 호가 구독 실패")
        
        print("\n3. 실시간 체결 구독 (삼성전자, SK하이닉스)")
        tick_results = await ws_handler.subscribe_tick(
            codes=["005930", "000660"],
            exchange="SOR"  # 스마트라우팅
        )
        if tick_results.get("KR"):
            print("✅ 체결 구독 성공")
        else:
            print("❌ 체결 구독 실패")
        
        print("\n4. 30초간 실시간 데이터 수신 대기...")
        print("   (Ctrl+C로 중단 가능)")
        await asyncio.sleep(30)
        
        print("\n5. 구독 해제")
        await ws_handler.unsubscribe(["005930", "000660"], data_type="all")
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
    print("🚀 한국 주식 WebSocket 테스트")
    print("삼성전자(005930), SK하이닉스(000660) 실시간 호가/체결 데이터를 30초간 수신합니다.")
    
    try:
        asyncio.run(test())
    except Exception as e:
        print(f"❌ 실행 중 오류: {e}")