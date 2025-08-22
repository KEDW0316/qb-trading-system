#!/usr/bin/env python3
"""
한국 주식 REST API 테스트
기존 basic_api_wrapper_test.py를 새 구조로 마이그레이션
"""

import asyncio
from dotenv import load_dotenv
from src.auth.kis_auth import KISAuthManager
from src.utils.rate_limiter import RateLimiter
from src.api import UnifiedClient  # 새로운 통합 클라이언트 사용

load_dotenv()


async def test():
    # 초기화
    import os
    env = os.getenv("KIS_ENV", "vps")  # .env에서 읽기, 기본값 vps
    auth = KISAuthManager(env=env)
    limiter = RateLimiter()
    
    # 새로운 통합 클라이언트 사용
    client = UnifiedClient(auth, limiter)
    print(f"환경: {env}")
    
    # 1. 현재가
    print("\n1. 현재가")
    price_data = await client.get_price("005930")  # 자동으로 한국 주식 감지
    print(f"   삼성전자: {price_data.get('stck_prpr')}원")
    
    # 2. 일봉
    print("\n2. 일봉")
    chart = await client.get_chart("005930", "20250815", "20250818")
    if chart:
        print(f"   최근: {chart[0].get('stck_bsop_date')} - {chart[0].get('stck_clpr')}원")
    
    # 3. 잔고
    print("\n3. 잔고")
    balance = await client.get_balance(market="KR")
    if "korea" in balance:
        stocks = balance["korea"]["stocks"]
        summary = balance["korea"]["summary"]
        print(f"   예수금: {summary.get('dnca_tot_amt')}원")
        print(f"   보유종목: {len(stocks)}개")
    
    # 4. 주문내역
    print("\n4. 주문내역")
    orders = await client.get_orders(market="KR")
    if "korea" in orders:
        order_list = orders["korea"]
        print(f"   오늘 주문: {len(order_list)}건")
    
    # 5. 실전 거래 테스트 (삼성전자 1주 매수 → 10초 후 매도)
    print("\n5. 실전 거래 테스트")
    print("⚠️  주의: 실제 돈으로 거래합니다!")
    
    try:
        # 현재가 확인
        price_data = await client.get_price("005930")
        current_price = int(price_data.get('stck_prpr', 0))
        print(f"   📈 삼성전자 현재가: {current_price:,}원")
        
        # 매수 주문 (시장가 1주)
        print("   💰 매수 주문 실행...")
        buy_result = await client.place_order(
            code="005930",
            order_type="buy", 
            quantity=1,
            price=0,  # 시장가
            order_div="03",  # 조건부지정가
            exchange="SOR"   # 스마트라우팅
        )
        
        if buy_result:
            order_no = buy_result.get('ODNO', '')
            print(f"   ✅ 매수 주문 성공: 주문번호 {order_no}")
            
            # 10초 대기
            print("   ⏳ 10초 대기 중...")
            await asyncio.sleep(10)
            
            # 매도 주문 (시장가 1주)
            print("   💸 매도 주문 실행...")
            sell_result = await client.place_order(
                code="005930",
                order_type="sell",
                quantity=1, 
                price=0,  # 시장가
                order_div="03",  # 조건부지정가
                exchange="SOR"   # 스마트라우팅
            )
            
            if sell_result:
                sell_order_no = sell_result.get('ODNO', '')
                print(f"   ✅ 매도 주문 성공: 주문번호 {sell_order_no}")
            else:
                print("   ❌ 매도 주문 실패")
        else:
            print("   ❌ 매수 주문 실패")
            
    except Exception as e:
        print(f"   ❌ 거래 실행 중 오류: {e}")
    
    # 6. Rate Limit 상태
    print("\n6. Rate Limit")
    print(f"   남은 호출: {limiter.get_remaining_calls()}/{limiter.max_calls}")
    
    # 리소스 정리
    await client.close()


if __name__ == "__main__":
    print("🚨 실전 거래 테스트가 포함되어 있습니다!")
    print("삼성전자 1주를 실제 매수 후 10초 뒤 매도합니다.")
    response = input("계속하시겠습니까? (y/N): ")
    
    if response.lower() == 'y':
        asyncio.run(test())
    else:
        print("테스트가 취소되었습니다.")