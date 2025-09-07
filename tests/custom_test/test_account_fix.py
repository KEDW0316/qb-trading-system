#!/usr/bin/env python3
"""
수정된 계좌 정보 처리 테스트
"""

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.bithumb_api import BithumbAPI
from src.strategy.simple_dashboard import SimpleDashboard

async def test_account_processing():
    """수정된 계좌 정보 처리 테스트"""
    print("🔍 수정된 계좌 정보 처리 테스트 시작...")
    
    api = BithumbAPI()
    dashboard = SimpleDashboard()
    
    # 계좌 정보 조회
    print("\n1. 계좌 정보 조회:")
    account_info = api.get_account_info()
    print(f"   응답 타입: {type(account_info)}")
    print(f"   데이터 개수: {len(account_info) if isinstance(account_info, list) else 'N/A'}")
    
    if not account_info or not isinstance(account_info, list):
        print("❌ 계좌 정보를 가져올 수 없습니다.")
        return
    
    # 보유 중인 코인들 체크
    print("\n2. 보유 중인 코인들 체크:")
    for coin_data in account_info:
        market = f"KRW-{coin_data['currency']}"
        if coin_data['currency'] == 'KRW':  # 원화는 제외
            continue
        
        # 보유 수량이 있는 경우만 체크
        balance = float(coin_data['balance'])
        if balance <= 0:
            continue
        
        print(f"   🪙 {coin_data['currency']}: {balance:.8f} (평균: {float(coin_data['avg_buy_price']):,.0f}원)")
        
        # 현재가 조회 테스트
        try:
            ticker = api.get_ticker(market)
            if isinstance(ticker, list) and len(ticker) > 0:
                current_price = float(ticker[0]["trade_price"])
                avg_buy_price = float(coin_data['avg_buy_price'])
                
                if avg_buy_price > 0:
                    profit_rate = (current_price - avg_buy_price) / avg_buy_price * 100
                    print(f"      현재가: {current_price:,}원, 수익률: {profit_rate:+.2f}%")
                else:
                    print(f"      현재가: {current_price:,}원, 평균 매수가 없음")
            else:
                print(f"      현재가 조회 실패")
        except Exception as e:
            print(f"      현재가 조회 오류: {e}")
    
    print("\n✅ 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(test_account_processing())
