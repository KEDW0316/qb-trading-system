#!/usr/bin/env python3
"""
5,500원 이상 자산 필터 테스트
"""

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.bithumb_api import BithumbAPI
from src.strategy.simple_dashboard import SimpleDashboard

async def test_minimum_value_filter():
    """5,500원 이상 자산 필터 테스트"""
    print("🔍 5,500원 이상 자산 필터 테스트 시작...")
    
    api = BithumbAPI()
    dashboard = SimpleDashboard()
    
    # 계좌 정보 조회
    account_info = api.get_account_info()
    if not account_info or not isinstance(account_info, list):
        print("❌ 계좌 정보를 가져올 수 없습니다.")
        return
    
    print(f"\n📊 전체 보유 자산: {len(account_info)}개")
    
    # 5,500원 이상 자산만 필터링
    filtered_assets = []
    total_value = 0
    
    for coin_data in account_info:
        if coin_data['currency'] == 'KRW':
            krw_balance = float(coin_data['balance'])
            if krw_balance >= 5500:
                filtered_assets.append({
                    'currency': coin_data['currency'],
                    'balance': krw_balance,
                    'value': krw_balance,
                    'type': 'KRW'
                })
                total_value += krw_balance
        else:
            balance = float(coin_data['balance'])
            if balance > 0:
                market = f"KRW-{coin_data['currency']}"
                avg_price = float(coin_data['avg_buy_price'])
                
                # 현재가 조회
                try:
                    ticker = api.get_ticker(market)
                    if isinstance(ticker, list) and len(ticker) > 0:
                        current_price = float(ticker[0]["trade_price"])
                        asset_value = current_price * balance
                        
                        if asset_value >= 5500:
                            profit_rate = 0
                            if avg_price > 0:
                                profit_rate = (current_price - avg_price) / avg_price * 100
                            
                            filtered_assets.append({
                                'currency': coin_data['currency'],
                                'balance': balance,
                                'current_price': current_price,
                                'avg_price': avg_price,
                                'value': asset_value,
                                'profit_rate': profit_rate,
                                'type': 'CRYPTO'
                            })
                            total_value += asset_value
                except:
                    # 현재가 조회 실패 시 평균 매수가로 계산
                    if avg_price > 0:
                        asset_value = avg_price * balance
                        if asset_value >= 5500:
                            filtered_assets.append({
                                'currency': coin_data['currency'],
                                'balance': balance,
                                'avg_price': avg_price,
                                'value': asset_value,
                                'type': 'CRYPTO'
                            })
                            total_value += asset_value
    
    # 결과 출력
    print(f"\n✅ 5,500원 이상 자산: {len(filtered_assets)}개")
    print(f"💰 총 자산 가치: {total_value:,.0f}원")
    print("\n📋 상세 내역:")
    
    for asset in filtered_assets:
        if asset['type'] == 'KRW':
            print(f"   💰 {asset['currency']}: {asset['value']:,.0f}원")
        else:
            if 'current_price' in asset:
                print(f"   🪙 {asset['currency']}: {asset['balance']:.8f} (현재: {asset['current_price']:,.0f}원, 가치: {asset['value']:,.0f}원, 수익률: {asset['profit_rate']:+.2f}%)")
            else:
                print(f"   🪙 {asset['currency']}: {asset['balance']:.8f} (평균: {asset['avg_price']:,.0f}원, 가치: {asset['value']:,.0f}원)")
    
    print(f"\n🎯 매도 조건 체크 대상: {len([a for a in filtered_assets if a['type'] == 'CRYPTO' and 'profit_rate' in a])}개")

if __name__ == "__main__":
    asyncio.run(test_minimum_value_filter())
