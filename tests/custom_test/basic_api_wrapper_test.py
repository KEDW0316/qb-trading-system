#!/usr/bin/env python3
"""
KIS API 래퍼 함수 단순 테스트
"""

import asyncio
from dotenv import load_dotenv
from src.auth.kis_auth import KISAuthManager
from src.utils.rate_limiter import RateLimiter
from src.api.http_client import KISHttpClient

load_dotenv()


async def test():
    # 초기화
    import os
    env = os.getenv("KIS_ENV", "vps")  # .env에서 읽기, 기본값 vps
    auth = KISAuthManager(env=env)
    limiter = RateLimiter()
    client = KISHttpClient(auth, limiter)
    print(f"환경: {env}")
    
    # 1. 현재가
    print("\n1. 현재가")
    price = await client.get_current_price("005930")
    print(f"   삼성전자: {price.get('stck_prpr')}원")
    
    # 2. 일봉
    print("\n2. 일봉")
    chart = await client.get_daily_chart("005930", "20250815", "20250818")
    if chart:
        print(f"   최근: {chart[0].get('stck_bsop_date')} - {chart[0].get('stck_clpr')}원")
    
    # 3. 잔고
    print("\n3. 잔고")
    stocks, summary = await client.get_account_balance()
    print(f"   예수금: {summary.get('dnca_tot_amt')}원")
    print(f"   보유종목: {len(stocks)}개")
    
    # 4. 주문내역 (모의투자는 다른 API 필요)
    print("\n4. 주문내역")
    orders = await client.get_order_list()
    print(f"   오늘 주문: {len(orders)}건")
    # print("   모의투자 주문내역은 별도 API 필요")
    
    # 5. 실전 거래 테스트 (삼성전자 1주 매수 → 10초 후 매도)
    print("\n5. 실전 거래 테스트")
    print("⚠️  주의: 실제 돈으로 거래합니다!")
    
    try:
        # 현재가 확인
        price_data = await client.get_current_price("005930")
        current_price = int(price_data.get('stck_prpr', 0))
        print(f"   📈 삼성전자 현재가: {current_price:,}원")
        
        # 매수 주문 (시장가 1주) - NXT 야간거래 시도
        print("   💰 매수 주문 실행 (NXT 야간거래)...")
        buy_result = await client.place_order(
            stock_code="005930",
            order_type="buy", 
            quantity=1,
            price=0,  # 시장가
            order_div="03",  # 01: 시장가
            exchange="SOR"   # NXT: 야간거래
        )
        
        if buy_result:
            order_no = buy_result.get('ODNO', '')
            print(f"   ✅ 매수 주문 성공: 주문번호 {order_no}")
            
            # 10초 대기
            print("   ⏳ 10초 대기 중...")
            await asyncio.sleep(10)
            
            # 매도 주문 (시장가 1주) - NXT 야간거래
            print("   💸 매도 주문 실행 (NXT 야간거래)...")
            sell_result = await client.place_order(
                stock_code="005930",
                order_type="sell",
                quantity=1, 
                price=0,  # 시장가
                order_div="03",  # 01: 시장가
                exchange="SOR"   # NXT: 야간거래
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


if __name__ == "__main__":
    print("🚨 실전 거래 테스트가 포함되어 있습니다!")
    print("삼성전자 1주를 실제 매수 후 10초 뒤 매도합니다.")
    response = input("계속하시겠습니까? (y/N): ")
    
    if response.lower() == 'y':
        asyncio.run(test())
    else:
        print("테스트가 취소되었습니다.")