#!/usr/bin/env python3
"""
간단한 매수 테스트
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.bithumb_api import BithumbAPI

def test_simple_buy():
    """간단한 매수 테스트"""
    print("🚀 간단한 매수 테스트 시작!")
    
    try:
        # API 초기화
        api = BithumbAPI()
        
        # BTC 현재가 조회
        print("BTC 현재가 조회 중...")
        ticker = api.get_ticker("KRW-BTC")
        
        if isinstance(ticker, list) and len(ticker) > 0:
            current_price = float(ticker[0]["trade_price"])
            print(f"BTC 현재가: {current_price:,}원")
            
            # 50,000원으로 매수 (최소 주문 금액 확인)
            buy_amount = 50000
            buy_volume = round(buy_amount / current_price, 4)  # 소수점 4자리까지만
            buy_price = int(current_price)
            
            print(f"매수 금액: {buy_amount:,}원")
            print(f"매수 수량: {buy_volume:.4f}")
            print(f"매수 가격: {buy_price:,}원")
            
            # 매수 주문 실행 (지정가 - 현재가보다 1% 높게)
            buy_price = int(current_price * 1.01)  # 현재가보다 1% 높게
            print("매수 주문 실행 중...")
            buy_order = api.place_order(
                market="KRW-BTC",
                side="bid",
                order_type="limit",  # 지정가
                price=buy_price,  # 현재가보다 1% 높게
                volume=buy_volume
            )
            
            print(f"매수 주문 결과: {buy_order}")
            
            # 빗썸 API는 성공 시 uuid를 반환함
            if "uuid" in buy_order:
                print("✅ 매수 주문 성공!")
                print(f"   주문번호: {buy_order['uuid']}")
            else:
                print(f"❌ 매수 주문 실패: {buy_order}")
                
        else:
            print("❌ 현재가 조회 실패")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_buy()
