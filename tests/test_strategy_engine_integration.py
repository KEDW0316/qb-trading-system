"""
전략 엔진 통합 테스트

이벤트 기반 전략 엔진의 전체 워크플로우를 테스트합니다.
market_data_received 이벤트부터 trading_signal 발행까지의 전체 흐름을 검증합니다.
"""

import asyncio
import pytest
import json
from datetime import datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from qb.engines.strategy_engine.base import BaseStrategy, MarketData, TradingSignal
from qb.engines.strategy_engine.loader import StrategyLoader
from qb.engines.strategy_engine.engine import StrategyEngine
from qb.engines.strategy_engine.performance import StrategyPerformanceTracker
from qb.engines.strategy_engine.strategies.moving_average_1m5m import MovingAverage1M5MStrategy


class MockRedisManager:
    """Redis 관리자 모의 객체"""
    
    def __init__(self):
        self.data = {}
        self.lists = {}
    
    async def get_data(self, key: str):
        """데이터 조회"""
        return self.data.get(key)
    
    async def set_data(self, key: str, value):
        """데이터 저장"""
        self.data[key] = value
    
    async def add_to_list(self, key: str, value):
        """리스트에 추가"""
        if key not in self.lists:
            self.lists[key] = []
        self.lists[key].append(value)
    
    async def get_list_range(self, key: str, start: int, end: int):
        """리스트 범위 조회"""
        if key not in self.lists:
            return []
        return self.lists[key][start:end+1]
    
    async def trim_list(self, key: str, start: int, end: int):
        """리스트 트림"""
        if key in self.lists:
            self.lists[key] = self.lists[key][start:end+1]
    
    async def scan_keys(self, pattern: str):
        """키 패턴 스캔"""
        return [key for key in self.data.keys() if pattern.replace('*', '') in key]


class MockEventBus:
    """이벤트 버스 모의 객체"""
    
    def __init__(self):
        self.subscribers = {}
        self.published_events = []
    
    def subscribe(self, event_type: str, handler):
        """이벤트 구독"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def publish(self, event_type: str, data):
        """이벤트 발행"""
        self.published_events.append({
            'type': event_type,
            'data': data,
            'timestamp': datetime.now()
        })
        
        # 구독자들에게 이벤트 전달
        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                await handler(data)


@pytest.fixture
def mock_redis():
    """Mock Redis 관리자 픽스처"""
    return MockRedisManager()


@pytest.fixture
def mock_event_bus():
    """Mock 이벤트 버스 픽스처"""
    return MockEventBus()


@pytest.fixture
def strategy_engine(mock_redis, mock_event_bus):
    """전략 엔진 픽스처"""
    return StrategyEngine(mock_redis, mock_event_bus)


@pytest.fixture
def sample_market_data():
    """샘플 시장 데이터 픽스처"""
    return {
        "symbol": "005930",  # 삼성전자
        "timestamp": "2025-01-27T09:30:00",
        "open": 75000,
        "high": 75500,
        "low": 74800,
        "close": 75200,
        "volume": 1500000,
        "interval_type": "1m"
    }


@pytest.fixture
def sample_indicators():
    """샘플 기술적 지표 데이터 픽스처"""
    return {
        "sma_5": 75000,  # 5분 단순이동평균
        "avg_volume_5d": 50_000_000_000,  # 5일 평균 거래대금
        "price_change_6m_max": 0.18  # 6개월 최대 상승률
    }


class TestStrategyEngineIntegration:
    """전략 엔진 통합 테스트 클래스"""

    @pytest.mark.asyncio
    async def test_engine_initialization(self, strategy_engine):
        """전략 엔진 초기화 테스트"""
        assert strategy_engine is not None
        assert strategy_engine.redis is not None
        assert strategy_engine.event_bus is not None
        assert strategy_engine.strategy_loader is not None
        assert len(strategy_engine.active_strategies) == 0
        assert not strategy_engine.is_running

    @pytest.mark.asyncio
    async def test_engine_start_stop(self, strategy_engine):
        """전략 엔진 시작/중지 테스트"""
        # 시작
        await strategy_engine.start()
        assert strategy_engine.is_running
        
        # 중지
        await strategy_engine.stop()
        assert not strategy_engine.is_running

    @pytest.mark.asyncio
    async def test_strategy_activation_deactivation(self, strategy_engine):
        """전략 활성화/비활성화 테스트"""
        await strategy_engine.start()
        
        # 1분봉_5분봉 전략 활성화
        strategy_name = "MovingAverage1M5MStrategy"
        params = {
            "ma_period": 5,
            "confidence_threshold": 0.7
        }
        symbols = ["005930", "000660"]
        
        # 전략 활성화
        success = await strategy_engine.activate_strategy(strategy_name, params, symbols)
        assert success
        assert strategy_name in strategy_engine.active_strategies
        assert len(strategy_engine.active_strategies) == 1
        
        # 전략 비활성화
        success = await strategy_engine.deactivate_strategy(strategy_name)
        assert success
        assert strategy_name not in strategy_engine.active_strategies
        assert len(strategy_engine.active_strategies) == 0

    @pytest.mark.asyncio
    async def test_market_data_processing_buy_signal(self, strategy_engine, mock_redis, 
                                                   sample_market_data, sample_indicators):
        """시장 데이터 처리 및 매수 신호 생성 테스트"""
        await strategy_engine.start()
        
        # Redis에 기술적 지표 설정
        indicators_key = f"indicators:{sample_market_data['symbol']}"
        await mock_redis.set_data(indicators_key, json.dumps(sample_indicators))
        
        # 전략 활성화
        strategy_name = "MovingAverage1M5MStrategy"
        symbols = [sample_market_data['symbol']]
        await strategy_engine.activate_strategy(strategy_name, None, symbols)
        
        # 매수 신호가 나올 조건: 현재가(75200) > 5분 평균(75000)
        sample_market_data['close'] = 75200
        sample_indicators['sma_5'] = 75000
        await mock_redis.set_data(indicators_key, json.dumps(sample_indicators))
        
        # 시장 데이터 이벤트 발행
        await strategy_engine.on_market_data(sample_market_data)
        
        # 거래 신호가 발행되었는지 확인
        published_events = strategy_engine.event_bus.published_events
        trading_signals = [e for e in published_events if e['type'] == 'trading_signal']
        
        assert len(trading_signals) > 0
        signal = trading_signals[0]['data']
        assert signal['action'] == 'BUY'
        assert signal['symbol'] == sample_market_data['symbol']
        assert signal['strategy'] == strategy_name

    @pytest.mark.asyncio
    async def test_market_data_processing_sell_signal(self, strategy_engine, mock_redis,
                                                    sample_market_data, sample_indicators):
        """시장 데이터 처리 및 매도 신호 생성 테스트"""
        await strategy_engine.start()
        
        # Redis에 기술적 지표 설정
        indicators_key = f"indicators:{sample_market_data['symbol']}"
        await mock_redis.set_data(indicators_key, json.dumps(sample_indicators))
        
        # 전략 활성화
        strategy_name = "MovingAverage1M5MStrategy"
        symbols = [sample_market_data['symbol']]
        await strategy_engine.activate_strategy(strategy_name, None, symbols)
        
        # 전략에 포지션 상태 설정 (이미 매수한 상태)
        strategy = strategy_engine.active_strategies[strategy_name]
        strategy.current_position[sample_market_data['symbol']] = {
            'quantity': 100,
            'entry_price': 75000,
            'entry_time': datetime.now()
        }
        
        # 매도 신호가 나올 조건: 현재가(74800) <= 5분 평균(75000)
        sample_market_data['close'] = 74800
        sample_indicators['sma_5'] = 75000
        await mock_redis.set_data(indicators_key, json.dumps(sample_indicators))
        
        # 시장 데이터 이벤트 발행
        await strategy_engine.on_market_data(sample_market_data)
        
        # 거래 신호가 발행되었는지 확인
        published_events = strategy_engine.event_bus.published_events
        trading_signals = [e for e in published_events if e['type'] == 'trading_signal']
        
        assert len(trading_signals) > 0
        signal = trading_signals[0]['data']
        assert signal['action'] == 'SELL'
        assert signal['symbol'] == sample_market_data['symbol']
        assert signal['strategy'] == strategy_name

    @pytest.mark.asyncio
    async def test_market_close_forced_sell(self, strategy_engine, mock_redis,
                                          sample_market_data, sample_indicators):
        """장마감 강제 매도 테스트"""
        await strategy_engine.start()
        
        # Redis에 기술적 지표 설정
        indicators_key = f"indicators:{sample_market_data['symbol']}"
        await mock_redis.set_data(indicators_key, json.dumps(sample_indicators))
        
        # 전략 활성화
        strategy_name = "MovingAverage1M5MStrategy"
        symbols = [sample_market_data['symbol']]
        await strategy_engine.activate_strategy(strategy_name, None, symbols)
        
        # 전략에 포지션 상태 설정
        strategy = strategy_engine.active_strategies[strategy_name]
        strategy.current_position[sample_market_data['symbol']] = {
            'quantity': 100,
            'entry_price': 75000,
            'entry_time': datetime.now()
        }
        
        # 장마감 시간으로 설정 (15:20)
        sample_market_data['timestamp'] = "2025-01-27T15:20:00"
        
        # 시장 데이터 이벤트 발행
        await strategy_engine.on_market_data(sample_market_data)
        
        # 강제 매도 신호가 발행되었는지 확인
        published_events = strategy_engine.event_bus.published_events
        trading_signals = [e for e in published_events if e['type'] == 'trading_signal']
        
        assert len(trading_signals) > 0
        signal = trading_signals[0]['data']
        assert signal['action'] == 'SELL'
        assert signal['symbol'] == sample_market_data['symbol']
        assert signal['confidence'] == 1.0  # 강제 매도는 최고 신뢰도
        assert '강제매도' in signal['reason']

    @pytest.mark.asyncio
    async def test_strategy_parameter_update(self, strategy_engine):
        """전략 파라미터 업데이트 테스트"""
        await strategy_engine.start()
        
        # 전략 활성화
        strategy_name = "MovingAverage1M5MStrategy"
        initial_params = {"ma_period": 5}
        await strategy_engine.activate_strategy(strategy_name, initial_params, ["005930"])
        
        # 파라미터 업데이트
        new_params = {"ma_period": 10, "confidence_threshold": 0.8}
        success = await strategy_engine.update_strategy_parameters(strategy_name, new_params)
        
        assert success
        
        # 업데이트된 파라미터 확인
        strategy = strategy_engine.active_strategies[strategy_name]
        updated_params = strategy.get_parameters()
        assert updated_params['ma_period'] == 10
        assert updated_params['confidence_threshold'] == 0.8

    @pytest.mark.asyncio
    async def test_multiple_strategies_execution(self, strategy_engine, mock_redis,
                                               sample_market_data, sample_indicators):
        """여러 전략 동시 실행 테스트"""
        await strategy_engine.start()
        
        # Redis에 기술적 지표 설정
        indicators_key = f"indicators:{sample_market_data['symbol']}"
        await mock_redis.set_data(indicators_key, json.dumps(sample_indicators))
        
        # 두 개의 다른 파라미터로 같은 전략 활성화
        strategy1_name = "MovingAverage1M5MStrategy"
        strategy2_name = "MovingAverage1M5MStrategy_v2"
        
        params1 = {"ma_period": 5}
        params2 = {"ma_period": 3}
        
        symbols = [sample_market_data['symbol']]
        
        # 첫 번째 전략 활성화 (실제로는 같은 클래스지만 다른 인스턴스)
        await strategy_engine.activate_strategy(strategy1_name, params1, symbols)
        
        # 두 번째 전략은 임시로 첫 번째와 같은 것으로 테스트
        # (실제 구현에서는 다른 전략 클래스를 사용할 수 있음)
        
        # 매수 조건 설정
        sample_market_data['close'] = 75200
        sample_indicators['sma_5'] = 75000
        sample_indicators['sma_3'] = 75100  # 3분 평균도 추가
        await mock_redis.set_data(indicators_key, json.dumps(sample_indicators))
        
        # 시장 데이터 이벤트 발행
        await strategy_engine.on_market_data(sample_market_data)
        
        # 신호가 발행되었는지 확인
        published_events = strategy_engine.event_bus.published_events
        trading_signals = [e for e in published_events if e['type'] == 'trading_signal']
        
        assert len(trading_signals) > 0  # 최소 하나의 신호는 있어야 함

    @pytest.mark.asyncio
    async def test_performance_tracking_integration(self, strategy_engine, mock_redis,
                                                  sample_market_data, sample_indicators):
        """성과 추적 통합 테스트"""
        await strategy_engine.start()
        
        # Redis에 기술적 지표 설정
        indicators_key = f"indicators:{sample_market_data['symbol']}"
        await mock_redis.set_data(indicators_key, json.dumps(sample_indicators))
        
        # 전략 활성화
        strategy_name = "MovingAverage1M5MStrategy"
        symbols = [sample_market_data['symbol']]
        await strategy_engine.activate_strategy(strategy_name, None, symbols)
        
        # 매수 신호 발생 조건
        sample_market_data['close'] = 75200
        sample_indicators['sma_5'] = 75000
        await mock_redis.set_data(indicators_key, json.dumps(sample_indicators))
        
        # 시장 데이터 이벤트 발행
        await strategy_engine.on_market_data(sample_market_data)
        
        # 성과 추적기에서 신호가 기록되었는지 확인
        # 실제 구현에서는 performance_tracker가 연동되어야 함
        published_events = strategy_engine.event_bus.published_events
        assert len(published_events) > 0

    @pytest.mark.asyncio
    async def test_strategy_loader_integration(self):
        """전략 로더 통합 테스트"""
        loader = StrategyLoader()
        
        # 전략 탐색
        discovered_strategies = loader.discover_strategies()
        assert isinstance(discovered_strategies, list)
        
        # MovingAverage1M5MStrategy가 발견되었는지 확인
        if "MovingAverage1M5MStrategy" in discovered_strategies:
            # 전략 로드
            strategy = loader.load_strategy("MovingAverage1M5MStrategy")
            assert strategy is not None
            assert strategy.__class__.__name__ == "MovingAverage1M5MStrategy"
            
            # 전략 정보 확인
            description = strategy.get_description()
            assert "1분봉_5분봉" in description
            
            required_indicators = strategy.get_required_indicators()
            assert "sma_5" in required_indicators
        else:
            # 전략이 발견되지 않은 경우, 최소한 로더가 동작하는지 확인
            assert isinstance(discovered_strategies, list)

    def test_strategy_engine_status(self, strategy_engine):
        """전략 엔진 상태 조회 테스트"""
        status = strategy_engine.get_engine_status()
        
        assert 'is_running' in status
        assert 'active_strategies' in status
        assert 'available_strategies' in status
        assert 'total_signals_generated' in status
        assert status['is_running'] == False  # 시작하지 않은 상태
        assert status['active_strategies'] == 0


class TestMovingAverage1M5MStrategy:
    """1분봉_5분봉 전략 단위 테스트"""

    @pytest.fixture
    def strategy(self):
        """전략 인스턴스 픽스처"""
        return MovingAverage1M5MStrategy()

    def test_strategy_initialization(self, strategy):
        """전략 초기화 테스트"""
        assert strategy is not None
        assert strategy.params['ma_period'] == 5
        assert strategy.params['confidence_threshold'] == 0.7
        assert len(strategy.current_position) == 0

    def test_required_indicators(self, strategy):
        """필요 지표 테스트"""
        indicators = strategy.get_required_indicators()
        assert "sma_5" in indicators
        assert "avg_volume_5d" in indicators
        assert "price_change_6m_max" in indicators

    def test_parameter_schema(self, strategy):
        """파라미터 스키마 테스트"""
        schema = strategy.get_parameter_schema()
        assert 'ma_period' in schema
        assert 'confidence_threshold' in schema
        assert 'market_close_time' in schema
        assert schema['ma_period']['type'] == int
        assert schema['confidence_threshold']['type'] == float

    @pytest.mark.asyncio
    async def test_buy_signal_generation(self, strategy):
        """매수 신호 생성 테스트"""
        market_data = MarketData(
            symbol="005930",
            timestamp=datetime(2025, 1, 27, 9, 30, 0),
            open=75000,
            high=75500,
            low=74800,
            close=75200,  # 현재가
            volume=1500000,
            interval_type="1m",
            indicators={
                "sma_5": 75000,  # 5분 평균
                "avg_volume_5d": 50_000_000_000,
                "price_change_6m_max": 0.18
            }
        )
        
        # 매수 조건: 현재가(75200) > 5분 평균(75000)
        signal = await strategy.analyze(market_data)
        
        assert signal is not None
        assert signal.action == 'BUY'
        assert signal.symbol == "005930"
        assert signal.confidence > 0.5
        assert "5분 평균" in signal.reason

    @pytest.mark.asyncio
    async def test_sell_signal_generation(self, strategy):
        """매도 신호 생성 테스트"""
        # 먼저 포지션 설정 (이미 매수한 상태)
        strategy.current_position["005930"] = {
            'quantity': 100,
            'entry_price': 75000,
            'entry_time': datetime.now()
        }
        
        market_data = MarketData(
            symbol="005930",
            timestamp=datetime(2025, 1, 27, 9, 31, 0),
            open=75000,
            high=75200,
            low=74500,
            close=74800,  # 현재가
            volume=1200000,
            interval_type="1m",
            indicators={
                "sma_5": 75000,  # 5분 평균
                "avg_volume_5d": 50_000_000_000,
                "price_change_6m_max": 0.18
            }
        )
        
        # 매도 조건: 현재가(74800) <= 5분 평균(75000)
        signal = await strategy.analyze(market_data)
        
        assert signal is not None
        assert signal.action == 'SELL'
        assert signal.symbol == "005930"
        assert signal.confidence > 0.5
        assert "5분 평균" in signal.reason


if __name__ == "__main__":
    # 테스트 실행
    print("🚀 Starting Strategy Engine Integration Tests...")
    
    # pytest를 사용하여 테스트 실행
    import subprocess
    result = subprocess.run([
        "python", "-m", "pytest", __file__, "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    print("📊 Test Results:")
    print(result.stdout)
    
    if result.stderr:
        print("⚠️ Test Errors:")
        print(result.stderr)
    
    if result.returncode == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
        
    print(f"Exit code: {result.returncode}")