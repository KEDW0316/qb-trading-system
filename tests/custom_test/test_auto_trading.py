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
            # 매수 금액 설정 (10,000원)
            buy_amount = 10000
            buy_volume = round(buy_amount / price, 4)  # 소수점 4자리까지만
            
            # 최소 수량 체크 (테스트 파일과 동일)
            min_volume = 0.0001
            if buy_volume < min_volume:
                buy_volume = min_volume
                buy_amount = int(buy_volume * price)
            
            # 가격을 정수로 변환 (테스트 파일과 동일)
            buy_price = int(price)
            
            print(f"\n🚨 {market} 매수 신호! 거래량 {volume_ratio:.1f}배 폭발!")
            print(f"   매수 금액: {buy_amount:,}원")
            print(f"   매수 수량: {buy_volume:.4f}")
            print(f"   매수 가격: {buy_price:,}원")
            
            # 실제 매수 주문 실행 (지정가 - 현재가보다 1% 높게 설정하여 즉시 체결)
            buy_price = int(price * 1.01)  # 현재가보다 1% 높게
            
            order_result = self.api.place_order(
                market=market,
                side="bid",  # 매수
                order_type="limit",  # 지정가
                price=buy_price,  # 현재가보다 1% 높게
                volume=buy_volume
            )
            
            # 빗썸 API는 성공 시 uuid를 반환함
            if "uuid" in order_result:
                # 시장가 매수이므로 실제 체결가를 조회
                actual_price = price  # 현재가를 실제 매수가로 사용
                
                self.dashboard.print_success(f"✅ {market} 매수 주문 성공! (주문번호: {order_result['uuid']})")
                self.dashboard.print_success(f"   실제 매수가: {actual_price:,}원")
                
                # 매수 주문 정보 저장
                self.buy_orders.append({
                    'market': market,
                    'volume': buy_volume,
                    'price': actual_price,  # 실제 매수가 저장
                    'timestamp': time.time(),
                    'order_id': order_result['uuid']
                })
                
            else:
                self.dashboard.print_error(f"❌ {market} 매수 주문 실패: {order_result}")
                
        except Exception as e:
            self.dashboard.print_error(f"❌ {market} 매수 주문 오류: {e}")
    
    async def check_sell_conditions(self):
        """매도 조건 체크 - 실제 계좌 포지션 기반 (5,500원 이상 자산만)"""
        try:
            # 실제 계좌 잔고 조회
            account_info = self.api.get_account_info()
            if not account_info or not isinstance(account_info, list):
                print("❌ 계좌 정보를 가져올 수 없습니다.")
                return
            
            # 보유 중인 코인들 체크
            for coin_data in account_info:
                market = f"KRW-{coin_data['currency']}"
                if coin_data['currency'] == 'KRW':  # 원화는 제외
                    continue
                
                # 보유 수량이 있는 경우만 체크
                balance = float(coin_data['balance'])
                if balance <= 0:
                    continue
                
                # 현재가 조회
                ticker = self.api.get_ticker(market)
                if isinstance(ticker, list) and len(ticker) > 0:
                    current_price = float(ticker[0]["trade_price"])
                else:
                    continue
                
                # 평균 매수가 조회 (빗썸 API에서 제공)
                avg_buy_price = float(coin_data['avg_buy_price'])
                if avg_buy_price <= 0:
                    continue
                
                # 자산 가치 계산 (현재가 × 보유수량)
                asset_value = current_price * balance
                
                # 5,500원 미만 자산은 제외
                if asset_value < 5500:
                    continue
                
                # 수익률 계산
                profit_rate = (current_price - avg_buy_price) / avg_buy_price * 100
                
                print(f"🔍 {coin_data['currency']} 체크: {asset_value:,.0f}원 (수익률: {profit_rate:+.2f}%)")
                
                # 매도 조건 체크
                if profit_rate >= 5.0:  # 5% 이상 상승 시 익절
                    await self.execute_sell_order_from_account(
                        market, balance, current_price, avg_buy_price, "익절"
                    )
                elif profit_rate <= -7.0:  # 7% 이상 하락 시 손절
                    await self.execute_sell_order_from_account(
                        market, balance, current_price, avg_buy_price, "손절"
                    )
                    
        except Exception as e:
            self.dashboard.print_error(f"❌ 매도 조건 체크 실패: {e}")
    
    async def execute_sell_order_from_account(self, market: str, balance: float, current_price: float, avg_buy_price: float, reason: str):
        """계좌 정보 기반 매도 주문 실행"""
        try:
            print(f"\n💰 {market} 매도 신호! ({reason})")
            print(f"   보유 수량: {balance:.8f}")
            print(f"   평균 매수가: {avg_buy_price:,}원")
            print(f"   현재가: {current_price:,}원")
            print(f"   수익률: {((current_price - avg_buy_price) / avg_buy_price * 100):+.2f}%")
            
            # 전체 수량 매도
            sell_volume = balance
            
            # 매도 주문 실행 (지정가 - 현재가보다 1% 낮게 설정하여 즉시 체결)
            sell_price = int(current_price * 0.99)  # 현재가보다 1% 낮게
            
            sell_result = self.api.place_order(
                market=market,
                side="ask",  # 매도
                order_type="limit",  # 지정가
                price=sell_price,  # 현재가보다 1% 낮게
                volume=sell_volume
            )
            
            # 빗썸 API는 성공 시 uuid를 반환함
            if "uuid" in sell_result:
                self.dashboard.print_success(f"✅ {market} 매도 주문 성공! ({reason}) (주문번호: {sell_result['uuid']})")
                self.dashboard.print_success(f"   예상 수익: {((current_price - avg_buy_price) * sell_volume):+,.0f}원")
            else:
                self.dashboard.print_error(f"❌ {market} 매도 주문 실패: {sell_result}")
                
        except Exception as e:
            self.dashboard.print_error(f"❌ {market} 매도 주문 오류: {e}")
    
    async def execute_sell_order(self, order: dict, current_price: float, reason: str):
        """매도 주문 실행"""
        try:
            print(f"\n💰 {order['market']} 매도 신호! ({reason})")
            print(f"   매도 수량: {order['volume']:.4f}")
            print(f"   매도 가격: {current_price:,}원")
            print(f"   수익률: {((current_price - order['price']) / order['price'] * 100):+.2f}%")
            
            # 실제 매도 주문 실행 (지정가 - 현재가보다 1% 낮게 설정하여 즉시 체결)
            sell_price = int(current_price * 0.99)  # 현재가보다 1% 낮게
            
            sell_result = self.api.place_order(
                market=order['market'],
                side="ask",  # 매도
                order_type="limit",  # 지정가
                price=sell_price,  # 현재가보다 1% 낮게
                volume=order['volume']
            )
            
            # 빗썸 API는 성공 시 uuid를 반환함
            if "uuid" in sell_result:
                self.dashboard.print_success(f"✅ {order['market']} 매도 주문 성공! ({reason}) (주문번호: {sell_result['uuid']})")
                
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
    
    async def run_sell_monitoring(self, duration_minutes: int = 60):
        """매도 모니터링 실행 (계좌 기반)"""
        print("🚀 매도 모니터링 시작!")
        print(f"⏰ 모니터링 시간: {duration_minutes}분")
        print("=" * 60)
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        while time.time() < end_time:
            try:
                print(f"\n🔍 매도 조건 체크 중... ({time.strftime('%H:%M:%S')})")
                
                # 계좌 기반 매도 조건 체크
                await self.check_sell_conditions()
                
                # 현재 계좌 현황 출력
                await self.print_account_status()
                
                print("⏳ 30초 후 다시 체크...")
                await asyncio.sleep(30)  # 30초마다 체크
                
            except KeyboardInterrupt:
                print("\n⏹️ 사용자에 의해 중단되었습니다.")
                break
            except Exception as e:
                print(f"❌ 모니터링 오류: {e}")
                await asyncio.sleep(10)  # 오류 시 10초 대기
        
        print(f"\n✅ 매도 모니터링 완료!")
    
    async def print_account_status(self):
        """계좌 현황 출력 (5,500원 이상 자산만)"""
        try:
            account_info = self.api.get_account_info()
            if not account_info or not isinstance(account_info, list):
                print("📊 계좌 정보를 가져올 수 없습니다.")
                return
            
            print("\n📊 현재 계좌 현황 (5,500원 이상 자산):")
            total_value = 0
            checked_assets = 0
            
            for coin_data in account_info:
                if coin_data['currency'] == 'KRW':
                    krw_balance = float(coin_data['balance'])
                    print(f"   💰 원화: {krw_balance:,.0f}원")
                    total_value += krw_balance
                else:
                    balance = float(coin_data['balance'])
                    if balance > 0:
                        market = f"KRW-{coin_data['currency']}"
                        avg_price = float(coin_data['avg_buy_price'])
                        
                        # 현재가 조회하여 자산 가치 계산
                        try:
                            ticker = self.api.get_ticker(market)
                            if isinstance(ticker, list) and len(ticker) > 0:
                                current_price = float(ticker[0]["trade_price"])
                                asset_value = current_price * balance
                                
                                if asset_value >= 5500:  # 5,500원 이상만 표시
                                    profit_rate = 0
                                    if avg_price > 0:
                                        profit_rate = (current_price - avg_price) / avg_price * 100
                                    
                                    print(f"   🪙 {coin_data['currency']}: {balance:.8f} (현재: {current_price:,.0f}원, 가치: {asset_value:,.0f}원, 수익률: {profit_rate:+.2f}%)")
                                    total_value += asset_value
                                    checked_assets += 1
                        except:
                            # 현재가 조회 실패 시 평균 매수가로 계산
                            if avg_price > 0:
                                asset_value = avg_price * balance
                                if asset_value >= 5500:
                                    print(f"   🪙 {coin_data['currency']}: {balance:.8f} (평균: {avg_price:,.0f}원, 가치: {asset_value:,.0f}원)")
                                    total_value += asset_value
                                    checked_assets += 1
            
            print(f"\n📈 총 자산 가치: {total_value:,.0f}원 (체크 대상: {checked_assets}개 자산)")
                        
        except Exception as e:
            print(f"❌ 계좌 현황 조회 실패: {e}")

async def main():
    """메인 함수"""
    trader = AutoTradingTest()
    
    print("🎯 자동매매 시스템 선택:")
    print("1. 매수 모니터링 (새로운 매수 기회 찾기)")
    print("2. 매도 모니터링 (기존 포지션 관리)")
    print("3. 통합 모니터링 (매수 + 매도)")
    
    try:
        choice = input("\n선택하세요 (1/2/3): ").strip()
        
        if choice == "1":
            print("\n🚀 매수 모니터링 시작!")
            await trader.run_auto_trading(cycles=3)
        elif choice == "2":
            print("\n🚀 매도 모니터링 시작!")
            duration = input("모니터링 시간(분)을 입력하세요 (기본: 60): ").strip()
            duration = int(duration) if duration.isdigit() else 60
            await trader.run_sell_monitoring(duration_minutes=duration)
        elif choice == "3":
            print("\n🚀 통합 모니터링 시작!")
            # 매수와 매도를 동시에 실행
            import asyncio
            tasks = [
                trader.run_auto_trading(cycles=10),  # 매수 모니터링
                trader.run_sell_monitoring(duration_minutes=120)  # 매도 모니터링
            ]
            await asyncio.gather(*tasks)
        else:
            print("❌ 잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n⏹️ 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())
