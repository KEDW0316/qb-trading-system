import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from src.api.bithumb_api import BithumbAPI
from src.strategy.simple_dashboard import SimpleDashboard

# 로깅 설정 (간소화)
logging.basicConfig(level=logging.WARNING)  # WARNING으로 변경하여 불필요한 로그 제거
logger = logging.getLogger(__name__)

# urllib3 DEBUG 로그 비활성화 (API 호출 상세 로그 제거)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("urllib3.util.retry").setLevel(logging.WARNING)

@dataclass
class MarketCondition:
    """종목별 시장 조건 데이터"""
    market: str
    is_sideways: bool
    sideways_range: Tuple[float, float]  # (최저가, 최고가)
    current_price: float
    avg_volume_30d: float
    today_volume: float
    volume_multiplier: float
    is_volume_explosion: bool
    is_bullish_candle: bool
    timestamp: datetime

class BatchVolumeMonitor:
    """배치 처리 방식 거래량 폭발 모니터링 클래스"""
    
    def __init__(self, api: BithumbAPI):
        self.api = api
        self.markets = []
        self.batch_size = 5   # 1초에 5개씩 처리 (API 부하 감소)
        self.delay = 1.0      # 1초 대기
        self.monitoring_interval = 60  # 1분마다 전체 스캔
        
        # 모니터링 결과 저장
        self.market_conditions = {}
        self.volume_explosions = []
        
        # 대시보드 초기화
        self.dashboard = SimpleDashboard()
        
    async def initialize(self):
        """초기화 및 모든 종목 목록 수집"""
        logger.info("🚀 Batch Volume Monitor 초기화 시작...")
        
        try:
            # 1. 모든 마켓 목록 조회
            self.markets = await self.get_all_markets()
            logger.info(f"📊 총 {len(self.markets)}개 종목 발견")
            
            # 2. 초기 데이터 수집 (선택적)
            logger.info("📈 초기 데이터 수집 중...")
            await self.collect_initial_data()
            
            logger.info("✅ 초기화 완료!")
            return True
            
        except Exception as e:
            logger.error(f"❌ 초기화 실패: {e}")
            return False
    
    async def get_all_markets(self) -> List[str]:
        """거래 가능한 모든 마켓 목록 조회"""
        try:
            logger.info("🔍 마켓 목록 조회 중...")
            response = self.api.get_market_list()
            
            logger.info(f"📡 API 응답 타입: {type(response)}")
            logger.info(f"📡 API 응답 길이: {len(response) if hasattr(response, '__len__') else '길이 없음'}")
            
            # 응답이 리스트인 경우 직접 처리
            if isinstance(response, list):
                markets = []
                logger.info(f"📊 응답 데이터 개수: {len(response)}")
                
                # 처음 5개만 로그로 출력 (디버깅용)
                for i, market_data in enumerate(response[:5]):
                    logger.info(f"   [{i}] 마켓 데이터: {market_data}")
                
                # 전체 응답을 모두 처리
                for market_data in response:
                    market_code = market_data.get("market")
                    if market_code and market_code.startswith("KRW-"):
                        markets.append(market_code)
                
                logger.info(f"🇰🇷 KRW 마켓 {len(markets)}개 발견")
                if markets:
                    logger.info(f"   발견된 마켓들: {markets[:10]}...")  # 처음 10개만 출력
                return markets
            
            # 응답이 딕셔너리이고 "data" 키가 있는 경우
            elif isinstance(response, dict) and "data" in response:
                markets = []
                logger.info(f"📊 응답 데이터 개수: {len(response['data'])}")
                
                # 처음 5개만 로그로 출력 (디버깅용)
                for i, market_data in enumerate(response["data"][:5]):
                    logger.info(f"   [{i}] 마켓 데이터: {market_data}")
                
                # 전체 응답을 모두 처리
                for market_data in response["data"]:
                    market_code = market_data.get("market")
                    if market_code and market_code.startswith("KRW-"):
                        markets.append(market_code)
                
                logger.info(f"🇰🇷 KRW 마켓 {len(markets)}개 발견")
                if markets:
                    logger.info(f"   발견된 마켓들: {markets[:10]}...")
                return markets
            
            # 기타 경우
            else:
                logger.warning("⚠️ 마켓 목록 조회 실패, 기본 종목 사용")
                logger.warning(f"   응답 타입: {type(response)}")
                logger.warning(f"   응답 내용: {response}")
                return ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-ADA", "KRW-DOGE"]
                
        except Exception as e:
            logger.error(f"❌ 마켓 목록 조회 오류: {e}")
            import traceback
            logger.error(f"   상세 오류: {traceback.format_exc()}")
            return ["KRW-BTC", "KRW-ETH", "KRW-XRP"]
    
    async def collect_initial_data(self):
        """초기 데이터 수집 (선택적)"""
        # 여기서는 기본 정보만 수집하고, 실제 모니터링 시 상세 데이터 조회
        logger.info("📊 초기 데이터 수집 완료")
    
    async def start_monitoring(self):
        """모니터링 시작"""
        logger.info("🔍 배치 모니터링 시작!")
        logger.info(f"   배치 크기: {self.batch_size}개/초")
        logger.info(f"   전체 종목: {len(self.markets)}개")
        logger.info(f"   스캔 주기: {self.monitoring_interval}초")
        
        try:
            while True:
                start_time = time.time()
                
                # 전체 종목을 배치로 처리
                await self.process_all_markets()
                
                # 처리 시간 계산
                elapsed = time.time() - start_time
                logger.info(f"⏱️ 전체 스캔 완료: {elapsed:.1f}초 소요")
                
                # 다음 스캔까지 대기
                wait_time = max(0, self.monitoring_interval - elapsed)
                if wait_time > 0:
                    logger.info(f"⏳ 다음 스캔까지 {wait_time:.1f}초 대기...")
                    await asyncio.sleep(wait_time)
                    
        except KeyboardInterrupt:
            logger.info("🛑 모니터링 중단됨")
        except Exception as e:
            logger.error(f"❌ 모니터링 오류: {e}")
    
    async def start_continuous_monitoring(self):
        """연속 순환 모니터링 시작 (무한 루프)"""
        if not self.markets:
            self.dashboard.print_error("마켓 목록이 비어있습니다")
            return
        
        total_batches = (len(self.markets) + self.batch_size - 1) // self.batch_size
        self.dashboard.print_success(f"연속 모니터링 시작! ({len(self.markets)}개 종목, {total_batches}개 배치)")
        
        cycle_count = 0
        
        try:
            while True:  # 무한 루프
                cycle_start = time.time()
                cycle_count += 1
                
                # 대시보드 업데이트
                self.dashboard.clear_screen()
                self.dashboard.print_header(f"사이클 {cycle_count} - {time.strftime('%H:%M:%S')}")
                
                # 전체 마켓을 배치로 순차 처리
                for i in range(0, len(self.markets), self.batch_size):
                    batch = self.markets[i:i + self.batch_size]
                    batch_num = i // self.batch_size + 1
                    
                    # 배치 처리
                    await self.process_batch_simple(batch, batch_num, total_batches)
                    
                    # 매도 조건 체크 (매수한 종목들)
                    await self.check_sell_conditions()
                    
                    # 다음 배치까지 대기 (마지막 배치가 아닌 경우)
                    if i + self.batch_size < len(self.markets):
                        await asyncio.sleep(self.delay)
                
                cycle_time = time.time() - cycle_start
                self.dashboard.print_success(f"사이클 {cycle_count} 완료! ({cycle_time:.1f}초)")
                
                # 현재 포지션 현황 출력
                if hasattr(self, 'buy_orders') and self.buy_orders:
                    print(f"\n📊 현재 포지션 ({len(self.buy_orders)}개):")
                    for order in self.buy_orders:
                        print(f"   {order['market']}: {order['volume']:.8f} @ {order['price']:,}원")
                else:
                    print(f"\n📊 현재 포지션: 없음")
                
                # 다음 사이클 시작 전 잠시 대기
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            self.dashboard.print_warning("사용자에 의해 모니터링 중단됨")
        except Exception as e:
            self.dashboard.print_error(f"모니터링 중 오류 발생: {e}")
        finally:
            self.dashboard.print_success("연속 모니터링 종료")

    async def process_batch_simple(self, batch: List[str], batch_num: int, total_batches: int):
        """간단한 배치 처리 (대시보드용)"""
        print(f"📦 배치 {batch_num}/{total_batches} 처리 중... ({len(batch)}개 종목)")
        
        for market in batch:
            try:
                # 개별 종목 조건 체크
                result = await self.check_market_conditions_simple(market)
                self.market_conditions[market] = result
                
                # 거래량 폭발 감지 시
                if result.is_volume_explosion:
                    self.volume_explosions.append(result)
                    await self.handle_volume_explosion(result)
                
            except Exception as e:
                self.dashboard.print_error(f"{market} 실패: {e}")
        
        print(f"✅ 배치 {batch_num} 완료!")

    async def process_batch(self, batch: List[str]):
        """배치 단위로 종목들 처리"""
        logger.info(f"🔍 배치 처리 시작: {len(batch)}개 종목")
        
        # 개별 종목별 처리 (간소화)
        for i, market in enumerate(batch, 1):
            try:
                # 개별 종목 조건 체크
                result = await self.check_market_conditions(market)
                self.market_conditions[market] = result
                
                # 거래량 폭발 감지 시
                if result.is_volume_explosion:
                    self.volume_explosions.append(result)
                    await self.handle_volume_explosion(result)
                
            except Exception as e:
                logger.error(f"❌ {market} 실패: {e}")
        
        logger.info(f"✅ 배치 처리 완료: {len(batch)}개 종목")

    async def process_all_markets(self):
        """모든 종목을 배치로 처리 (1회성)"""
        if not self.markets:
            logger.warning("⚠️ 마켓 목록이 비어있습니다")
            return
        
        total_batches = (len(self.markets) + self.batch_size - 1) // self.batch_size
        logger.info(f"🔄 전체 {len(self.markets)}개 종목 배치 처리 시작...")
        
        for i in range(0, len(self.markets), self.batch_size):
            batch = self.markets[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            
            logger.info(f"📦 배치 {batch_num}/{total_batches} 처리 중... ({len(batch)}개 종목)")
            
            # 배치 처리
            await self.process_batch(batch)
            
            # 다음 배치까지 대기 (마지막 배치가 아닌 경우)
            if i + self.batch_size < len(self.markets):
                logger.info(f"⏳ 다음 배치까지 {self.delay}초 대기...")
                await asyncio.sleep(self.delay)
            else:
                logger.info("✅ 마지막 배치 완료!")
        
        logger.info("🎉 모든 배치 처리 완료!")
    
    async def check_market_conditions_simple(self, market: str) -> MarketCondition:
        """간단한 시장 조건 체크 (대시보드용)"""
        try:
            # 1. 현재가 조회
            current_price = await self.get_current_price(market)
            
            # 2. 거래량 데이터 조회
            avg_volume_30d, today_volume = await self.get_volume_data(market)
            
            # 3. 거래량 폭발 체크 (5배 이상)
            volume_multiplier = today_volume / avg_volume_30d if avg_volume_30d > 0 else 0
            is_volume_explosion = volume_multiplier >= 5.0
            
            # 4. 횡보 체크 (간단화)
            is_sideways = await self.check_sideways_market_simple(market)
            
            # 5. 양봉 체크
            is_bullish_candle = await self.check_bullish_candle(market)
            
            # 6. 매수 조건 종합
            buy_condition = is_sideways and is_volume_explosion and is_bullish_candle
            
            # 대시보드에 간단한 상태 출력
            conditions = {
                "횡보": is_sideways,
                "거래량폭발": is_volume_explosion,
                "양봉": is_bullish_candle
            }
            
            self.dashboard.print_simple_status(
                market, current_price, 0, today_volume, conditions, volume_multiplier
            )
            
            return MarketCondition(
                market=market,
                is_sideways=is_sideways,
                sideways_range=(0, 0),
                current_price=current_price,
                avg_volume_30d=avg_volume_30d,
                today_volume=today_volume,
                volume_multiplier=volume_multiplier,
                is_volume_explosion=is_volume_explosion,
                is_bullish_candle=is_bullish_candle,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.dashboard.print_error(f"{market} 조건 체크 실패: {e}")
            raise

    async def check_market_conditions(self, market: str) -> MarketCondition:
        """개별 종목의 시장 조건 체크"""
        try:
            # 1. 2개월 횡보 상태 체크
            is_sideways, sideways_range = await self.check_sideways_market(market)
            
            # 2. 현재가 조회
            current_price = await self.get_current_price(market)
            
            # 3. 거래량 데이터 조회
            avg_volume_30d, today_volume = await self.get_volume_data(market)
            
            # 4. 거래량 폭발 체크 (5배 이상)
            volume_multiplier = today_volume / avg_volume_30d if avg_volume_30d > 0 else 0
            is_volume_explosion = volume_multiplier >= 5.0
            
            # 5. 양봉 체크
            is_bullish_candle = await self.check_bullish_candle(market)
            
            # 6. 매수 조건 종합 및 간단한 출력
            buy_condition = is_sideways and is_volume_explosion and is_bullish_candle
            
            if buy_condition:
                logger.warning(f"🚨 {market}: 매수 조건 만족! 거래량 {volume_multiplier:.1f}배 폭발!")
            else:
                logger.info(f"⚠️ {market}: 매수 조건 불만족")
            
            return MarketCondition(
                market=market,
                is_sideways=is_sideways,
                sideways_range=sideways_range,
                current_price=current_price,
                avg_volume_30d=avg_volume_30d,
                today_volume=today_volume,
                volume_multiplier=volume_multiplier,
                is_volume_explosion=is_volume_explosion,
                is_bullish_candle=is_bullish_candle,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ {market} 조건 체크 실패: {e}")
            raise
    
    async def check_sideways_market_simple(self, market: str) -> bool:
        """간단한 횡보 체크 (대시보드용)"""
        try:
            # 30일 데이터로 간단히 체크
            candles = self.api.get_daily_candles(market, 30)
            
            if isinstance(candles, list) and len(candles) >= 7:
                data = candles
            elif isinstance(candles, dict) and "data" in candles and len(candles["data"]) >= 7:
                data = candles["data"]
            else:
                return False
            
            # 7일 전 가격 기준 ±10% 범위 체크
            reference_price = float(data[6]["trade_price"])
            current_price = float(data[0]["trade_price"])
            
            range_min = reference_price * 0.9
            range_max = reference_price * 1.1
            
            return range_min <= current_price <= range_max
            
        except Exception as e:
            return False

    async def check_sideways_market(self, market: str) -> Tuple[bool, Tuple[float, float]]:
        """2개월 횡보 시장 체크"""
        try:
            # 2개월 = 약 60일 (최대 200개까지 요청 가능)
            candles = self.api.get_daily_candles(market, 60)
            
            # API 응답 형태 확인 및 처리
            if isinstance(candles, list):
                # 리스트 형태로 응답이 온 경우
                if len(candles) < 30:  # 최소 30일은 필요
                    logger.warning(f"            ⚠️ {market}: 최소 30일 데이터 필요, 현재 {len(candles)}일")
                    return False, (0, 0)
                data_length = len(candles)
                data = candles
            elif isinstance(candles, dict) and "data" in candles:
                # 딕셔너리 형태로 응답이 온 경우
                if len(candles["data"]) < 30:
                    logger.warning(f"            ⚠️ {market}: 최소 30일 데이터 필요, 현재 {len(candles['data'])}일")
                    return False, (0, 0)
                data_length = len(candles["data"])
                data = candles["data"]
            else:
                logger.warning(f"            ⚠️ {market}: 예상치 못한 응답 형태: {type(candles)}")
                return False, (0, 0)
            
            # 데이터가 부족한 경우 적응형으로 처리
            if data_length < 60:
                # 30일 이상이면 30일 기준으로 횡보 체크
                if data_length >= 30:
                    reference_day = min(29, data_length - 1)  # 30일 전 또는 가능한 최대
                    reference_price = float(data[reference_day]["trade_price"])
                else:
                    logger.warning(f"⚠️ {market}: 30일 미만 데이터로 횡보 체크 불가")
                    return False, (0, 0)
            else:
                reference_day = 59  # 60일 전
                reference_price = float(data[59]["trade_price"])
            
            # 기준가 기준 ±10% 범위 계산
            range_min = reference_price * 0.9
            range_max = reference_price * 1.1
            
            # 현재가가 범위 내에 있는지 체크
            current_price = float(data[0]["trade_price"])
            is_sideways = range_min <= current_price <= range_max
            
            logger.info(f"            기준가 ({reference_day+1}일 전): {reference_price:,.0f}원")
            logger.info(f"            횡보 범위: {range_min:,.0f} ~ {range_max:,.0f}원 (±10%)")
            logger.info(f"            현재가: {current_price:,.0f}원")
            logger.info(f"            횡보 여부: {is_sideways}")
            
            return is_sideways, (range_min, range_max)
            
        except Exception as e:
            logger.error(f"❌ {market} 횡보 체크 실패: {e}")
            return False, (0, 0)
    
    async def get_current_price(self, market: str) -> float:
        """현재가 조회"""
        try:
            ticker = self.api.get_ticker(market)
            
            if "data" in ticker and len(ticker["data"]) > 0:
                return float(ticker["data"][0]["trade_price"])
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"❌ {market} 현재가 조회 실패: {e}")
            return 0.0
    
    async def get_volume_data(self, market: str) -> Tuple[float, float]:
        """거래량 데이터 조회 (30일 평균 + 오늘)"""
        try:
            # 30일 일봉 데이터
            candles = self.api.get_daily_candles(market, 30)
            
            # API 응답 형태 확인 및 처리
            if isinstance(candles, list):
                # 리스트 형태로 응답이 온 경우
                if len(candles) < 7:  # 최소 7일은 필요
                    logger.warning(f"            ⚠️ {market}: 최소 7일 데이터 필요, 현재 {len(candles)}일")
                    return 0.0, 0.0
                data_length = len(candles)
                data = candles
            elif isinstance(candles, dict) and "data" in candles:
                # 딕셔너리 형태로 응답이 온 경우
                if len(candles["data"]) < 7:
                    logger.warning(f"            ⚠️ {market}: 최소 7일 데이터 필요, 현재 {len(candles['data'])}일")
                    return 0.0, 0.0
                data_length = len(candles["data"])
                data = candles["data"]
            else:
                logger.warning(f"            ⚠️ {market}: 예상치 못한 응답 형태: {type(candles)}")
                return 0.0, 0.0
            
            logger.info(f"            📊 {market}: {data_length}일 데이터 사용 가능")
            
            # 오늘 거래량
            today_volume = float(data[0]["candle_acc_trade_volume"])
            
            # 평균 거래량 계산 (오늘 제외, 가능한 만큼)
            if data_length >= 30:
                # 30일 이상이면 30일 평균
                volumes = [float(candle["candle_acc_trade_volume"]) for candle in data[1:31]]
                period_name = "30일"
            else:
                # 7일 이상이면 가능한 만큼 평균
                volumes = [float(candle["candle_acc_trade_volume"]) for candle in data[1:data_length]]
                period_name = f"{data_length-1}일"
            
            avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
            
            # 상세 로깅 제거 (간소화)
            
            return avg_volume, today_volume
            
        except Exception as e:
            logger.error(f"❌ {market} 거래량 데이터 조회 실패: {e}")
            return 0.0, 0.0
    
    async def check_bullish_candle(self, market: str) -> bool:
        """양봉 체크 (시가 < 종가)"""
        try:
            candles = self.api.get_daily_candles(market, 1)
            
            # API 응답 형태 확인 및 처리
            if isinstance(candles, list):
                # 리스트 형태로 응답이 온 경우
                if len(candles) > 0:
                    candle = candles[0]
                    data_source = "리스트"
                else:
                    logger.warning(f"            ⚠️ {market}: 1일 데이터 부족, 응답: {candles}")
                    return False
            elif isinstance(candles, dict) and "data" in candles:
                # 딕셔너리 형태로 응답이 온 경우
                if len(candles["data"]) > 0:
                    candle = candles["data"][0]
                    data_source = "딕셔너리"
                else:
                    logger.warning(f"            ⚠️ {market}: 1일 데이터 부족, 응답: {candles}")
                    return False
            else:
                logger.warning(f"            ⚠️ {market}: 예상치 못한 응답 형태: {type(candles)}")
                return False
            
            opening_price = float(candle["opening_price"])
            closing_price = float(candle["trade_price"])
            
            is_bullish = closing_price > opening_price
            price_change = closing_price - opening_price
            price_change_pct = (price_change / opening_price) * 100
            
            # 상세 로깅 제거 (간소화)
            
            return is_bullish
                
        except Exception as e:
            logger.error(f"❌ {market} 양봉 체크 실패: {e}")
            return False
    
    async def handle_volume_explosion(self, condition: MarketCondition):
        """거래량 폭발 처리"""
        self.dashboard.print_warning(f"{condition.market}: 거래량 폭발 감지! ({condition.volume_multiplier:.1f}배)")
        
        # 매수 조건 체크
        if condition.is_sideways and condition.is_bullish_candle:
            self.dashboard.print_success(f"{condition.market}: 매수 조건 만족! 매수 주문 실행...")
            await self.execute_buy_order(condition)
        else:
            self.dashboard.print_warning(f"{condition.market}: 매수 조건 불만족")
    
    async def execute_buy_order(self, condition: MarketCondition):
        """매수 주문 실행"""
        try:
            # 매수 금액 설정 (예: 5만원)
            buy_amount = 50000
            buy_volume = buy_amount / condition.current_price
            
            # 매수 주문 실행
            order_result = self.api.place_order(
                market=condition.market,
                side="bid",  # 매수
                order_type="limit",
                price=condition.current_price,
                volume=buy_volume
            )
            
            if order_result.get("status") == "success":
                self.dashboard.print_success(f"✅ {condition.market} 매수 주문 성공! (수량: {buy_volume:.8f})")
                
                # 매수 주문 정보 저장
                self.buy_orders = getattr(self, 'buy_orders', [])
                self.buy_orders.append({
                    'market': condition.market,
                    'volume': buy_volume,
                    'price': condition.current_price,
                    'timestamp': datetime.now(),
                    'order_id': order_result.get('data', {}).get('uuid', 'unknown')
                })
                
            else:
                self.dashboard.print_error(f"❌ {condition.market} 매수 주문 실패: {order_result}")
                
        except Exception as e:
            self.dashboard.print_error(f"❌ {condition.market} 매수 주문 오류: {e}")
    
    async def check_sell_conditions(self):
        """매도 조건 체크"""
        if not hasattr(self, 'buy_orders') or not self.buy_orders:
            return
        
        for order in self.buy_orders[:]:  # 복사본으로 순회
            try:
                # 현재가 조회
                current_price = await self.get_current_price(order['market'])
                
                # 매도 조건 체크 (예: 5% 상승 또는 3% 하락)
                price_change = (current_price - order['price']) / order['price'] * 100
                
                if price_change >= 5.0:  # 5% 이상 상승 시 매도
                    await self.execute_sell_order(order, current_price, "익절")
                elif price_change <= -3.0:  # 3% 이상 하락 시 매도
                    await self.execute_sell_order(order, current_price, "손절")
                    
            except Exception as e:
                self.dashboard.print_error(f"❌ {order['market']} 매도 조건 체크 실패: {e}")
    
    async def execute_sell_order(self, order: dict, current_price: float, reason: str):
        """매도 주문 실행"""
        try:
            # 매도 주문 실행
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
    
    def get_summary(self) -> Dict:
        """모니터링 결과 요약"""
        total_markets = len(self.markets)
        checked_markets = len(self.market_conditions)
        volume_explosions = len(self.volume_explosions)
        
        return {
            "total_markets": total_markets,
            "checked_markets": checked_markets,
            "volume_explosions": volume_explosions,
            "last_update": datetime.now().isoformat(),
            "explosions": [
                {
                    "market": exp.market,
                    "multiplier": exp.volume_multiplier,
                    "timestamp": exp.timestamp.isoformat()
                }
                for exp in self.volume_explosions[-10:]  # 최근 10개만
            ]
        }
    
    def print_summary(self):
        """요약 정보 출력"""
        summary = self.get_summary()
        
        print("\n" + "="*60)
        print("📊 배치 모니터링 요약")
        print("="*60)
        print(f"전체 종목: {summary['total_markets']}개")
        print(f"체크 완료: {summary['checked_markets']}개")
        print(f"거래량 폭발: {summary['volume_explosions']}개")
        print(f"마지막 업데이트: {summary['last_update']}")
        
        if summary['explosions']:
            print(f"\n💥 최근 거래량 폭발:")
            for exp in summary['explosions']:
                print(f"  {exp['market']}: {exp['multiplier']:.1f}배 ({exp['timestamp']})")
        
        print("="*60)


async def main():
    """메인 실행 함수"""
    try:
        # API 초기화
        api = BithumbAPI()
        
        # 모니터 초기화
        monitor = BatchVolumeMonitor(api)
        
        # 초기화
        if await monitor.initialize():
            # 모니터링 시작
            await monitor.start_monitoring()
        else:
            logger.error("❌ 초기화 실패로 모니터링을 시작할 수 없습니다.")
            
    except Exception as e:
        logger.error(f"❌ 메인 실행 오류: {e}")


if __name__ == "__main__":
    asyncio.run(main())
