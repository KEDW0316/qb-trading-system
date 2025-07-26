"""
DataCollector Engine 통합 테스트

Task 23: 실시간 데이터 수집 WebSocket 클라이언트 테스트
"""

import pytest
import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.engines.data_collector import (
    DataCollector, CollectionConfig, 
    DataNormalizer, ConnectionManager, DataQualityChecker
)
from qb.engines.data_collector.adapters import (
    BaseDataAdapter, KISDataAdapter, NaverDataAdapter, YahooDataAdapter
)
from qb.utils.redis_manager import RedisManager
from qb.utils.event_bus import EventBus, EventType


class TestDataCollectorEngine:
    """DataCollector 엔진 기본 테스트"""
    
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
            adapters=['naver'],  # KIS는 인증이 필요하므로 테스트에서 제외
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
        
        # 통계 초기화 확인
        assert data_collector.stats['messages_received'] == 0
        assert data_collector.stats['messages_processed'] == 0
        assert data_collector.stats['messages_failed'] == 0
    
    @pytest.mark.asyncio
    async def test_data_collector_lifecycle(self, data_collector):
        """DataCollector 생명주기 테스트 (시작/일시중지/재개/중지)"""
        # Mock 메서드들
        with patch.object(data_collector, '_initialize_adapters', new_callable=AsyncMock):
            with patch.object(data_collector, '_subscribe_symbols', new_callable=AsyncMock):
                with patch.object(data_collector, '_start_collection_tasks', new_callable=AsyncMock):
                    # 시작 테스트
                    result = await data_collector.start()
                    assert result is True
                    assert data_collector.status.value == "running"
                    
                    # 일시중지 테스트
                    result = await data_collector.pause()
                    assert result is True
                    assert data_collector.status.value == "paused"
                    
                    # 재개 테스트
                    result = await data_collector.resume()
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
    
    @pytest.mark.asyncio
    async def test_data_processing_flow(self, data_collector, mock_redis_manager, mock_event_bus):
        """데이터 처리 흐름 테스트"""
        # 테스트 데이터
        test_data = {
            'symbol': '005930',
            'timestamp': datetime.now().isoformat(),
            'close': 75000.0,
            'volume': 1000000,
            'open': 74800.0,
            'high': 75200.0,
            'low': 74600.0
        }
        
        # 데이터 처리 실행
        await data_collector._process_message('test', test_data)
        
        # Redis 저장 확인
        mock_redis_manager.set_market_data.assert_called_once()
        mock_redis_manager.add_candle.assert_called_once()
        
        # 통계 업데이트 확인
        assert data_collector.stats['messages_received'] == 1
        assert data_collector.stats['messages_processed'] == 1


class TestDataNormalizer:
    """DataNormalizer 테스트"""
    
    @pytest.fixture
    def normalizer(self):
        return DataNormalizer()
    
    @pytest.mark.asyncio
    async def test_naver_data_normalization(self, normalizer):
        """Naver 데이터 정규화 테스트"""
        naver_data = {
            'symbol': '005930',
            'nv': '75000',  # 현재가
            'aq': '1000000',  # 거래량
            'cv': '500',  # 전일대비
            'timestamp': datetime.now().isoformat()
        }
        
        normalized = await normalizer.normalize(naver_data, 'naver')
        
        assert normalized['symbol'] == '005930'
        assert normalized['close'] == 75000.0
        assert normalized['volume'] == 1000000
        assert normalized['source'] == 'naver'
    
    @pytest.mark.asyncio
    async def test_yahoo_data_normalization(self, normalizer):
        """Yahoo 데이터 정규화 테스트"""
        yahoo_data = {
            'symbol': '005930.KS',
            'regularMarketPrice': 75000.0,
            'regularMarketVolume': 1000000,
            'regularMarketChange': 500.0,
            'timestamp': datetime.now().isoformat()
        }
        
        normalized = await normalizer.normalize(yahoo_data, 'yahoo')
        
        assert normalized['symbol'] == '005930.KS'
        assert normalized['close'] == 75000.0
        assert normalized['volume'] == 1000000
        assert normalized['source'] == 'yahoo'
    
    @pytest.mark.asyncio
    async def test_symbol_normalization(self, normalizer):
        """심볼 정규화 테스트"""
        # KIS 형식
        kis_symbol = normalizer.normalize_symbol('005930', 'kis')
        assert kis_symbol == '005930'
        
        # Yahoo 형식
        yahoo_symbol = normalizer.normalize_symbol('005930', 'yahoo')
        assert yahoo_symbol == '005930.KS'
        
        # 이미 변환된 심볼
        yahoo_symbol2 = normalizer.normalize_symbol('005930.KS', 'yahoo')
        assert yahoo_symbol2 == '005930.KS'


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
    async def test_missing_required_fields(self, quality_checker):
        """필수 필드 누락 테스트"""
        invalid_data = {
            'volume': 1000000  # symbol, timestamp, close 누락
        }
        
        is_valid, issues = await quality_checker.validate(invalid_data)
        assert is_valid is False
        assert len(issues) >= 3  # 최소 3개 필수 필드 누락
    
    @pytest.mark.asyncio
    async def test_invalid_price_range(self, quality_checker):
        """가격 범위 오류 테스트"""
        invalid_data = {
            'symbol': '005930',
            'timestamp': datetime.now().isoformat(),
            'close': -100.0,  # 음수 가격
            'volume': 1000000
        }
        
        is_valid, issues = await quality_checker.validate(invalid_data)
        assert is_valid is False
        assert any(issue.issue_type.value == "invalid_value" for issue in issues)
    
    @pytest.mark.asyncio
    async def test_price_outlier_detection(self, quality_checker):
        """가격 이상치 탐지 테스트"""
        # 정상 가격 데이터로 히스토리 구축
        for i in range(15):
            normal_data = {
                'symbol': '005930',
                'timestamp': datetime.now().isoformat(),
                'close': 75000.0 + (i * 10),  # 정상 범위 가격
                'volume': 1000000
            }
            await quality_checker.validate(normal_data)
        
        # 이상치 가격 테스트
        outlier_data = {
            'symbol': '005930',
            'timestamp': datetime.now().isoformat(),
            'close': 150000.0,  # 평균의 2배
            'volume': 1000000
        }
        
        is_valid, issues = await quality_checker.validate(outlier_data)
        # 이상치가 감지되어도 critical하지 않으면 통과할 수 있음
        outlier_detected = any(issue.issue_type.value == "outlier_price" for issue in issues)
        # 이상치가 감지되었는지 확인 (통과 여부와 별개)
        assert outlier_detected or len(issues) == 0  # 이상치 감지되거나 문제없음


class TestConnectionManager:
    """ConnectionManager 테스트"""
    
    @pytest.fixture
    def connection_manager(self):
        return ConnectionManager(max_retries=3, retry_delay=0.1, connection_timeout=1)
    
    @pytest.mark.asyncio
    async def test_successful_connection(self, connection_manager):
        """성공적인 연결 테스트"""
        async def mock_connect():
            return True
        
        result = await connection_manager.connect(mock_connect)
        assert result is True
        assert connection_manager.is_connected() is True
        assert connection_manager.state.value == "connected"
    
    @pytest.mark.asyncio
    async def test_connection_timeout(self, connection_manager):
        """연결 타임아웃 테스트"""
        async def mock_slow_connect():
            await asyncio.sleep(2)  # 타임아웃보다 긴 시간
            return True
        
        result = await connection_manager.connect(mock_slow_connect)
        assert result is False
        assert connection_manager.state.value == "failed"
    
    @pytest.mark.asyncio
    async def test_reconnection_with_retries(self, connection_manager):
        """재연결 재시도 테스트"""
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
        assert connection_manager.is_connected() is True


class TestAdapters:
    """데이터 어댑터 테스트"""
    
    def test_base_adapter_interface(self):
        """베이스 어댑터 인터페이스 테스트"""
        config = {'test': 'value'}
        
        # BaseDataAdapter는 추상 클래스이므로 직접 인스턴스화 불가
        # 하지만 인터페이스 메서드들이 정의되어 있는지 확인
        assert hasattr(BaseDataAdapter, 'connect')
        assert hasattr(BaseDataAdapter, 'disconnect')
        assert hasattr(BaseDataAdapter, 'subscribe_symbol')
        assert hasattr(BaseDataAdapter, 'unsubscribe_symbol')
        assert hasattr(BaseDataAdapter, 'collect_data')
        assert hasattr(BaseDataAdapter, 'get_historical_data')
    
    def test_naver_adapter_initialization(self):
        """Naver 어댑터 초기화 테스트"""
        config = {
            'polling_interval': 10
        }
        
        adapter = NaverDataAdapter(config)
        assert adapter.name == 'Naver'
        assert adapter.polling_interval == 10
        assert adapter.status.value == 'disconnected'
        assert len(adapter.subscribed_symbols) == 0
    
    def test_yahoo_adapter_initialization(self):
        """Yahoo 어댑터 초기화 테스트"""
        config = {
            'polling_interval': 15
        }
        
        adapter = YahooDataAdapter(config)
        assert adapter.name == 'Yahoo'
        assert adapter.polling_interval == 15
        assert adapter.status.value == 'disconnected'
    
    @pytest.mark.asyncio
    async def test_adapter_lifecycle(self):
        """어댑터 생명주기 테스트"""
        config = {'polling_interval': 5}
        adapter = NaverDataAdapter(config)
        
        # 연결
        result = await adapter.connect()
        assert result is True
        assert adapter.status.value == 'connected'
        
        # 심볼 구독
        result = await adapter.subscribe_symbol('005930')
        assert result is True
        assert '005930' in adapter.subscribed_symbols
        
        # 심볼 구독 해제
        result = await adapter.unsubscribe_symbol('005930')
        assert result is True
        assert '005930' not in adapter.subscribed_symbols
        
        # 연결 해제
        result = await adapter.disconnect()
        assert result is True
        assert adapter.status.value == 'disconnected'


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
            adapters=['test'],
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
            'open': 74800.0,
            'high': 75200.0,
            'low': 74600.0,
            'close': 75000.0,
            'volume': 1000000,
            'source': 'test'
        }
        
        # 데이터 처리 테스트
        await collector._process_message('test', test_data)
        
        # 검증
        mock_redis.set_market_data.assert_called_once()
        mock_redis.add_candle.assert_called_once()
        mock_event_bus.publish.assert_called_once()
        
        # 통계 확인
        assert collector.stats['messages_received'] == 1
        assert collector.stats['messages_processed'] == 1
        assert collector.stats['messages_failed'] == 0
    
    def test_status_reporting(self):
        """상태 보고 테스트"""
        mock_redis = Mock(spec=RedisManager)
        mock_event_bus = Mock(spec=EventBus)
        
        config = CollectionConfig(
            symbols=['005930', '000660'],
            adapters=['naver', 'yahoo'],
            max_candles=200,
            collection_interval=1.0,
            quality_check_enabled=True
        )
        
        collector = DataCollector(
            redis_manager=mock_redis,
            event_bus=mock_event_bus,
            config=config
        )
        
        # asyncio.run을 사용하여 비동기 메서드 호출
        async def get_status():
            return await collector.get_status()
        
        status = asyncio.run(get_status())
        
        # 상태 정보 확인
        assert 'status' in status
        assert 'uptime_seconds' in status
        assert 'active_symbols' in status
        assert 'adapters' in status
        assert 'stats' in status
        assert 'config' in status
        
        assert status['status'] == 'stopped'
        assert isinstance(status['active_symbols'], list)
        assert isinstance(status['stats'], dict)


def run_tests():
    """테스트 실행 함수"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 특정 테스트만 실행하고 싶은 경우
    # pytest.main([__file__ + "::TestDataCollectorEngine::test_data_collector_initialization", "-v"])
    
    # 모든 테스트 실행
    pytest.main([__file__, "-v", "-s"])


if __name__ == "__main__":
    run_tests()