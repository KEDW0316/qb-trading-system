#!/usr/bin/env python3
"""
통합 클라이언트 테스트
한국/미국 시장 자동 감지 기능 테스트
"""

import asyncio
from dotenv import load_dotenv
from src.auth.kis_auth import KISAuthManager
from src.utils.rate_limiter import RateLimiter
from src.api import UnifiedClient

load_dotenv()


async def test():
    # 초기화
    import os
    env = os.getenv("KIS_ENV", "vps")
    auth = KISAuthManager(env=env)
    limiter = RateLimiter()
    
    client = UnifiedClient(auth, limiter)
    print(f"환경: {env}")
    print("=" * 60)
    
    # 1. 자동 시장 감지 테스트
    print("\n1. 자동 시장 감지 테스트")
    print("-" * 40)
    
    # 한국 주식 (6자리 숫자 → 자동으로 한국 시장)
    print("\n   📍 한국 주식 테스트 (005930)")
    try:
        kr_price = await client.get_price("005930")  # market 파라미터 없이
        print(f"   ✅ 삼성전자 현재가: {kr_price.get('stck_prpr')}원")
        print(f"      시장 자동 감지: 한국 (6자리 숫자)")
    except Exception as e:
        print(f"   ❌ 한국 주식 조회 실패: {e}")
    
    # 미국 주식 (알파벳 → 자동으로 미국 시장)
    print("\n   📍 미국 주식 테스트 (AAPL)")
    try:
        us_price = await client.get_price("AAPL")  # market 파라미터 없이
        print(f"   ✅ Apple 현재가: ${us_price.get('last', us_price.get('base'))}")
        print(f"      시장 자동 감지: 미국 (알파벳)")
    except Exception as e:
        print(f"   ❌ 미국 주식 조회 실패: {e}")
    
    # 2. 통합 잔고 조회
    print("\n2. 통합 잔고 조회")
    print("-" * 40)
    
    try:
        all_balance = await client.get_balance(market="all")
        
        if "korea" in all_balance:
            kr_summary = all_balance["korea"].get("summary", {})
            kr_stocks = all_balance["korea"].get("stocks", [])
            print(f"\n   🇰🇷 한국 계좌:")
            print(f"      예수금: {kr_summary.get('dnca_tot_amt', 0)}원")
            print(f"      보유종목: {len(kr_stocks)}개")
        
        if "usa" in all_balance:
            us_summary = all_balance["usa"].get("summary", {})
            us_stocks = all_balance["usa"].get("stocks", [])
            print(f"\n   🇺🇸 미국 계좌:")
            print(f"      예수금: ${us_summary.get('frcr_dncl_amt_2', 0)}")
            print(f"      보유종목: {len(us_stocks)}개")
            
    except Exception as e:
        print(f"   ❌ 잔고 조회 실패: {e}")
    
    # 3. 통합 주문 내역 조회
    print("\n3. 통합 주문 내역 조회")
    print("-" * 40)
    
    try:
        all_orders = await client.get_orders(market="all")
        
        if "korea" in all_orders:
            kr_orders = all_orders["korea"]
            print(f"\n   🇰🇷 한국 주문: {len(kr_orders)}건")
            if kr_orders and len(kr_orders) > 0:
                latest = kr_orders[0]
                print(f"      최근: {latest.get('ord_dt')} {latest.get('pdno')} {latest.get('ord_qty')}주")
        
        if "usa" in all_orders:
            us_orders = all_orders["usa"]
            print(f"\n   🇺🇸 미국 주문: {len(us_orders)}건")
            if us_orders and len(us_orders) > 0:
                latest = us_orders[0]
                print(f"      최근: {latest.get('ord_dt')} {latest.get('pdno')} {latest.get('ord_qty')}주")
                
    except Exception as e:
        print(f"   ❌ 주문 내역 조회 실패: {e}")
    
    # 4. 명시적 시장 지정 테스트
    print("\n4. 명시적 시장 지정 테스트")
    print("-" * 40)
    
    # market 파라미터로 명시적 지정
    print("\n   📍 market 파라미터 사용")
    try:
        # 한국 시장 명시
        kr_result = await client.get_price("005930", market="KR")
        print(f"   ✅ market='KR' 지정: {kr_result.get('stck_prpr')}원")
        
        # 미국 시장 명시
        us_result = await client.get_price("AAPL", market="US")
        print(f"   ✅ market='US' 지정: ${us_result.get('last', us_result.get('base'))}")
        
    except Exception as e:
        print(f"   ❌ 명시적 시장 지정 실패: {e}")
    
    # 5. 차트 데이터 자동 감지
    print("\n5. 차트 데이터 자동 감지")
    print("-" * 40)
    
    try:
        # 한국 차트 (List 반환)
        kr_chart = await client.get_chart("005930", period="D")
        print(f"\n   🇰🇷 한국 차트: {len(kr_chart) if isinstance(kr_chart, list) else 'N/A'}개 데이터")
        
        # 미국 차트 (Tuple 반환)
        us_chart = await client.get_chart("AAPL", period="D")
        if isinstance(us_chart, tuple):
            chart_data, summary = us_chart
            print(f"   🇺🇸 미국 차트: {len(chart_data)}개 데이터")
        else:
            print(f"   🇺🇸 미국 차트: 데이터 형식 오류")
            
    except Exception as e:
        print(f"   ❌ 차트 조회 실패: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 통합 클라이언트 테스트 완료")
    
    # 리소스 정리
    await client.close()


if __name__ == "__main__":
    print("🚀 통합 클라이언트 테스트")
    print("한국/미국 시장 자동 감지 및 통합 기능을 테스트합니다.")
    print("")
    
    asyncio.run(test())