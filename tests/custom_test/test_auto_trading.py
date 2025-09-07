#!/usr/bin/env python3
"""
자동매매 테스트 (매수/매도 로직 포함)
"""

import asyncio
import sys
import os
import time

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.bithumb_api import BithumbAPI
from src.strategy.simple_dashboard import SimpleDashboard

class AutoTradingTest:
    """자동매매 테스트 클래스"""
    
    def __init__(self):
        self.api = BithumbAPI()
        self.dashboard = SimpleDashboard()
        self.markets = []  # 전체 마켓 목록 (자동 수집)
        self.buy_orders = []  # 매수 주문 저장
        self.batch_size = 5   # 5개씩 배치 처리
        self.delay = 1.0      # 1초 대기
        
    async def check_market(self, market: str):
        """개별 종목 체크 및 매수 조건 확인"""
        try:
            # 현재가 조회
            ticker = self.api.get_ticker(market)
            if isinstance(ticker, list) and len(ticker) > 0:
                current_price = float(ticker[0]["trade_price"])
                change_rate = float(ticker[0]["signed_change_rate"]) * 100
            else:
                return
            
            # 거래량 데이터 조회
            candles = self.api.get_daily_candles(market, 7)
            if isinstance(candles, list) and len(candles) >= 2:
                data = candles
            else:
                return
            
            today_volume = float(data[0]["candle_acc_trade_volume"])
            avg_volume = sum(float(candle["candle_acc_trade_volume"]) for candle in data[1:]) / (len(data) - 1)
            volume_ratio = today_volume / avg_volume if avg_volume > 0 else 0
            
            # 매수 조건 체크
            conditions = {
                "거래량폭발": volume_ratio >= 3.0,  # 3배 이상
                "양봉": float(data[0]["trade_price"]) > float(data[0]["opening_price"]),
                "가격상승": change_rate > 0
            }
            
            # 매수 조건 만족 시 매수 실행
            if all(conditions.values()):
                await self.execute_buy_order(market, current_price, volume_ratio)
            
            # 대시보드에 출력
            self.dashboard.print_simple_status(
                market, current_price, change_rate, today_volume, conditions, volume_ratio
            )
            
        except Exception as e:
            self.dashboard.print_error(f"{market} 체크 실패: {e}")
    
    async def execute_buy_order(self, market: str, price: float, volume_ratio: float):
        """매수 주문 실행"""
        try:
            # 매수 금액 설정 (테스트용으로 5천원)
            buy_amount = 5000
            buy_volume = buy_amount / price
            
            # 최소 수량 체크 (테스트 파일과 동일)
            min_volume = 0.0001
            if buy_volume < min_volume:
                buy_volume = min_volume
                buy_amount = int(buy_volume * price)
            
            # 가격을 정수로 변환 (테스트 파일과 동일)
            buy_price = int(price)
            
            print(f"\n🚨 {market} 매수 신호! 거래량 {volume_ratio:.1f}배 폭발!")
            print(f"   매수 금액: {buy_amount:,}원")
            print(f"   매수 수량: {buy_volume:.8f}")
            print(f"   매수 가격: {buy_price:,}원")
            
            # 실제 매수 주문 실행
            order_result = self.api.place_order(
                market=market,
                side="bid",  # 매수
                order_type="limit",
                price=buy_price,  # 정수 가격 사용
                volume=buy_volume
            )
            
            if order_result.get("status") == "success":
                self.dashboard.print_success(f"✅ {market} 매수 주문 성공!")
                
                # 매수 주문 정보 저장
                self.buy_orders.append({
                    'market': market,
                    'volume': buy_volume,
                    'price': price,
                    'timestamp': time.time(),
                    'order_id': order_result.get('data', {}).get('uuid', 'unknown')
                })
                
            else:
                self.dashboard.print_error(f"❌ {market} 매수 주문 실패: {order_result}")
                
        except Exception as e:
            self.dashboard.print_error(f"❌ {market} 매수 주문 오류: {e}")
    
    async def check_sell_conditions(self):
        """매도 조건 체크"""
        if not self.buy_orders:
            return
        
        for order in self.buy_orders[:]:  # 복사본으로 순회
            try:
                # 현재가 조회
                ticker = self.api.get_ticker(order['market'])
                if isinstance(ticker, list) and len(ticker) > 0:
                    current_price = float(ticker[0]["trade_price"])
                else:
                    continue
                
                # 가격 변동률 계산
                price_change = (current_price - order['price']) / order['price'] * 100
                
                # 매도 조건 체크 (테스트용으로 더 민감하게 설정)
                if price_change >= 2.0:  # 2% 이상 상승 시 매도
                    await self.execute_sell_order(order, current_price, "익절")
                elif price_change <= -1.0:  # 1% 이상 하락 시 매도
                    await self.execute_sell_order(order, current_price, "손절")
                    
            except Exception as e:
                self.dashboard.print_error(f"❌ {order['market']} 매도 조건 체크 실패: {e}")
    
    async def execute_sell_order(self, order: dict, current_price: float, reason: str):
        """매도 주문 실행"""
        try:
            print(f"\n💰 {order['market']} 매도 신호! ({reason})")
            print(f"   매도 수량: {order['volume']:.8f}")
            print(f"   매도 가격: {current_price:,}원")
            print(f"   수익률: {((current_price - order['price']) / order['price'] * 100):+.2f}%")
            
            # 실제 매도 주문 실행
            sell_result = self.api.place_order(
                market=order['market'],
                side="ask",  # 매도
                order_type="limit",
                price=current_price,
                volume=order['volume']
            )
            
            if sell_result.get("status") == "success":
                self.dashboard.print_success(f"✅ {order['market']} 매도 주문 성공! ({reason})")
                
                # 매수 주문에서 제거
                self.buy_orders.remove(order)
                
            else:
                self.dashboard.print_error(f"❌ {order['market']} 매도 주문 실패: {sell_result}")
                
        except Exception as e:
            self.dashboard.print_error(f"❌ {order['market']} 매도 주문 오류: {e}")
    
    async def initialize(self):
        """초기화 및 전체 마켓 목록 수집"""
        print("🚀 자동매매 시스템 초기화 중...")
        
        try:
            # 전체 마켓 목록 조회
            response = self.api.get_market_list()
            
            if isinstance(response, list):
                markets = []
                for market_data in response:
                    market_code = market_data.get("market")
                    if market_code and market_code.startswith("KRW-"):
                        markets.append(market_code)
                self.markets = markets
            elif isinstance(response, dict) and "data" in response:
                markets = []
                for market_data in response["data"]:
                    market_code = market_data.get("market")
                    if market_code and market_code.startswith("KRW-"):
                        markets.append(market_code)
                self.markets = markets
            else:
                # 기본 종목 사용
                self.markets = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-DOGE"]
            
            print(f"✅ {len(self.markets)}개 종목 발견!")
            print(f"   처음 10개: {self.markets[:10]}")
            return True
            
        except Exception as e:
            print(f"❌ 초기화 실패: {e}")
            self.markets = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-DOGE"]
            return False

    async def run_auto_trading(self, cycles: int = 3):
        """자동매매 실행 (전체 종목 배치 처리)"""
        # 초기화
        if not await self.initialize():
            print("❌ 초기화 실패로 종료합니다.")
            return
        
        self.dashboard.clear_screen()
        self.dashboard.print_header(f"자동매매 시스템 - {len(self.markets)}개 종목")
        
        total_batches = (len(self.markets) + self.batch_size - 1) // self.batch_size
        
        for cycle in range(1, cycles + 1):
            print(f"\n🔄 사이클 {cycle}/{cycles} 시작! ({time.strftime('%H:%M:%S')})")
            print(f"📊 전체 {len(self.markets)}개 종목을 {total_batches}개 배치로 처리")
            print("=" * 60)
            
            # 전체 종목을 배치로 순차 처리
            for i in range(0, len(self.markets), self.batch_size):
                batch = self.markets[i:i + self.batch_size]
                batch_num = i // self.batch_size + 1
                
                print(f"\n📦 배치 {batch_num}/{total_batches} 처리 중... ({len(batch)}개 종목)")
                print(f"   종목들: {batch}")
                
                # 배치 내 각 종목 체크
                for market in batch:
                    await self.check_market(market)
                    await asyncio.sleep(0.3)  # 0.3초 대기
                
                # 매도 조건 체크
                await self.check_sell_conditions()
                
                print(f"✅ 배치 {batch_num} 완료!")
                
                # 다음 배치까지 대기 (마지막 배치가 아닌 경우)
                if i + self.batch_size < len(self.markets):
                    print(f"⏳ 다음 배치까지 {self.delay}초 대기...")
                    await asyncio.sleep(self.delay)
            
            # 현재 포지션 현황
            if self.buy_orders:
                print(f"\n📊 현재 포지션 ({len(self.buy_orders)}개):")
                for order in self.buy_orders:
                    print(f"   {order['market']}: {order['volume']:.8f} @ {order['price']:,}원")
            else:
                print(f"\n📊 현재 포지션: 없음")
            
            print(f"\n✅ 사이클 {cycle} 완료!")
            
            if cycle < cycles:
                print("⏳ 다음 사이클까지 5초 대기...")
                await asyncio.sleep(5)
        
        # 최종 통계
        print(f"\n📊 최종 통계")
        self.dashboard.print_statistics()

async def main():
    """메인 함수"""
    trader = AutoTradingTest()
    await trader.run_auto_trading(cycles=3)

if __name__ == "__main__":
    asyncio.run(main())
