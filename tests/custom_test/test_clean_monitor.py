#!/usr/bin/env python3
"""
깔끔한 모니터링 테스트
"""

import asyncio
import sys
import os
import time

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.bithumb_api import BithumbAPI
from src.strategy.simple_dashboard import SimpleDashboard

class CleanMonitor:
    """깔끔한 모니터링 클래스"""
    
    def __init__(self):
        self.api = BithumbAPI()
        self.dashboard = SimpleDashboard()
        self.markets = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-DOGE"]
        
    async def check_market(self, market: str):
        """개별 종목 체크"""
        try:
            print(f"🔍 {market} 체크 중...")
            
            # 현재가 조회
            ticker = self.api.get_ticker(market)
            print(f"   Ticker 응답: {type(ticker)}")
            
            if isinstance(ticker, list) and len(ticker) > 0:
                current_price = float(ticker[0]["trade_price"])
                change_rate = float(ticker[0]["signed_change_rate"]) * 100
                print(f"   현재가: {current_price:,}원, 변동률: {change_rate:+.2f}%")
            elif isinstance(ticker, dict) and "data" in ticker and len(ticker["data"]) > 0:
                current_price = float(ticker["data"][0]["trade_price"])
                change_rate = float(ticker["data"][0]["signed_change_rate"]) * 100
                print(f"   현재가: {current_price:,}원, 변동률: {change_rate:+.2f}%")
            else:
                print(f"   ❌ 티커 데이터 없음: {ticker}")
                return
            
            # 거래량 데이터 조회
            candles = self.api.get_daily_candles(market, 7)
            print(f"   Candles 응답: {type(candles)}")
            
            if isinstance(candles, list) and len(candles) >= 2:
                data = candles
            elif isinstance(candles, dict) and "data" in candles and len(candles["data"]) >= 2:
                data = candles["data"]
            else:
                print(f"   ❌ 캔들 데이터 없음: {candles}")
                return
            
            today_volume = float(data[0]["candle_acc_trade_volume"])
            avg_volume = sum(float(candle["candle_acc_trade_volume"]) for candle in data[1:]) / (len(data) - 1)
            volume_ratio = today_volume / avg_volume if avg_volume > 0 else 0
            
            print(f"   거래량: {today_volume:,} (평균 대비 {volume_ratio:.1f}배)")
            
            # 간단한 조건 체크
            conditions = {
                "거래량폭발": volume_ratio >= 3.0,  # 3배 이상
                "양봉": float(data[0]["trade_price"]) > float(data[0]["opening_price"]),
                "가격상승": change_rate > 0
            }
            
            print(f"   조건: {conditions}")
            
            # 대시보드에 출력
            self.dashboard.print_simple_status(
                market, current_price, change_rate, today_volume, conditions, volume_ratio
            )
            
        except Exception as e:
            print(f"   ❌ {market} 체크 실패: {e}")
            import traceback
            traceback.print_exc()
    
    async def run_monitoring(self, cycles: int = 3):
        """모니터링 실행"""
        self.dashboard.clear_screen()
        self.dashboard.print_header("깔끔한 모니터링 테스트")
        
        for cycle in range(1, cycles + 1):
            print(f"\n🔄 사이클 {cycle}/{cycles} 시작!")
            print("=" * 50)
            
            for market in self.markets:
                await self.check_market(market)
                await asyncio.sleep(0.5)  # 0.5초 대기
            
            print(f"\n✅ 사이클 {cycle} 완료!")
            
            if cycle < cycles:
                print("⏳ 다음 사이클까지 3초 대기...")
                await asyncio.sleep(3)
        
        # 최종 통계
        print(f"\n📊 최종 통계")
        self.dashboard.print_statistics()

async def main():
    """메인 함수"""
    monitor = CleanMonitor()
    await monitor.run_monitoring(cycles=2)

if __name__ == "__main__":
    asyncio.run(main())
