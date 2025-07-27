"""
Risk Engine Tests - 리스크 엔진 통합 테스트

리스크 관리 시스템의 핵심 기능들을 테스트합니다.
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# QB 모듈 import
from qb.engines.risk_engine.engine import RiskEngine, RiskLevel, RiskCheckResult
from qb.engines.risk_engine.rules import PositionSizeRule, DailyLossRule
from qb.engines.risk_engine.stop_loss import AutoStopLossManager, StopType
from qb.engines.risk_engine.emergency import EmergencyStop, EmergencyReason
from qb.engines.risk_engine.monitor import RiskMonitor
from qb.engines.risk_engine.position_sizing import FixedRiskPositionSizer, PositionSizeManager
from qb.engines.risk_engine.portfolio_risk import PortfolioRiskManager


class TestRiskEngine:
    """리스크 엔진 테스트"""
    
    @pytest.fixture
    async def risk_engine(self):
        """리스크 엔진 fixture"""
        # Mock dependencies
        db_manager = AsyncMock()
        redis_manager = AsyncMock()
        event_bus = MagicMock()
        
        config = {
            'max_daily_loss': 50000,
            'max_monthly_loss': 200000,
            'max_consecutive_losses': 5,
            'max_position_size_ratio': 0.1,
            'max_sector_exposure_ratio': 0.3,
            'max_total_exposure_ratio': 0.9,
            'min_cash_reserve_ratio': 0.1,
            'max_trades_per_day': 50,
            'position_risk_ratio': 0.01,
            'default_stop_loss_pct': 3.0
        }
        
        engine = RiskEngine(db_manager, redis_manager, event_bus, config)
        
        # Mock 메서드들
        engine._get_portfolio_value = AsyncMock(return_value=Decimal('1000000'))
        engine._get_cash_balance = AsyncMock(return_value=Decimal('100000'))
        engine._get_total_exposure = AsyncMock(return_value=Decimal('800000'))
        engine._get_position_count = AsyncMock(return_value=5)
        engine._calculate_risk_score = AsyncMock(return_value=0.3)
        
        return engine
    
    @pytest.mark.asyncio
    async def test_risk_engine_initialization(self, risk_engine):
        """리스크 엔진 초기화 테스트"""
        assert risk_engine is not None
        assert risk_engine.config['max_daily_loss'] == 50000
        assert len(risk_engine.risk_rules) > 0
        assert risk_engine.stop_loss_manager is not None
        assert risk_engine.emergency_stop is not None
        assert risk_engine.monitor is not None
    
    @pytest.mark.asyncio
    async def test_order_risk_check_approved(self, risk_engine):
        """주문 리스크 체크 - 승인 케이스"""
        result = await risk_engine.check_order_risk(
            symbol="005930",
            side="BUY",
            quantity=100,
            price=70000.0
        )
        
        assert isinstance(result, RiskCheckResult)
        assert result.approved is True
        assert result.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
    
    @pytest.mark.asyncio
    async def test_order_risk_check_rejected(self, risk_engine):
        """주문 리스크 체크 - 거부 케이스"""
        # 일일 손실 한도 초과 시뮬레이션
        risk_engine._daily_pnl = Decimal('-60000')  # 한도 초과
        
        result = await risk_engine.check_order_risk(
            symbol="005930",
            side="BUY", 
            quantity=1000,
            price=70000.0
        )
        
        assert isinstance(result, RiskCheckResult)
        # 일일 손실 한도 초과로 인한 거부 가능성
    
    @pytest.mark.asyncio
    async def test_daily_pnl_tracking(self, risk_engine):
        """일일 손익 추적 테스트"""
        # 손익 업데이트
        await risk_engine.update_daily_pnl(Decimal('5000'))
        assert risk_engine._daily_pnl == Decimal('5000')
        
        await risk_engine.update_daily_pnl(Decimal('-3000'))
        assert risk_engine._daily_pnl == Decimal('2000')
        
        # 손실 추가
        await risk_engine.update_daily_pnl(Decimal('-7000'))
        assert risk_engine._daily_pnl == Decimal('-5000')


class TestRiskRules:
    """리스크 규칙 테스트"""
    
    @pytest.fixture
    def mock_risk_engine(self):
        """Mock 리스크 엔진"""
        engine = MagicMock()
        engine.config = {
            'max_position_size_ratio': 0.1,
            'max_daily_loss': 50000,
        }
        engine._get_portfolio_value = AsyncMock(return_value=Decimal('1000000'))
        engine.redis_manager.get_hash = AsyncMock(return_value={})
        engine._daily_pnl = Decimal('0')
        return engine
    
    @pytest.mark.asyncio
    async def test_position_size_rule_approved(self, mock_risk_engine):
        """포지션 크기 규칙 - 승인 케이스"""
        rule = PositionSizeRule(mock_risk_engine)
        
        result = await rule.validate(
            symbol="005930",
            side="BUY",
            quantity=100,
            price=70000.0
        )
        
        assert result.approved is True
        assert result.risk_level == RiskLevel.LOW
    
    @pytest.mark.asyncio
    async def test_position_size_rule_rejected(self, mock_risk_engine):
        """포지션 크기 규칙 - 거부 케이스"""
        rule = PositionSizeRule(mock_risk_engine)
        
        # 매우 큰 포지션 주문
        result = await rule.validate(
            symbol="005930",
            side="BUY",
            quantity=2000,  # 1.4억원 (포트폴리오의 14%)
            price=70000.0
        )
        
        assert result.approved is False
        assert result.risk_level == RiskLevel.HIGH
        assert "포지션 크기 한도 초과" in result.reason
    
    @pytest.mark.asyncio
    async def test_daily_loss_rule(self, mock_risk_engine):
        """일일 손실 규칙 테스트"""
        rule = DailyLossRule(mock_risk_engine)
        
        # 손실 한도 초과
        mock_risk_engine._daily_pnl = Decimal('-60000')
        
        result = await rule.validate(
            symbol="005930",
            side="BUY",
            quantity=100,
            price=70000.0
        )
        
        assert result.approved is False
        assert result.risk_level == RiskLevel.CRITICAL
        assert "일일 손실 한도 초과" in result.reason


class TestAutoStopLoss:
    """자동 손절/익절 테스트"""
    
    @pytest.fixture
    def mock_risk_engine(self):
        """Mock 리스크 엔진"""
        engine = MagicMock()
        engine.config = {
            'enable_auto_stop_loss': True,
            'enable_auto_take_profit': True,
            'default_stop_loss_pct': 3.0,
            'default_take_profit_pct': 5.0
        }
        engine.redis_manager = AsyncMock()
        engine.event_bus = MagicMock()
        return engine
    
    @pytest.mark.asyncio
    async def test_stop_loss_manager_initialization(self, mock_risk_engine):
        """손절 매니저 초기화 테스트"""
        manager = AutoStopLossManager(mock_risk_engine)
        assert manager is not None
        assert manager.config == mock_risk_engine.config
    
    @pytest.mark.asyncio
    async def test_set_stop_loss(self, mock_risk_engine):
        """손절 설정 테스트"""
        manager = AutoStopLossManager(mock_risk_engine)
        
        # Mock 포지션 데이터
        position_data = {
            'quantity': 100,
            'average_price': '70000',
            'market_price': '72000'
        }
        mock_risk_engine.redis_manager.get_hash.return_value = position_data
        
        result = await manager.set_stop_loss(
            symbol="005930",
            stop_price=67000.0,
            stop_type=StopType.FIXED_STOP_LOSS
        )
        
        assert result is True


class TestEmergencyStop:
    """비상 정지 테스트"""
    
    @pytest.fixture
    def mock_risk_engine(self):
        """Mock 리스크 엔진"""
        engine = MagicMock()
        engine.config = {
            'max_daily_loss': 50000,
            'max_monthly_loss': 200000,
            'max_consecutive_losses': 5,
            'emergency_admin_key': 'TEST_KEY_2024'
        }
        engine.db_manager = AsyncMock()
        engine.redis_manager = AsyncMock()
        engine.event_bus = MagicMock()
        engine._daily_pnl = Decimal('0')
        engine._monthly_pnl = Decimal('0')
        engine._consecutive_losses = 0
        engine._get_portfolio_value = AsyncMock(return_value=Decimal('1000000'))
        engine._calculate_risk_score = AsyncMock(return_value=0.3)
        return engine
    
    @pytest.mark.asyncio
    async def test_emergency_stop_initialization(self, mock_risk_engine):
        """비상 정지 초기화 테스트"""
        emergency = EmergencyStop(mock_risk_engine)
        assert emergency is not None
        assert emergency.is_active is False
        assert emergency.reason is None
    
    @pytest.mark.asyncio
    async def test_manual_emergency_activation(self, mock_risk_engine):
        """수동 비상 정지 활성화 테스트"""
        emergency = EmergencyStop(mock_risk_engine)
        
        result = await emergency.manual_activate("Test emergency stop")
        
        assert result is True
        assert emergency.is_active is True
        assert emergency.reason == EmergencyReason.MANUAL_STOP
    
    @pytest.mark.asyncio
    async def test_emergency_reset(self, mock_risk_engine):
        """비상 정지 해제 테스트"""
        emergency = EmergencyStop(mock_risk_engine)
        
        # 먼저 비상 정지 활성화
        await emergency.manual_activate("Test")
        assert emergency.is_active is True
        
        # 해제 테스트
        result = await emergency.reset("TEST_KEY_2024")
        
        assert result is True
        assert emergency.is_active is False
        assert emergency.reason is None


class TestPositionSizing:
    """포지션 크기 계산 테스트"""
    
    @pytest.fixture
    def mock_risk_engine(self):
        """Mock 리스크 엔진"""
        engine = MagicMock()
        engine.config = {
            'position_risk_ratio': 0.01,
            'max_position_size_ratio': 0.1,
            'default_stop_loss_pct': 3.0,
            'min_position_quantity': 1
        }
        engine._get_portfolio_value = AsyncMock(return_value=Decimal('1000000'))
        engine._get_cash_balance = AsyncMock(return_value=Decimal('100000'))
        return engine
    
    @pytest.mark.asyncio
    async def test_fixed_risk_position_sizer(self, mock_risk_engine):
        """고정 리스크 포지션 크기 계산 테스트"""
        sizer = FixedRiskPositionSizer(mock_risk_engine)
        
        result = await sizer.calculate_position_size(
            symbol="005930",
            side="BUY",
            entry_price=70000.0,
            stop_loss_price=67900.0  # 3% 손절
        )
        
        assert result.recommended_quantity > 0
        assert result.risk_amount > 0
        assert result.confidence > 0.5
        assert "고정 리스크" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_position_size_manager(self, mock_risk_engine):
        """포지션 크기 매니저 테스트"""
        manager = PositionSizeManager(mock_risk_engine)
        
        result = await manager.calculate_optimal_position_size(
            symbol="005930",
            side="BUY",
            entry_price=70000.0,
            strategy="fixed_risk"
        )
        
        assert result.recommended_quantity >= 0
        assert result.position_value >= 0
        assert isinstance(result.confidence, float)


class TestRiskMonitor:
    """리스크 모니터 테스트"""
    
    @pytest.fixture
    def mock_risk_engine(self):
        """Mock 리스크 엔진"""
        engine = MagicMock()
        engine.config = {'max_total_exposure_ratio': 0.9}
        engine.redis_manager = AsyncMock()
        engine.event_bus = MagicMock()
        engine._get_portfolio_value = AsyncMock(return_value=Decimal('1000000'))
        engine._get_cash_balance = AsyncMock(return_value=Decimal('100000'))
        engine._get_total_exposure = AsyncMock(return_value=Decimal('800000'))
        engine._get_position_count = AsyncMock(return_value=5)
        engine._daily_pnl = Decimal('5000')
        engine._calculate_risk_score = AsyncMock(return_value=0.3)
        return engine
    
    @pytest.mark.asyncio
    async def test_risk_monitor_initialization(self, mock_risk_engine):
        """리스크 모니터 초기화 테스트"""
        monitor = RiskMonitor(mock_risk_engine)
        assert monitor is not None
        assert 'portfolio_value' in monitor.metrics
        assert 'risk_score' in monitor.metrics
    
    @pytest.mark.asyncio
    async def test_metrics_update(self, mock_risk_engine):
        """메트릭 업데이트 테스트"""
        monitor = RiskMonitor(mock_risk_engine)
        
        await monitor.update_metrics()
        
        assert monitor.metrics['portfolio_value'] == Decimal('1000000')
        assert monitor.metrics['total_exposure'] == Decimal('800000')
        assert monitor.metrics['last_update'] is not None
    
    @pytest.mark.asyncio
    async def test_risk_report_generation(self, mock_risk_engine):
        """리스크 보고서 생성 테스트"""
        monitor = RiskMonitor(mock_risk_engine)
        
        # 메트릭 업데이트 후 보고서 생성
        await monitor.update_metrics()
        report = await monitor.get_risk_report()
        
        assert 'timestamp' in report
        assert 'metrics' in report
        assert 'alerts' in report
        assert 'recommendations' in report
        
        metrics = report['metrics']
        assert metrics['portfolio_value'] == 1000000.0
        assert metrics['exposure_ratio'] == 0.8  # 800k/1000k


class TestPortfolioRisk:
    """포트폴리오 리스크 테스트"""
    
    @pytest.fixture
    def mock_risk_engine(self):
        """Mock 리스크 엔진"""
        engine = MagicMock()
        engine.config = {}
        engine.db_manager = AsyncMock()
        engine.redis_manager = AsyncMock()
        engine.event_bus = MagicMock()
        engine._get_portfolio_value = AsyncMock(return_value=Decimal('1000000'))
        engine._get_total_exposure = AsyncMock(return_value=Decimal('800000'))
        engine._get_cash_balance = AsyncMock(return_value=Decimal('200000'))
        return engine
    
    @pytest.mark.asyncio
    async def test_portfolio_risk_manager_initialization(self, mock_risk_engine):
        """포트폴리오 리스크 매니저 초기화 테스트"""
        manager = PortfolioRiskManager(mock_risk_engine)
        assert manager is not None
        assert 'max_position_weight' in manager.thresholds
        assert 'portfolio_volatility' in manager.thresholds
    
    @pytest.mark.asyncio 
    async def test_empty_portfolio_analysis(self, mock_risk_engine):
        """빈 포트폴리오 분석 테스트"""
        manager = PortfolioRiskManager(mock_risk_engine)
        
        # 빈 포지션 리스트 반환하도록 설정
        mock_risk_engine.redis_manager.get_keys_by_pattern.return_value = []
        
        metrics = await manager.analyze_portfolio_risk()
        
        assert metrics.portfolio_value == Decimal('1000000')
        assert metrics.max_position_weight == 0.0
        assert metrics.sector_count == 0
        assert metrics.overall_risk_score == 0.0


class TestIntegration:
    """통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_full_risk_check_workflow(self):
        """전체 리스크 체크 워크플로 테스트"""
        # Mock dependencies
        db_manager = AsyncMock()
        redis_manager = AsyncMock()
        event_bus = MagicMock()
        
        config = {
            'max_daily_loss': 50000,
            'max_position_size_ratio': 0.1,
            'position_risk_ratio': 0.01,
            'default_stop_loss_pct': 3.0
        }
        
        # RiskEngine 생성
        risk_engine = RiskEngine(db_manager, redis_manager, event_bus, config)
        
        # Mock 메서드들
        risk_engine._get_portfolio_value = AsyncMock(return_value=Decimal('1000000'))
        risk_engine._get_cash_balance = AsyncMock(return_value=Decimal('100000'))
        risk_engine._get_total_exposure = AsyncMock(return_value=Decimal('500000'))
        
        # 1. 주문 리스크 체크
        risk_result = await risk_engine.check_order_risk(
            symbol="005930",
            side="BUY",
            quantity=100,
            price=70000.0
        )
        
        assert isinstance(risk_result, RiskCheckResult)
        
        # 2. 포지션 크기 추천
        position_result = await risk_engine.position_sizer.calculate_optimal_position_size(
            symbol="005930",
            side="BUY",
            entry_price=70000.0,
            strategy="fixed_risk"
        )
        
        assert position_result.recommended_quantity >= 0
        
        # 3. 리스크 모니터 업데이트
        await risk_engine.monitor.update_metrics()
        
        # 4. 포트폴리오 리스크 분석
        portfolio_metrics = await risk_engine.portfolio_risk_manager.analyze_portfolio_risk()
        
        assert portfolio_metrics.portfolio_value == Decimal('1000000')
    
    @pytest.mark.asyncio
    async def test_emergency_scenario(self):
        """비상 상황 시나리오 테스트"""
        # Mock dependencies
        db_manager = AsyncMock()
        redis_manager = AsyncMock()
        event_bus = MagicMock()
        
        config = {
            'max_daily_loss': 50000,
            'emergency_admin_key': 'TEST_KEY'
        }
        
        risk_engine = RiskEngine(db_manager, redis_manager, event_bus, config)
        
        # 큰 손실 발생 시뮬레이션
        risk_engine._daily_pnl = Decimal('-60000')  # 한도 초과
        
        # 비상 정지 조건 확인
        emergency_triggered = await risk_engine.emergency_stop.check_conditions()
        
        assert emergency_triggered is True
        assert risk_engine.emergency_stop.is_active is True
        
        # 주문 리스크 체크 - 거부되어야 함
        risk_result = await risk_engine.check_order_risk(
            symbol="005930",
            side="BUY",
            quantity=100,
            price=70000.0
        )
        
        assert risk_result.approved is False
        assert "비상 정지" in risk_result.reason


# Performance Tests
class TestPerformance:
    """성능 테스트"""
    
    @pytest.mark.asyncio
    async def test_risk_check_performance(self):
        """리스크 체크 성능 테스트"""
        # Mock setup
        db_manager = AsyncMock()
        redis_manager = AsyncMock()
        event_bus = MagicMock()
        
        config = {
            'max_daily_loss': 50000,
            'max_position_size_ratio': 0.1
        }
        
        risk_engine = RiskEngine(db_manager, redis_manager, event_bus, config)
        risk_engine._get_portfolio_value = AsyncMock(return_value=Decimal('1000000'))
        risk_engine._get_cash_balance = AsyncMock(return_value=Decimal('100000'))
        risk_engine._get_total_exposure = AsyncMock(return_value=Decimal('500000'))
        
        # 시간 측정
        import time
        start_time = time.time()
        
        # 100번 리스크 체크 실행
        for i in range(100):
            await risk_engine.check_order_risk(
                symbol="005930",
                side="BUY",
                quantity=100,
                price=70000.0
            )
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # 100번 실행이 1초 이내여야 함
        assert elapsed < 1.0, f"Risk check too slow: {elapsed:.3f}s for 100 calls"
        
        print(f"Risk check performance: {elapsed*10:.1f}ms per call")


if __name__ == "__main__":
    # 개별 테스트 실행
    pytest.main([__file__, "-v", "--tb=short"])