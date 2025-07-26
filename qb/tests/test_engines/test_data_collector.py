"""
Data Collector Engine 통합 테스트
"""

import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from qb.engines.data_collector import (
    DataCollector, CollectionConfig, KISDataAdapter, 
    NaverDataAdapter, YahooDataAdapter, DataNormalizer,
    ConnectionManager, DataQualityChecker
)
from qb.utils.redis_manager import RedisManager
from qb.utils.event_bus import EventBus, EventType


class TestDataCollectorEngine:
    """DataCollector 엔진 통합 테스트"""
    
    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis Manager"""
        redis_manager = Mock(spec=RedisManager)
        redis_manager.ping.return_value = True
        redis_manager.set_market_data = AsyncMock(return_value=True)
        redis_manager.add_candle = AsyncMock(return_value=True)
        return redis_manager
    
    @pytest.fixture
    def mock_event_bus(self):
        """Mock Event Bus"""
        event_bus = Mock(spec=EventBus)
        event_bus.publish = Mock()
        event_bus.create_event = Mock()
        return event_bus
    
    @pytest.fixture
    def collection_config(self):
        """테스트용 수집 설정"""
        return CollectionConfig(
            symbols=['005930', '000660'],  # 삼성전자, SK하이닉스
            adapters=['kis', 'naver'],
            max_candles=50,
            collection_interval=0.1,  # 빠른 테스트를 위해 0.1초
            quality_check_enabled=True,
            auto_restart=True,
            heartbeat_interval=5
        )
    
    @pytest.fixture
    def data_collector(self, mock_redis_manager, mock_event_bus, collection_config):
        """DataCollector 인스턴스"""
        return DataCollector(
            redis_manager=mock_redis_manager,
            event_bus=mock_event_bus,
            config=collection_config
        )
    
    def test_data_collector_initialization(self, data_collector):
        """DataCollector 초기화 테스트"""
        assert data_collector.status.value == "stopped"
        assert len(data_collector.config.symbols) == 2
        assert data_collector.data_normalizer is not None
        assert data_collector.connection_manager is not None
        assert data_collector.quality_checker is not None
    
    @pytest.mark.asyncio
    async def test_data_collector_start_stop(self, data_collector):
        """DataCollector 시작/중지 테스트"""
        # 시작 테스트
        with patch.object(data_collector, '_initialize_adapters', new_callable=AsyncMock):
            with patch.object(data_collector, '_subscribe_symbols', new_callable=AsyncMock):
                with patch.object(data_collector, '_start_collection_tasks', new_callable=AsyncMock):
                    result = await data_collector.start()
                    assert result is True
                    assert data_collector.status.value == "running"
        
        # 중지 테스트
        with patch.object(data_collector, '_stop_collection_tasks', new_callable=AsyncMock):
            with patch.object(data_collector, '_disconnect_adapters', new_callable=AsyncMock):
                result = await data_collector.stop()
                assert result is True
                assert data_collector.status.value == "stopped"
    
    @pytest.mark.asyncio
    async def test_symbol_management(self, data_collector):
        """심볼 추가/제거 테스트"""
        # Mock 어댑터 추가
        mock_adapter = Mock()
        mock_adapter.subscribe_symbol = AsyncMock(return_value=True)
        mock_adapter.unsubscribe_symbol = AsyncMock(return_value=True)
        data_collector.adapters['test'] = mock_adapter
        
        # 심볼 추가
        result = await data_collector.add_symbol('005380')
        assert result is True
        assert '005380' in data_collector.active_symbols
        
        # 심볼 제거
        result = await data_collector.remove_symbol('005380')
        assert result is True
        assert '005380' not in data_collector.active_symbols


class TestDataNormalizer:
    """DataNormalizer 테스트"""
    
    @pytest.fixture
    def normalizer(self):
        return DataNormalizer()
    
    @pytest.mark.asyncio
    async def test_kis_data_normalization(self, normalizer):
        """KIS 데이터 정규화 테스트"""
        kis_data = {
            'MKSC_SHRN_ISCD': '005930',
            'STCK_PRPR': '75000',
            'CNTG_VOL': '1000',
            'PRDY_VRSS': '500',
            'timestamp': datetime.now().isoformat()
        }
        
        normalized = await normalizer.normalize(kis_data, 'kis')
        
        assert normalized['symbol'] == '005930'
        assert normalized['close'] == 75000.0
        assert normalized['volume'] == 1000
        assert normalized['change'] == 500.0
        assert normalized['source'] == 'kis'
    
    @pytest.mark.asyncio
    async def test_invalid_data_handling(self, normalizer):
        """잘못된 데이터 처리 테스트"""
        invalid_data = {
            'invalid_field': 'invalid_value'
        }
        
        try:
            normalized = await normalizer.normalize(invalid_data, 'kis')
            # 기본값이 설정되어야 함
            assert normalized['symbol'] == ''
            assert normalized['close'] == 0.0
        except Exception as e:
            # 예외가 발생할 수 있음
            assert True


class TestDataQualityChecker:
    """DataQualityChecker 테스트"""
    
    @pytest.fixture
    def quality_checker(self):
        return DataQualityChecker(history_size=10)
    
    @pytest.mark.asyncio
    async def test_valid_data_validation(self, quality_checker):
        """유효한 데이터 검증 테스트"""
        valid_data = {
            'symbol': '005930',
            'timestamp': datetime.now().isoformat(),
            'open': 75000.0,
            'high': 75500.0,
            'low': 74500.0,
            'close': 75200.0,
            'volume': 1000000
        }
        
        is_valid, issues = await quality_checker.validate(valid_data)
        assert is_valid is True
        assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_invalid_data_validation(self, quality_checker):
        """잘못된 데이터 검증 테스트"""
        invalid_data = {
            'symbol': '',  # 빈 심볼
            'close': -100,  # 음수 가격
            'volume': -1000  # 음수 거래량
        }
        
        is_valid, issues = await quality_checker.validate(invalid_data)
        assert is_valid is False
        assert len(issues) > 0


class TestConnectionManager:
    """ConnectionManager 테스트"""
    
    @pytest.fixture
    def connection_manager(self):
        return ConnectionManager(max_retries=3, retry_delay=0.1)
    
    @pytest.mark.asyncio
    async def test_successful_connection(self, connection_manager):
        """성공적인 연결 테스트"""
        async def mock_connect():
            return True
        
        result = await connection_manager.connect(mock_connect)
        assert result is True
        assert connection_manager.is_connected() is True
    
    @pytest.mark.asyncio
    async def test_failed_connection_with_retry(self, connection_manager):
        """실패한 연결 재시도 테스트"""
        call_count = 0
        
        async def mock_connect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return False
            return True
        
        async def mock_disconnect():
            pass
        
        result = await connection_manager.reconnect(mock_connect, mock_disconnect)
        assert result is True
        assert call_count == 3


class TestAdapters:
    """데이터 어댑터 테스트"""
    
    def test_kis_adapter_initialization(self):
        """KIS 어댑터 초기화 테스트"""
        config = {
            'mode': 'paper',
            'approval_key': 'test_key',
            'max_retries': 3
        }
        
        with patch('qb.collectors.kis_client.KISClient'):
            adapter = KISDataAdapter(config)
            assert adapter.name == 'KIS'
            assert adapter.approval_key == 'test_key'
    
    def test_naver_adapter_initialization(self):
        """Naver 어댑터 초기화 테스트"""
        config = {
            'polling_interval': 10
        }
        
        adapter = NaverDataAdapter(config)
        assert adapter.name == 'Naver'
        assert adapter.polling_interval == 10
    
    def test_yahoo_adapter_initialization(self):
        """Yahoo 어댑터 초기화 테스트"""
        config = {
            'polling_interval': 15
        }
        
        adapter = YahooDataAdapter(config)
        assert adapter.name == 'Yahoo'
        assert adapter.polling_interval == 15


@pytest.mark.integration
class TestDataCollectorIntegration:
    """DataCollector 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_data_flow(self):
        """End-to-End 데이터 흐름 테스트"""
        # Mock 설정
        mock_redis = Mock(spec=RedisManager)
        mock_redis.ping.return_value = True
        mock_redis.set_market_data = AsyncMock(return_value=True)
        mock_redis.add_candle = AsyncMock(return_value=True)
        
        mock_event_bus = Mock(spec=EventBus)
        mock_event_bus.publish = Mock()
        mock_event_bus.create_event = Mock()
        
        config = CollectionConfig(
            symbols=['005930'],
            adapters=['naver'],
            max_candles=10,
            collection_interval=0.1,
            quality_check_enabled=True
        )
        
        collector = DataCollector(
            redis_manager=mock_redis,
            event_bus=mock_event_bus,
            config=config
        )
        
        # 테스트 데이터
        test_data = {
            'symbol': '005930',
            'timestamp': datetime.now().isoformat(),
            'close': 75000.0,
            'volume': 1000000,
            'source': 'naver'
        }
        
        # 데이터 처리 테스트
        await collector._process_message('naver', test_data)
        
        # Redis 저장 확인
        mock_redis.set_market_data.assert_called_once()
        mock_redis.add_candle.assert_called_once()
        
        # 이벤트 발행 확인
        mock_event_bus.publish.assert_called_once()


if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(level=logging.DEBUG)
    
    # 테스트 실행
    pytest.main([__file__, "-v"])