"""
Mock KIS Data Adapter

실제 KIS WebSocket 없이 전체 시스템 테스트를 위한 Mock 어댑터
기존 KISDataAdapter와 동일한 인터페이스 제공
"""

import asyncio
import random
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.engines.data_collector.adapters import BaseDataAdapter, AdapterStatus


@dataclass
class MockSymbolData:
    """모의 종목 데이터"""
    symbol: str
    current_price: float
    base_price: float  # 시작 가격
    volatility: float  # 변동성 (0.01 = 1%)
    trend: float  # 추세 (-1.0 ~ 1.0)
    volume_base: int  # 기본 거래량
    
    
class MockPriceGenerator:
    """모의 가격 생성기"""
    
    def __init__(self, symbol_data: MockSymbolData):
        self.data = symbol_data
        self.price_history = [symbol_data.current_price]
        
    def next_price(self) -> float:
        """다음 가격 생성"""
        current = self.data.current_price
        
        # 랜덤 변동 + 추세 반영
        random_change = random.normalvariate(0, 1) * self.data.volatility * current
        trend_change = self.data.trend * 0.001 * current  # 추세는 작게 적용
        
        # 새 가격 계산 (최소 100원 보장)
        new_price = max(current + random_change + trend_change, 100.0)
        
        # 가격 업데이트
        self.data.current_price = new_price
        self.price_history.append(new_price)
        
        # 히스토리는 최근 100개만 유지
        if len(self.price_history) > 100:
            self.price_history.pop(0)
            
        # 가끔 추세 변경 (5% 확률)
        if random.random() < 0.05:
            self.data.trend = random.uniform(-0.5, 0.5)
            
        return new_price
    
    def generate_orderbook(self) -> Dict[str, Any]:
        """호가창 데이터 생성"""
        current = self.data.current_price
        
        # 호가 생성 (현재가 기준으로 위아래 분산)
        bid_prices = []
        ask_prices = []
        bid_volumes = []
        ask_volumes = []
        
        for i in range(1, 11):  # 10호가까지
            # 매수호가 (현재가보다 낮음)
            bid_price = current * (1 - random.uniform(0.001, 0.005) * i)
            bid_prices.append(int(bid_price))
            bid_volumes.append(random.randint(10, 500))
            
            # 매도호가 (현재가보다 높음)  
            ask_price = current * (1 + random.uniform(0.001, 0.005) * i)
            ask_prices.append(int(ask_price))
            ask_volumes.append(random.randint(10, 500))
        
        return {
            'bid_prices': bid_prices,
            'ask_prices': ask_prices, 
            'bid_volumes': bid_volumes,
            'ask_volumes': ask_volumes
        }


class MockKISDataAdapter(BaseDataAdapter):
    """
    Mock KIS Data Adapter
    
    실제 KIS WebSocket 대신 모의 데이터를 생성하여
    전체 시스템 테스트를 위한 어댑터
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("MockKIS", config)
        
        # 모의 데이터 설정
        self.tick_interval = config.get('tick_interval', 1.0)  # 틱 간격 (초)
        self.symbols_data: Dict[str, MockSymbolData] = {}
        self.price_generators: Dict[str, MockPriceGenerator] = {}
        
        # 데이터 생성 태스크
        self._data_generation_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 메시지 큐 초기화
        self.message_queue = asyncio.Queue()
        
        # 기본 종목 설정
        default_symbols = {
            "005930": {"name": "삼성전자", "base_price": 75000, "volatility": 0.02},
            "000660": {"name": "SK하이닉스", "base_price": 145000, "volatility": 0.025}, 
            "035720": {"name": "카카오", "base_price": 85000, "volatility": 0.03}
        }
        
        # 모의 종목 데이터 초기화
        for symbol, info in default_symbols.items():
            self._initialize_symbol_data(symbol, info)
            
        self.logger.info(f"MockKISDataAdapter initialized with {len(default_symbols)} symbols")
    
    def _initialize_symbol_data(self, symbol: str, info: Dict[str, Any]):
        """종목 데이터 초기화"""
        symbol_data = MockSymbolData(
            symbol=symbol,
            current_price=info['base_price'],
            base_price=info['base_price'],
            volatility=info['volatility'],
            trend=random.uniform(-0.3, 0.3),  # 초기 추세
            volume_base=random.randint(100, 1000)
        )
        
        self.symbols_data[symbol] = symbol_data
        self.price_generators[symbol] = MockPriceGenerator(symbol_data)
        
    async def connect(self) -> bool:
        """Mock 연결 (항상 성공)"""
        try:
            self.status = AdapterStatus.CONNECTING
            await asyncio.sleep(0.1)  # 연결 지연 시뮬레이션
            
            self.status = AdapterStatus.CONNECTED
            self.stats['connections'] += 1
            self._running = True
            
            # 데이터 생성 태스크 시작
            self._data_generation_task = asyncio.create_task(self._generate_data_loop())
            
            self.logger.info("MockKIS connected successfully")
            return True
            
        except Exception as e:
            self.status = AdapterStatus.ERROR
            self.stats['errors'] += 1
            self.logger.error(f"Failed to connect MockKIS: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """Mock 연결 해제"""
        try:
            self._running = False
            
            if self._data_generation_task:
                self._data_generation_task.cancel()
                try:
                    await self._data_generation_task
                except asyncio.CancelledError:
                    pass
                    
            self.status = AdapterStatus.DISCONNECTED
            self.logger.info("MockKIS disconnected")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to disconnect MockKIS: {e}")
            return False
    
    async def subscribe_symbol(self, symbol: str) -> bool:
        """심볼 구독 (Mock)"""
        try:
            if symbol not in self.symbols_data:
                # 새로운 심볼이면 기본값으로 초기화
                self._initialize_symbol_data(symbol, {
                    'name': f'Stock_{symbol}',
                    'base_price': random.uniform(10000, 100000),
                    'volatility': random.uniform(0.015, 0.035)
                })
            
            self.subscribed_symbols.add(symbol)
            self.logger.info(f"Subscribed to MockKIS symbol: {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe symbol {symbol}: {e}")
            return False
    
    async def unsubscribe_symbol(self, symbol: str) -> bool:
        """심볼 구독 해제 (Mock)"""
        try:
            self.subscribed_symbols.discard(symbol)
            self.logger.info(f"Unsubscribed from MockKIS symbol: {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe symbol {symbol}: {e}")
            return False
            
    async def collect_data(self) -> List[Dict[str, Any]]:
        """데이터 수집 (큐에서 가져오기)"""
        messages = []
        
        # 큐에서 모든 대기 중인 메시지 가져오기
        while not self.message_queue.empty():
            try:
                message = self.message_queue.get_nowait()
                messages.append(message)
            except asyncio.QueueEmpty:
                break
                
        return messages
    
    async def _generate_data_loop(self):
        """데이터 생성 루프"""
        try:
            while self._running:
                await self._generate_tick_data()
                await asyncio.sleep(self.tick_interval)
                
        except asyncio.CancelledError:
            self.logger.info("Data generation loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in data generation loop: {e}")
    
    async def _generate_tick_data(self):
        """틱 데이터 생성"""
        for symbol in self.subscribed_symbols:
            if symbol not in self.price_generators:
                continue
                
            try:
                generator = self.price_generators[symbol]
                symbol_data = self.symbols_data[symbol]
                
                # 새 가격 생성
                new_price = generator.next_price()
                
                # 체결 데이터 생성 (H0STCNT0 형식 - 1분봉으로 설정)
                tick_data = {
                    "symbol": symbol,
                    "timestamp": datetime.now().isoformat(),
                    "open": new_price * 0.999,
                    "high": new_price * 1.001,
                    "low": new_price * 0.998,
                    "close": new_price,
                    "volume": random.randint(symbol_data.volume_base // 2, symbol_data.volume_base * 2),
                    "change": new_price - symbol_data.base_price,
                    "change_rate": ((new_price - symbol_data.base_price) / symbol_data.base_price) * 100,
                    "message_type": "trade",
                    "data_type": "1m",  # 1분봉으로 설정
                    "source": "mock_kis"
                }
                
                # 큐에 추가
                await self.message_queue.put(tick_data)
                self.stats['messages_received'] += 1
                
                # 30% 확률로 호가 데이터도 생성 (H0STASP0 형식)
                if random.random() < 0.3:
                    orderbook = generator.generate_orderbook()
                    
                    orderbook_data = {
                        "symbol": symbol,
                        "timestamp": datetime.now().isoformat(),
                        "bid_price": orderbook['bid_prices'][0],  # 최우선 매수호가
                        "ask_price": orderbook['ask_prices'][0],  # 최우선 매도호가
                        "bid_volume": orderbook['bid_volumes'][0],
                        "ask_volume": orderbook['ask_volumes'][0],
                        "message_type": "orderbook",
                        "source": "mock_kis"
                    }
                    
                    await self.message_queue.put(orderbook_data)
                    self.stats['messages_received'] += 1
                    
            except Exception as e:
                self.logger.error(f"Error generating data for {symbol}: {e}")
                self.stats['errors'] += 1
    
    def get_status(self) -> Dict[str, Any]:
        """어댑터 상태 반환"""
        status = super().get_status()
        status.update({
            'tick_interval': self.tick_interval,
            'symbols_count': len(self.symbols_data),
            'running': self._running,
            'current_prices': {
                symbol: data.current_price 
                for symbol, data in self.symbols_data.items()
            }
        })
        return status
    
    def set_tick_interval(self, interval: float):
        """틱 간격 동적 변경"""
        self.tick_interval = max(0.1, interval)  # 최소 0.1초
        self.logger.info(f"Tick interval changed to {self.tick_interval}s")
        
    def set_volatility(self, symbol: str, volatility: float):
        """종목 변동성 동적 변경"""
        if symbol in self.symbols_data:
            self.symbols_data[symbol].volatility = max(0.001, volatility)  # 최소 0.1%
            self.logger.info(f"Volatility for {symbol} changed to {volatility}")
            
    def set_trend(self, symbol: str, trend: float):
        """종목 추세 동적 변경"""
        if symbol in self.symbols_data:
            self.symbols_data[symbol].trend = max(-1.0, min(1.0, trend))  # -1.0 ~ 1.0
            self.logger.info(f"Trend for {symbol} changed to {trend}")
    
    async def get_historical_data(self, symbol: str, timeframe: str, count: int = 200) -> List[Dict[str, Any]]:
        """과거 데이터 조회 (Mock)"""
        try:
            if symbol not in self.symbols_data:
                return []
            
            symbol_data = self.symbols_data[symbol]
            base_price = symbol_data.base_price
            
            # 가짜 과거 데이터 생성
            historical_data = []
            current_time = datetime.now()
            
            for i in range(count, 0, -1):  # 과거부터 현재까지
                # 시간 계산 (1분 간격)
                timestamp = current_time - timedelta(minutes=i)
                
                # 가격 생성 (기준가에서 랜덤 변동)
                price_variation = random.uniform(-0.1, 0.1)  # ±10% 변동
                price = base_price * (1 + price_variation)
                
                # OHLC 데이터 생성
                open_price = price * random.uniform(0.995, 1.005)
                high_price = max(price, open_price) * random.uniform(1.0, 1.01)
                low_price = min(price, open_price) * random.uniform(0.99, 1.0)
                close_price = price
                volume = random.randint(1000, 10000)
                
                candle_data = {
                    "symbol": symbol,
                    "timestamp": timestamp.isoformat(),
                    "timeframe": timeframe,
                    "open": round(open_price, 2),
                    "high": round(high_price, 2),
                    "low": round(low_price, 2), 
                    "close": round(close_price, 2),
                    "volume": volume
                }
                
                historical_data.append(candle_data)
            
            self.logger.info(f"Generated {len(historical_data)} historical candles for {symbol}")
            return historical_data
            
        except Exception as e:
            self.logger.error(f"Failed to generate historical data for {symbol}: {e}")
            return []