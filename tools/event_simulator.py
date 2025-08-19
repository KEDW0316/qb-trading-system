#!/usr/bin/env python3
"""
QB Trading System - 이벤트 시뮬레이터
=====================================

실제 거래 시스템(run_live_trading.py)과 함께 동작하여
실시간 시장 데이터 이벤트를 모사해서 전송하는 도구입니다.

사용법:
    # 기본 실행 (삼성전자, 매 30초마다 이벤트 전송)
    python tools/event_simulator.py
    
    # 특정 종목, 빈도 설정
    python tools/event_simulator.py --symbol 005930 --interval 10 --duration 300
    
    # 복수 종목 동시 시뮬레이션
    python tools/event_simulator.py --symbols 005930,000660,035420
    
    # 매매 신호 생성 확률 조정
    python tools/event_simulator.py --buy-bias 0.6 --sell-bias 0.4
"""

import asyncio
import argparse
import sys
import os
import time
import json
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

from qb.utils.redis_manager import RedisManager
from qb.engines.event_bus.core import EnhancedEventBus
from qb.utils.event_bus import EventType, Event

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class StockPrice:
    """주식 가격 정보"""
    symbol: str
    current_price: float
    open_price: float
    high_price: float
    low_price: float
    volume: int
    timestamp: datetime
    
    def get_ohlcv(self) -> Dict[str, Any]:
        """OHLCV 데이터 반환"""
        return {
            "symbol": self.symbol,
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.current_price,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "interval_type": "1m"
        }

class MarketDataGenerator:
    """실제 시장 데이터와 유사한 Mock 데이터 생성기"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.base_prices = {
            "005930": 75000,  # 삼성전자
            "000660": 145000,  # SK하이닉스
            "035420": 265000,  # NAVER
            "051910": 950000,  # LG화학
            "006400": 38000,   # 삼성SDI
            "207940": 87000,   # 삼성바이오로직스
            "005380": 71000,   # 현대차
            "005490": 115000,  # POSCO홀딩스
            "035720": 52000,   # 카카오
            "028260": 147000   # 삼성물산
        }
        
        # 기본 가격 설정
        self.current_price = self.base_prices.get(symbol, 50000)
        self.daily_open = self.current_price * random.uniform(0.98, 1.02)
        self.daily_high = self.daily_open
        self.daily_low = self.daily_open
        
        # 가격 변동 파라미터
        self.volatility = 0.005  # 0.5% 변동성
        self.trend_factor = random.uniform(-0.0002, 0.0002)  # 트렌드
        self.volume_base = random.randint(100000, 500000)
        
        logger.info(f"📊 {symbol} 데이터 생성기 초기화: 기준가 ₩{self.current_price:,.0f}")
    
    def generate_next_price(self) -> StockPrice:
        """다음 가격 데이터 생성"""
        # 가격 변동 (브라운 운동 + 트렌드)
        random_change = random.gauss(0, self.volatility)
        price_change = (random_change + self.trend_factor) * self.current_price
        
        # 새로운 가격 계산
        new_price = max(1, self.current_price + price_change)
        
        # OHLC 업데이트
        open_price = self.current_price  # 이전 가격이 현재 캔들의 시가
        high_price = max(open_price, new_price)
        low_price = min(open_price, new_price)
        close_price = new_price
        
        # 일중 고저가 업데이트
        self.daily_high = max(self.daily_high, high_price)
        self.daily_low = min(self.daily_low, low_price)
        
        # 거래량 생성 (변동성에 따라 증가)
        volume_multiplier = 1 + abs(random_change) * 10  # 변동성이 클수록 거래량 증가
        volume = int(self.volume_base * volume_multiplier * random.uniform(0.5, 2.0))
        
        # 현재 가격 업데이트
        self.current_price = close_price
        
        return StockPrice(
            symbol=self.symbol,
            current_price=close_price,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            volume=volume,
            timestamp=datetime.now()
        )

class TechnicalIndicatorGenerator:
    """기술적 지표 생성기"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.price_history = []
        
    def update_indicators(self, stock_price: StockPrice, buy_bias: float = 0.5, sell_bias: float = 0.5) -> Dict[str, float]:
        """기술적 지표 업데이트"""
        self.price_history.append(stock_price.current_price)
        if len(self.price_history) > 100:  # 최근 100개만 유지
            self.price_history.pop(0)
        
        current_price = stock_price.current_price
        
        # Moving Average 1M5M 전략에 필요한 지표들
        # 매매 신호 생성을 위한 조건부 설정
        signal_type = self._determine_signal_type(buy_bias, sell_bias)
        
        if signal_type == "BUY":
            # 매수 신호 생성: 현재가 > SMA
            sma_5 = current_price * random.uniform(0.995, 0.999)  # 현재가보다 약간 낮게
        elif signal_type == "SELL":
            # 매도 신호 생성: 현재가 <= SMA  
            sma_5 = current_price * random.uniform(1.001, 1.005)  # 현재가보다 약간 높게
        else:
            # 중립: 신호 없음
            sma_5 = current_price * random.uniform(0.998, 1.002)
            
        indicators = {
            # Moving Average 1M5M 전략 필수 지표
            'sma_3': current_price * random.uniform(0.995, 1.005),
            'sma_5': sma_5,  # 핵심 지표
            'avg_volume_5d': random.randint(50_000_000_000, 100_000_000_000),  # 500~1000억 (필터 통과)
            'price_change_6m_max': current_price * random.uniform(1.15, 1.25),  # 15~25% 상승 (끼 있는 종목)
            
            # 추가 기술 지표들
            'sma_20': current_price * random.uniform(0.95, 1.05),
            'ema_12': current_price * random.uniform(0.97, 1.03),
            'ema_26': current_price * random.uniform(0.96, 1.04),
            'rsi_14': random.uniform(30, 70),
            'macd': random.uniform(-500, 500),
            'macd_signal': random.uniform(-300, 300),
            'bb_upper': current_price * 1.02,
            'bb_lower': current_price * 0.98,
            'volume_sma_20': random.randint(50000, 200000),
            'price_change_6m_min': current_price * 0.85,
            'volatility_20d': random.uniform(0.15, 0.35),
            'atr_14': current_price * random.uniform(0.01, 0.03),
        }
        
        signal_desc = "BUY" if current_price > sma_5 else "SELL" if current_price <= sma_5 else "HOLD"
        logger.info(f"📊 {self.symbol} 지표 업데이트: 현재가=₩{current_price:,.0f}, SMA5=₩{sma_5:,.0f} → {signal_desc} 신호")
        
        return indicators
    
    def _determine_signal_type(self, buy_bias: float, sell_bias: float) -> str:
        """매매 신호 타입 결정"""
        rand = random.random()
        if rand < buy_bias:
            return "BUY"
        elif rand < buy_bias + sell_bias:
            return "SELL"
        else:
            return "HOLD"

class OrderbookGenerator:
    """호가 데이터 생성기"""
    
    def generate_orderbook(self, stock_price: StockPrice) -> Dict[str, Any]:
        """호가 데이터 생성"""
        current_price = stock_price.current_price
        
        # 매수/매도 호가 생성 (현재가 기준 ±0.5% 범위)
        bid_price = current_price * random.uniform(0.995, 0.999)  # 매수호가는 현재가보다 낮게
        ask_price = current_price * random.uniform(1.001, 1.005)  # 매도호가는 현재가보다 높게
        
        orderbook = {
            'symbol': stock_price.symbol,
            'bid_price': bid_price,  # 최우선 매수호가
            'ask_price': ask_price,  # 최우선 매도호가
            'bid_quantity': random.randint(100, 1000),
            'ask_quantity': random.randint(100, 1000),
            'timestamp': datetime.now().isoformat()
        }
        
        return orderbook

class EventSimulator:
    """이벤트 시뮬레이터 메인 클래스"""
    
    def __init__(self, symbols: List[str], interval_seconds: int = 30, 
                 buy_bias: float = 0.5, sell_bias: float = 0.5,
                 orderbook_interval: int = 3):
        self.symbols = symbols
        self.interval_seconds = interval_seconds
        self.orderbook_interval = orderbook_interval  # 호가 업데이트 간격 (기본 3초)
        self.buy_bias = buy_bias
        self.sell_bias = sell_bias
        self.running = False
        
        # Redis & Event Bus 초기화
        self.redis_manager = RedisManager()
        self.event_bus = EnhancedEventBus(redis_manager=self.redis_manager)
        
        # 데이터 생성기들
        self.market_generators = {symbol: MarketDataGenerator(symbol) for symbol in symbols}
        self.indicator_generators = {symbol: TechnicalIndicatorGenerator(symbol) for symbol in symbols}
        self.orderbook_generator = OrderbookGenerator()
        
        # 현재 가격 추적 (호가 생성용)
        self.current_prices = {symbol: gen.current_price for symbol, gen in self.market_generators.items()}
        
        # 통계
        self.events_sent = 0
        self.orderbook_updates = 0
        self.start_time = None
        
        logger.info(f"🎭 Event Simulator 초기화 완료: {len(symbols)}개 종목")
        logger.info(f"📊 시장데이터: {interval_seconds}초 간격, 📋 호가데이터: {orderbook_interval}초 간격")
    
    async def start(self, duration_seconds: Optional[int] = None):
        """시뮬레이터 시작"""
        if not self.redis_manager.ping():
            logger.error("❌ Redis 연결 실패")
            return False
        
        self.running = True
        self.start_time = datetime.now()
        
        logger.info("🚀 Event Simulator 시작!")
        logger.info(f"📊 대상 종목: {', '.join(self.symbols)}")
        logger.info(f"⏱️ 이벤트 간격: {self.interval_seconds}초")
        logger.info(f"📈 매수 편향: {self.buy_bias:.1%}, 매도 편향: {self.sell_bias:.1%}")
        
        if duration_seconds:
            logger.info(f"⏰ 실행 시간: {duration_seconds}초")
        
        try:
            end_time = datetime.now() + timedelta(seconds=duration_seconds) if duration_seconds else None
            
            # 호가 업데이트용 별도 태스크 시작
            orderbook_task = asyncio.create_task(self._orderbook_update_loop(end_time))
            
            while self.running:
                # 모든 종목에 대해 시장 데이터 이벤트 생성
                for symbol in self.symbols:
                    await self._generate_market_data_event(symbol)
                
                # 통계 출력 (매 10번째마다)
                if self.events_sent % (10 * len(self.symbols)) == 0:
                    self._print_status()
                
                # 종료 시간 체크
                if end_time and datetime.now() >= end_time:
                    logger.info("⏰ 지정된 실행 시간이 완료되었습니다.")
                    break
                
                # 대기
                await asyncio.sleep(self.interval_seconds)
            
            # 호가 업데이트 태스크 종료
            orderbook_task.cancel()
            try:
                await orderbook_task
            except asyncio.CancelledError:
                pass
                
        except KeyboardInterrupt:
            logger.info("⚠️ 사용자에 의해 중단되었습니다.")
        except Exception as e:
            logger.error(f"❌ 시뮬레이터 오류: {e}")
        finally:
            await self.stop()
    
    async def _generate_market_data_event(self, symbol: str):
        """시장 데이터 이벤트 생성 (30초 간격)"""
        try:
            # 1. 시장 데이터 생성
            stock_price = self.market_generators[symbol].generate_next_price()
            
            # 현재 가격 업데이트 (호가 생성용)
            self.current_prices[symbol] = stock_price.current_price
            
            # 2. 기술적 지표 생성 및 Redis 저장
            indicators = self.indicator_generators[symbol].update_indicators(
                stock_price, self.buy_bias, self.sell_bias
            )
            # 기술지표를 JSON으로 저장 (StrategyEngine에서 get_data로 조회)
            indicators_key = f"indicators:{symbol}"
            await asyncio.to_thread(self.redis_manager.redis.set, indicators_key, json.dumps(indicators), 3600)
            
            # 3. 시장 데이터를 Redis에 저장
            market_data_dict = stock_price.get_ohlcv()
            await asyncio.to_thread(self.redis_manager.set_market_data, symbol, market_data_dict)
            
            # 4. 시장 데이터 이벤트 발행
            market_data_event = Event(
                event_type=EventType.MARKET_DATA_RECEIVED,
                source="EventSimulator",
                timestamp=datetime.now(),
                data=stock_price.get_ohlcv(),
                correlation_id=f"sim_{symbol}_{int(time.time())}"
            )
            
            # Event Bus로 발행
            success = self.event_bus.publish(market_data_event)
            if success:
                self.events_sent += 1
                signal_type = "BUY" if stock_price.current_price > indicators.get('sma_5', 0) else "SELL"
                logger.info(f"📡 {symbol} 시장데이터: ₩{stock_price.current_price:,.0f}, SMA5: ₩{indicators.get('sma_5', 0):,.0f} → {signal_type} 조건")
            else:
                logger.error(f"❌ {symbol} 이벤트 발송 실패")
            
        except Exception as e:
            logger.error(f"❌ {symbol} 시장데이터 생성 실패: {e}")
    
    async def _orderbook_update_loop(self, end_time: Optional[datetime]):
        """호가 데이터 업데이트 루프 (3초 간격)"""
        try:
            while self.running:
                if end_time and datetime.now() >= end_time:
                    break
                
                # 모든 종목의 호가 업데이트
                for symbol in self.symbols:
                    await self._update_orderbook(symbol)
                
                await asyncio.sleep(self.orderbook_interval)
                
        except asyncio.CancelledError:
            logger.info("📋 호가 업데이트 루프 종료")
        except Exception as e:
            logger.error(f"❌ 호가 업데이트 루프 오류: {e}")
    
    async def _update_orderbook(self, symbol: str):
        """호가 데이터 업데이트"""
        try:
            # 현재 가격을 기준으로 호가 생성
            current_price = self.current_prices.get(symbol, 50000)
            
            # StockPrice 객체 생성 (호가 생성용)
            mock_stock_price = StockPrice(
                symbol=symbol,
                current_price=current_price,
                open_price=current_price,
                high_price=current_price,
                low_price=current_price,
                volume=0,
                timestamp=datetime.now()
            )
            
            # 호가 데이터 생성 및 Redis 저장
            orderbook = self.orderbook_generator.generate_orderbook(mock_stock_price)
            await asyncio.to_thread(self.redis_manager.set_orderbook_data, symbol, orderbook)
            
            self.orderbook_updates += 1
            
            # 10번마다 로그 출력
            if self.orderbook_updates % 10 == 0:
                logger.debug(f"📋 {symbol} 호가 업데이트: 매수호가 ₩{orderbook['bid_price']:,.0f}, 매도호가 ₩{orderbook['ask_price']:,.0f}")
            
        except Exception as e:
            logger.error(f"❌ {symbol} 호가 업데이트 실패: {e}")
    
    def _print_status(self):
        """현재 상태 출력"""
        runtime = datetime.now() - self.start_time if self.start_time else timedelta(0)
        events_per_symbol = self.events_sent // len(self.symbols) if self.symbols else 0
        orderbook_per_symbol = self.orderbook_updates // len(self.symbols) if self.symbols else 0
        
        logger.info("=" * 50)
        logger.info(f"🎭 Event Simulator 상태 ({runtime})")
        logger.info(f"📡 시장데이터 이벤트: {self.events_sent}개 (종목별 {events_per_symbol}개)")
        logger.info(f"📋 호가 업데이트: {self.orderbook_updates}개 (종목별 {orderbook_per_symbol}개)")
        logger.info(f"⚡ 초당 이벤트: {self.events_sent / max(1, runtime.total_seconds()):.1f}개/초")
        logger.info(f"📈 초당 호가: {self.orderbook_updates / max(1, runtime.total_seconds()):.1f}개/초")
        logger.info("=" * 50)
    
    async def stop(self):
        """시뮬레이터 중지"""
        self.running = False
        runtime = datetime.now() - self.start_time if self.start_time else timedelta(0)
        
        logger.info("\n🛑 Event Simulator 중지")
        logger.info("=" * 50)
        logger.info(f"⏱️ 총 실행 시간: {runtime}")
        logger.info(f"📡 총 이벤트 발송: {self.events_sent}개")
        logger.info(f"📊 종목 수: {len(self.symbols)}개")
        logger.info(f"⚡ 평균 이벤트 속도: {self.events_sent / max(1, runtime.total_seconds()):.1f}개/초")
        logger.info("=" * 50)

async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='QB Trading System - Event Simulator')
    parser.add_argument('--symbol', default='005930', help='시뮬레이션할 종목 코드 (기본: 005930)')
    parser.add_argument('--symbols', help='복수 종목 (쉼표 구분, 예: 005930,000660,035420)')
    parser.add_argument('--interval', type=int, default=30, help='시장데이터 발송 간격 (초, 기본: 30)')
    parser.add_argument('--orderbook-interval', type=int, default=3, help='호가 업데이트 간격 (초, 기본: 3)')
    parser.add_argument('--duration', type=int, help='실행 시간 (초, 기본: 무제한)')
    parser.add_argument('--buy-bias', type=float, default=0.3, help='매수 신호 편향 (0.0-1.0, 기본: 0.3)')
    parser.add_argument('--sell-bias', type=float, default=0.3, help='매도 신호 편향 (0.0-1.0, 기본: 0.3)')
    parser.add_argument('--debug', action='store_true', help='디버그 모드')
    
    args = parser.parse_args()
    
    # 로그 레벨 설정
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 종목 리스트 구성
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
    else:
        symbols = [args.symbol]
    
    # 편향 검증
    if args.buy_bias + args.sell_bias > 1.0:
        logger.warning(f"⚠️ 매수/매도 편향 합계가 1.0을 초과합니다 ({args.buy_bias + args.sell_bias:.1f})")
    
    # 시뮬레이터 시작
    simulator = EventSimulator(
        symbols=symbols,
        interval_seconds=args.interval,
        buy_bias=args.buy_bias,
        sell_bias=args.sell_bias,
        orderbook_interval=args.orderbook_interval
    )
    
    await simulator.start(duration_seconds=args.duration)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️ 프로그램이 중단되었습니다.")
    except Exception as e:
        logger.error(f"\n❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()