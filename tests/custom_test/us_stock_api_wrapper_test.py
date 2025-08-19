#!/usr/bin/env python3
"""
KIS API 미국 주식 래퍼 함수 테스트
실전 거래 테스트 포함 (5만원 이하 저가 주식)
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
    env = os.getenv("KIS_ENV", "prod")  # 실전투자 환경 (prod)
    auth = KISAuthManager(env=env)
    limiter = RateLimiter()
    client = KISHttpClient(auth, limiter)
    print(f"환경: {env} (실전투자)")
    
    # 테스트용 저가 주식 선택
    # FORD (F) - 포드 자동차: 약 $10-12 (14,000원~17,000원)
    # SIRI - 시리우스 XM: 약 $3-4 (4,200원~5,600원)
    # NIO - 니오: 약 $4-6 (5,600원~8,400원)
    test_symbol = "F"  # 포드 자동차 (안정적인 저가주)
    
    print(f"\n테스트 종목: {test_symbol} (Ford Motor Company)")
    print("=" * 50)
    
    # 1. 미국 주식 현재가
    print("\n1. 미국 주식 현재가")
    try:
        price_data = await client.get_us_current_price(test_symbol, "NYSE")
        
        # API 응답 디버깅
        print(f"   [DEBUG] API 응답: {price_data}")
        
        # 'last' 필드 안전하게 처리
        last_price_str = price_data.get('last', '0')
        if last_price_str and last_price_str != '':
            current_price = float(last_price_str)
        else:
            # 빈 값일 경우 대체 필드 시도
            current_price = float(price_data.get('base', 0))  # 전일 종가
            print(f"   ⚠️  현재가 없음, 전일 종가 사용: ${current_price}")
        
        print(f"   {test_symbol} 현재가: ${current_price}")
        print(f"   원화 환산 (1,400원): {current_price * 1400:,.0f}원")
        print(f"   전일 종가: ${price_data.get('base', 'N/A')}")
        print(f"   등락률: {price_data.get('rate', 'N/A')}%")
        print(f"   거래량: {price_data.get('tvol', 'N/A')}")
    except Exception as e:
        print(f"   ❌ 현재가 조회 실패: {e}")
        current_price = 10.0  # Ford 예상 가격으로 기본값 설정
    
    # 2. 미국 주식 일봉 차트
    print("\n2. 미국 주식 일봉 차트")
    try:
        chart_data, summary = await client.get_us_daily_chart(
            test_symbol, 
            start_date="20250801",
            end_date="20250818",
            period="D",
            exchange="NYSE"
        )
        if chart_data:
            print(f"   차트 데이터: {len(chart_data)}개")
            latest = chart_data[0] if chart_data else {}
            print(f"   최근 거래일: {latest.get('xymd', 'N/A')}")
            print(f"   종가: ${latest.get('clos', 'N/A')}")
            print(f"   거래량: {latest.get('tvol', 'N/A')}")
    except Exception as e:
        print(f"   ❌ 차트 조회 실패: {e}")
    
    # 3. 미국 주식 잔고
    print("\n3. 미국 주식 계좌 잔고")
    try:
        stocks, summary = await client.get_us_account_balance()
        print(f"   보유 미국 주식: {len(stocks)}종목")
        print(f"   외화 예수금: ${summary.get('frcr_dncl_amt_2', 'N/A')}")
        print(f"   원화 예수금: {summary.get('tot_dncl_amt', 'N/A')}원")
        
        # 보유 종목 중 테스트 종목 확인
        for stock in stocks:
            if stock.get('ovrs_pdno') == test_symbol:
                print(f"   📌 {test_symbol} 보유수량: {stock.get('ovrs_cblc_qty')}주")
    except Exception as e:
        print(f"   ❌ 잔고 조회 실패: {e}")
    
    # 4. 통합 메서드 테스트
    print("\n4. 통합 메서드 테스트")
    try:
        # 자동 시장 구분 테스트
        unified_price = await client.get_price(test_symbol, market="US")
        last_str = unified_price.get('last', '0')
        if last_str and last_str != '':
            print(f"   통합 메서드 현재가: ${float(last_str)}")
        else:
            print(f"   통합 메서드 전일종가: ${unified_price.get('base', 'N/A')}")
    except Exception as e:
        print(f"   ❌ 통합 메서드 실패: {e}")
    
    # 5. 실전 거래 테스트 (미국 주식 1주 매수 → 10초 후 매도)
    print("\n5. 실전 거래 테스트")
    print("⚠️  주의: 실제 돈으로 거래합니다!")
    print(f"   종목: {test_symbol} (Ford)")
    print(f"   예상 매수금액: 약 ${current_price:.2f} (₩{current_price * 1400:,.0f})")
    
    try:
        # 매수 주문 (지정가 1주)
        # 미국 주식은 시장가 주문이 제한적이므로 현재가 근처 지정가 사용
        buy_price = round(current_price * 1.01, 2)  # 현재가보다 1% 높은 가격
        print(f"\n   💰 매수 주문 실행...")
        print(f"      - 수량: 1주")
        print(f"      - 지정가: ${buy_price}")
        
        buy_result = await client.place_us_order(
            symbol=test_symbol,
            order_type="buy",
            quantity=1,
            price=buy_price,  # 지정가
            order_div="00",   # 00: 지정가
            exchange="NYSE"
        )
        
        if buy_result:
            buy_order_no = buy_result.get('ODNO', '')
            print(f"   ✅ 매수 주문 성공!")
            print(f"      - 주문번호: {buy_order_no}")
            print(f"      - 주문시간: {buy_result.get('ORD_TMD', '')}")
            
            # 10초 대기
            print("\n   ⏳ 10초 대기 중...")
            await asyncio.sleep(10)
            
            # 매도 주문 (지정가 1주)
            sell_price = round(current_price * 0.99, 2)  # 현재가보다 1% 낮은 가격
            print(f"\n   💸 매도 주문 실행...")
            print(f"      - 수량: 1주")
            print(f"      - 지정가: ${sell_price}")
            
            sell_result = await client.place_us_order(
                symbol=test_symbol,
                order_type="sell",
                quantity=1,
                price=sell_price,  # 지정가
                order_div="00",    # 00: 지정가
                exchange="NYSE"
            )
            
            if sell_result:
                sell_order_no = sell_result.get('ODNO', '')
                print(f"   ✅ 매도 주문 성공!")
                print(f"      - 주문번호: {sell_order_no}")
                print(f"      - 주문시간: {sell_result.get('ORD_TMD', '')}")
                
                # 주문 취소 테스트 (선택사항)
                print("\n   🔄 매도 주문 취소 테스트...")
                cancel_confirm = input("   매도 주문을 취소하시겠습니까? (y/N): ")
                if cancel_confirm.lower() == 'y':
                    cancel_result = await client.cancel_us_order(
                        order_no=sell_order_no,
                        quantity=0,  # 전량 취소
                        exchange="NYSE"
                    )
                    if cancel_result:
                        print(f"   ✅ 주문 취소 성공!")
                    else:
                        print(f"   ❌ 주문 취소 실패")
            else:
                print("   ❌ 매도 주문 실패")
                print(f"      오류: {sell_result}")
        else:
            print("   ❌ 매수 주문 실패")
            print(f"      오류: {buy_result}")
            
    except Exception as e:
        print(f"   ❌ 거래 실행 중 오류: {e}")
    
    # 6. Rate Limit 상태
    print("\n6. Rate Limit 상태")
    print(f"   남은 호출: {limiter.get_remaining_calls()}/{limiter.max_calls}")
    print(f"   다음 리셋: {limiter.get_time_until_reset():.1f}초 후")


if __name__ == "__main__":
    print("=" * 60)
    print("🚨 미국 주식 실전 거래 테스트")
    print("=" * 60)
    print("📌 테스트 종목: F (Ford Motor Company)")
    print("📌 예상 금액: 약 $10-12 (14,000원~17,000원)")
    print("📌 거래 내용: 1주 매수 → 10초 대기 → 1주 매도")
    print("=" * 60)
    print("\n⚠️  경고: 실제 돈으로 거래가 실행됩니다!")
    print("⚠️  미국 주식 거래 가능 시간인지 확인하세요!")
    print("    - 한국시간 23:30 ~ 06:00 (서머타임 22:30 ~ 05:00)")
    print("=" * 60)
    
    response = input("\n계속하시겠습니까? (y/N): ")
    
    if response.lower() == 'y':
        print("\n테스트를 시작합니다...")
        asyncio.run(test())
        print("\n테스트가 완료되었습니다.")
    else:
        print("테스트가 취소되었습니다.")