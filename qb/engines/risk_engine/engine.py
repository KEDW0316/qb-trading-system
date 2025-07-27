"""
Risk Engine - 실시간 리스크 관리 시스템

QB Trading System의 핵심 리스크 관리 엔진입니다.
RPC 스타일로 주문 실행 전 리스크 체크를 수행하고,
실시간 포지션 모니터링 및 자동 손절/익절 기능을 제공합니다.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from ...utils.event_bus import EventBus, EventType
from ...utils.redis_manager import RedisManager
from ...database.connection import DatabaseManager

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """리스크 레벨 정의"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskCheckResult:
    """리스크 체크 결과"""
    approved: bool
    reason: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW
    suggested_quantity: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RiskMetrics:
    """리스크 지표"""
    portfolio_value: Decimal
    cash_balance: Decimal
    total_exposure: Decimal
    daily_pnl: Decimal
    monthly_pnl: Decimal
    position_count: int
    max_position_value: Decimal
    risk_score: float
    leverage_ratio: float
    updated_at: datetime


class RiskEngine:
    """
    리스크 관리 엔진
    
    주요 기능:
    1. RPC 스타일 주문 사전 리스크 체크
    2. 실시간 포지션 리스크 모니터링
    3. 자동 손절/익절 트리거
    4. 일일/월간 손실 한도 관리
    5. 비상 정지 시스템
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        redis_manager: RedisManager,
        event_bus: EventBus,
        config: Optional[Dict[str, Any]] = None
    ):
        self.db_manager = db_manager
        self.redis_manager = redis_manager
        self.event_bus = event_bus
        self.config = config or self._get_default_config()
        
        # 런타임 상태
        self._running = False
        self._daily_pnl = Decimal('0')
        self._monthly_pnl = Decimal('0')
        self._consecutive_losses = 0
        self._trade_count_today = 0
        self._last_trade_times: Dict[str, datetime] = {}  # 종목별 마지막 거래 시간
        
        # 컴포넌트 지연 로딩
        self._risk_rules = None
        self._stop_loss_manager = None
        self._risk_monitor = None
        self._emergency_stop = None
        
        logger.info("RiskEngine initialized")
    
    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """기본 리스크 설정"""
        return {
            # 포지션 제한
            'max_position_size_ratio': 0.2,  # 종목당 최대 투자 비율 (포트폴리오 대비)
            'max_sector_exposure_ratio': 0.3,  # 섹터별 최대 투자 비율
            'max_total_exposure_ratio': 0.9,  # 전체 최대 투자 비율 (현금 제외)
            'min_cash_reserve_ratio': 0.1,   # 최소 현금 보유 비율
            
            # 손절/익절
            'default_stop_loss_pct': 3.0,    # 기본 손절 비율 (%)
            'default_take_profit_pct': 5.0,  # 기본 익절 비율 (%)
            'trailing_stop_pct': 2.0,        # 트레일링 스탑 비율 (%)
            'enable_auto_stop_loss': True,   # 자동 손절 활성화
            'enable_auto_take_profit': False, # 자동 익절 활성화
            
            # 손실 한도
            'max_daily_loss': 50000,         # 일일 최대 손실 금액 (원)
            'max_monthly_loss': 500000,      # 월간 최대 손실 금액 (원)
            'max_consecutive_losses': 5,     # 최대 연속 손실 횟수
            
            # 거래 제한
            'max_trades_per_day': 20,        # 하루 최대 거래 횟수
            'min_order_interval': 60,        # 동일 종목 최소 주문 간격 (초)
            'min_order_value': 10000,        # 최소 주문 금액 (원)
            'max_order_value': 1000000,      # 최대 주문 금액 (원)
            
            # 알림 임계값
            'risk_alert_threshold': 0.8,     # 리스크 한도 알림 임계값
            'high_risk_threshold': 0.9,      # 고위험 임계값
            
            # 시스템 설정
            'risk_check_timeout': 5.0,       # 리스크 체크 타임아웃 (초)
            'enable_risk_monitoring': True,  # 리스크 모니터링 활성화
            'monitoring_interval': 30,       # 모니터링 주기 (초)
        }
    
    async def start(self):
        """리스크 엔진 시작"""
        if self._running:
            logger.warning("RiskEngine is already running")
            return
        
        try:
            # 컴포넌트 초기화
            await self._initialize_components()
            
            # 이벤트 구독
            self.event_bus.subscribe(EventType.ORDER_EXECUTED, self._handle_order_executed)
            self.event_bus.subscribe(EventType.MARKET_DATA_RECEIVED, self._handle_market_data)
            
            # 모니터링 태스크 시작
            if self.config['enable_risk_monitoring']:
                asyncio.create_task(self._monitoring_loop())
            
            # 일일 데이터 로드
            await self._load_daily_data()
            
            self._running = True
            logger.info("RiskEngine started successfully")
            
            # 시작 이벤트 발행
            await self._publish_event(EventType.SYSTEM_STATUS, {
                "component": "RiskEngine",
                "status": "started",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to start RiskEngine: {e}")
            raise
    
    async def stop(self):
        """리스크 엔진 중지"""
        if not self._running:
            return
        
        self._running = False
        
        try:
            # 이벤트 구독 해제
            self.event_bus.unsubscribe(EventType.ORDER_EXECUTED, self._handle_order_executed)
            self.event_bus.unsubscribe(EventType.MARKET_DATA_RECEIVED, self._handle_market_data)
            
            logger.info("RiskEngine stopped successfully")
            
            # 중지 이벤트 발행
            await self._publish_event(EventType.SYSTEM_STATUS, {
                "component": "RiskEngine",
                "status": "stopped",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error stopping RiskEngine: {e}")
    
    async def check_order_risk(
        self,
        symbol: str,
        side: str,  # 'BUY' or 'SELL'
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """
        RPC 스타일 주문 리스크 체크
        
        주문 실행 전 모든 리스크 규칙을 검증하고 승인/거부를 결정합니다.
        """
        start_time = datetime.now()
        
        try:
            logger.debug(f"Checking order risk: {side} {quantity} {symbol} @ {price}")
            
            # 기본 유효성 검증
            basic_check = await self._basic_validation(symbol, side, quantity, price)
            if not basic_check.approved:
                return basic_check
            
            # 비상 정지 상태 확인
            if await self._emergency_stop.check_conditions():
                return RiskCheckResult(
                    approved=False,
                    reason="시스템 비상 정지 상태",
                    risk_level=RiskLevel.CRITICAL
                )
            
            # 각 리스크 규칙 검증
            for rule in self._risk_rules:
                result = await rule.validate(symbol, side, quantity, price, metadata)
                if not result.approved:
                    logger.warning(f"Risk rule failed: {rule.__class__.__name__} - {result.reason}")
                    await self._publish_risk_alert(result.reason, symbol, result.risk_level)
                    return result
            
            # 모든 검증 통과
            logger.debug(f"Order risk check passed for {symbol}")
            return RiskCheckResult(approved=True, risk_level=RiskLevel.LOW)
            
        except Exception as e:
            logger.error(f"Error in order risk check: {e}")
            return RiskCheckResult(
                approved=False,
                reason=f"리스크 체크 오류: {str(e)}",
                risk_level=RiskLevel.CRITICAL
            )
        finally:
            # 성능 모니터링
            duration = (datetime.now() - start_time).total_seconds()
            timeout = self.config.get('risk_check_timeout', 1.0)
            if duration > timeout:
                logger.warning(f"Risk check timeout: {duration:.2f}s > {timeout}s")
    
    async def update_position_risk(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """
        포지션 리스크 업데이트 및 자동 손절/익절 체크
        
        Args:
            symbol: 종목 코드
            current_price: 현재 가격
            
        Returns:
            Dict: 실행된 액션 정보 (손절/익절 주문 등)
        """
        try:
            if not self._stop_loss_manager:
                return None
            
            return await self._stop_loss_manager.check_positions(symbol, current_price)
            
        except Exception as e:
            logger.error(f"Error updating position risk for {symbol}: {e}")
            return None
    
    async def update_daily_pnl(self, trade_pnl: Decimal) -> bool:
        """
        일일 손익 업데이트 및 한도 체크
        
        Args:
            trade_pnl: 거래 손익
            
        Returns:
            bool: 일일 손실 한도 초과 여부
        """
        try:
            self._daily_pnl += trade_pnl
            
            # 연속 손실 추적
            if trade_pnl < 0:
                self._consecutive_losses += 1
            else:
                self._consecutive_losses = 0
            
            # Redis에 저장
            await self._save_daily_pnl()
            
            # 한도 접근 알림
            max_loss = Decimal(self.config['max_daily_loss'])
            current_loss = abs(self._daily_pnl) if self._daily_pnl < 0 else Decimal('0')
            
            alert_threshold = Decimal(self.config.get('risk_alert_threshold', 0.8))
            if current_loss > max_loss * alert_threshold:
                await self._publish_risk_alert(
                    f"일일 손실 한도 {alert_threshold*100:.0f}% 접근: {current_loss:,.0f}원",
                    "SYSTEM",
                    RiskLevel.HIGH
                )
            
            # 한도 초과 확인
            limit_exceeded = current_loss >= max_loss
            if limit_exceeded:
                await self._publish_risk_alert(
                    f"일일 손실 한도 초과: {current_loss:,.0f}원 >= {max_loss:,.0f}원",
                    "SYSTEM",
                    RiskLevel.CRITICAL
                )
            
            return limit_exceeded
            
        except Exception as e:
            logger.error(f"Error updating daily PnL: {e}")
            return False
    
    async def update_monthly_pnl(self, trade_pnl: Decimal) -> bool:
        """
        월간 손익 업데이트 및 한도 체크
        
        Args:
            trade_pnl: 거래 손익
            
        Returns:
            bool: 월간 손실 한도 초과 여부
        """
        try:
            self._monthly_pnl += trade_pnl
            
            # Redis에 저장
            await self._save_monthly_pnl()
            
            # 한도 접근 알림
            max_loss = Decimal(self.config['max_monthly_loss'])
            current_loss = abs(self._monthly_pnl) if self._monthly_pnl < 0 else Decimal('0')
            
            alert_threshold = Decimal(self.config.get('risk_alert_threshold', 0.8))
            if current_loss > max_loss * alert_threshold:
                await self._publish_risk_alert(
                    f"월간 손실 한도 {alert_threshold*100:.0f}% 접근: {current_loss:,.0f}원",
                    "SYSTEM",
                    RiskLevel.HIGH
                )
            
            # 한도 초과 확인
            limit_exceeded = current_loss >= max_loss
            if limit_exceeded:
                await self._publish_risk_alert(
                    f"월간 손실 한도 초과: {current_loss:,.0f}원 >= {max_loss:,.0f}원",
                    "SYSTEM",
                    RiskLevel.CRITICAL
                )
            
            return limit_exceeded
            
        except Exception as e:
            logger.error(f"Error updating monthly PnL: {e}")
            return False
    
    async def update_consecutive_losses(self, is_loss: bool):
        """
        연속 손실 횟수 업데이트
        
        Args:
            is_loss: 손실 여부 (True: 손실, False: 수익)
        """
        try:
            if is_loss:
                self._consecutive_losses += 1
            else:
                self._consecutive_losses = 0  # 수익 시 리셋
            
            # Redis에 저장
            await self.redis_manager.set(
                "risk_metrics:consecutive_losses",
                str(self._consecutive_losses),
                ttl=86400
            )
            
            logger.info(f"Consecutive losses updated: {self._consecutive_losses}")
            
        except Exception as e:
            logger.error(f"Error updating consecutive losses: {e}")
    
    async def should_stop_trading(self) -> Tuple[bool, Optional[str]]:
        """
        거래 중단 여부 결정
        
        Returns:
            Tuple[bool, str]: (중단 여부, 중단 이유)
        """
        try:
            if not self._emergency_stop:
                return False, None
            
            is_emergency = await self._emergency_stop.check_conditions()
            reason = self._emergency_stop.reason if is_emergency else None
            
            return is_emergency, reason
            
        except Exception as e:
            logger.error(f"Error checking stop trading conditions: {e}")
            return True, f"리스크 체크 오류: {str(e)}"
    
    async def get_risk_metrics(self) -> RiskMetrics:
        """현재 리스크 지표 조회"""
        try:
            # 포트폴리오 정보 조회
            portfolio_value = await self._get_portfolio_value()
            cash_balance = await self._get_cash_balance()
            total_exposure = await self._get_total_exposure()
            position_count = await self._get_position_count()
            max_position_value = await self._get_max_position_value()
            
            # 리스크 점수 계산
            risk_score = await self._calculate_risk_score()
            
            # 레버리지 비율 계산
            leverage_ratio = float(total_exposure / portfolio_value) if portfolio_value > 0 else 0.0
            
            return RiskMetrics(
                portfolio_value=portfolio_value,
                cash_balance=cash_balance,
                total_exposure=total_exposure,
                daily_pnl=self._daily_pnl,
                monthly_pnl=self._monthly_pnl,
                position_count=position_count,
                max_position_value=max_position_value,
                risk_score=risk_score,
                leverage_ratio=leverage_ratio,
                updated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error getting risk metrics: {e}")
            raise
    
    async def get_engine_status(self) -> Dict[str, Any]:
        """엔진 상태 조회"""
        try:
            risk_metrics = await self.get_risk_metrics()
            
            return {
                "running": self._running,
                "daily_pnl": float(self._daily_pnl),
                "monthly_pnl": float(self._monthly_pnl),
                "consecutive_losses": self._consecutive_losses,
                "trade_count_today": self._trade_count_today,
                "risk_metrics": asdict(risk_metrics),
                "config": self.config,
                "emergency_stop": {
                    "active": self._emergency_stop.is_active if self._emergency_stop else False,
                    "reason": self._emergency_stop.reason if self._emergency_stop else None
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting engine status: {e}")
            return {"running": self._running, "error": str(e)}
    
    # Private Methods
    
    async def _initialize_components(self):
        """컴포넌트 초기화 (지연 로딩)"""
        # 다른 모듈들을 여기서 import하여 순환 import 방지
        from .rules import get_risk_rules
        from .stop_loss import AutoStopLossManager
        from .monitor import RiskMonitor
        from .emergency import EmergencyStop
        from .position_sizing import PositionSizeManager
        from .portfolio_risk import PortfolioRiskManager
        
        self._risk_rules = get_risk_rules(self)
        self._stop_loss_manager = AutoStopLossManager(self)
        self._risk_monitor = RiskMonitor(self)
        self._emergency_stop = EmergencyStop(self)
        self._position_sizer = PositionSizeManager(self)
        self._portfolio_risk_manager = PortfolioRiskManager(self)
        
        # 별칭 설정 (호환성)
        self.risk_rules = self._risk_rules
        self.stop_loss_manager = self._stop_loss_manager
        self.monitor = self._risk_monitor
        self.emergency_stop = self._emergency_stop
        self.position_sizer = self._position_sizer
        self.portfolio_risk_manager = self._portfolio_risk_manager
        
        logger.info("Risk engine components initialized")
    
    async def _basic_validation(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float
    ) -> RiskCheckResult:
        """기본 유효성 검증"""
        
        # 수량 검증
        if quantity <= 0:
            return RiskCheckResult(
                approved=False,
                reason="주문 수량이 0 이하입니다",
                risk_level=RiskLevel.HIGH
            )
        
        # 가격 검증
        if price <= 0:
            return RiskCheckResult(
                approved=False,
                reason="주문 가격이 0 이하입니다",
                risk_level=RiskLevel.HIGH
            )
        
        # 주문 금액 검증
        order_value = quantity * price
        min_value = self.config.get('min_order_value', 10000)
        max_value = self.config.get('max_order_value', 100000000)
        
        if order_value < min_value:
            return RiskCheckResult(
                approved=False,
                reason=f"최소 주문 금액 미달: {order_value:,.0f}원 < {min_value:,.0f}원",
                risk_level=RiskLevel.MEDIUM
            )
        
        if order_value > max_value:
            return RiskCheckResult(
                approved=False,
                reason=f"최대 주문 금액 초과: {order_value:,.0f}원 > {max_value:,.0f}원",
                risk_level=RiskLevel.HIGH
            )
        
        # 거래 빈도 검증
        if side == 'BUY':
            last_trade_time = self._last_trade_times.get(symbol)
            if last_trade_time:
                time_diff = (datetime.now() - last_trade_time).total_seconds()
                min_interval = self.config['min_order_interval']
                
                if time_diff < min_interval:
                    return RiskCheckResult(
                        approved=False,
                        reason=f"주문 간격 부족: {time_diff:.0f}초 < {min_interval}초",
                        risk_level=RiskLevel.MEDIUM
                    )
        
        return RiskCheckResult(approved=True)
    
    async def _monitoring_loop(self):
        """리스크 모니터링 루프"""
        logger.info("Risk monitoring loop started")
        
        while self._running:
            try:
                await asyncio.sleep(self.config['monitoring_interval'])
                
                if self._risk_monitor:
                    await self._risk_monitor.update_metrics()
                
            except Exception as e:
                logger.error(f"Error in risk monitoring loop: {e}")
                await asyncio.sleep(5)
        
        logger.info("Risk monitoring loop stopped")
    
    async def _handle_order_executed(self, event_data: Dict[str, Any]):
        """주문 체결 이벤트 처리"""
        try:
            fill_data = event_data.get("fill", {})
            symbol = fill_data.get("symbol")
            side = fill_data.get("side")
            
            # 거래 횟수 업데이트
            self._trade_count_today += 1
            
            # 마지막 거래 시간 업데이트
            if symbol and side == 'BUY':
                self._last_trade_times[symbol] = datetime.now()
            
            # 일일 거래 한도 체크
            if self._trade_count_today >= self.config['max_trades_per_day']:
                await self._publish_risk_alert(
                    f"일일 거래 한도 달성: {self._trade_count_today}회",
                    "SYSTEM",
                    RiskLevel.HIGH
                )
            
        except Exception as e:
            logger.error(f"Error handling order executed event: {e}")
    
    async def _handle_market_data(self, event_data: Dict[str, Any]):
        """시장 데이터 이벤트 처리"""
        try:
            market_data = event_data.get("data", {})
            symbol = market_data.get("symbol")
            close_price = market_data.get("close")
            
            if symbol and close_price:
                # 포지션 리스크 업데이트
                await self.update_position_risk(symbol, float(close_price))
            
        except Exception as e:
            logger.error(f"Error handling market data event: {e}")
    
    async def _load_daily_data(self):
        """일일 데이터 로드"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Redis에서 일일 손익 로드
            daily_pnl_key = f"risk_metrics:daily_pnl:{today}"
            daily_pnl = await self.redis_manager.get(daily_pnl_key)
            if daily_pnl:
                self._daily_pnl = Decimal(daily_pnl)
            
            # 거래 횟수 로드
            trade_count_key = f"risk_metrics:trade_count:{today}"
            trade_count = await self.redis_manager.get(trade_count_key)
            if trade_count:
                self._trade_count_today = int(trade_count)
            
            logger.info(f"Daily data loaded: PnL={self._daily_pnl}, Trades={self._trade_count_today}")
            
        except Exception as e:
            logger.error(f"Error loading daily data: {e}")
    
    async def _save_daily_pnl(self):
        """일일 손익 저장"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            daily_pnl_key = f"risk_metrics:daily_pnl:{today}"
            await self.redis_manager.set(daily_pnl_key, str(self._daily_pnl), ttl=86400)
            
        except Exception as e:
            logger.error(f"Error saving daily PnL: {e}")
    
    async def _save_monthly_pnl(self):
        """월간 손익 저장"""
        try:
            month = datetime.now().strftime('%Y-%m')
            monthly_pnl_key = f"risk_metrics:monthly_pnl:{month}"
            await self.redis_manager.set(monthly_pnl_key, str(self._monthly_pnl), ttl=86400*31)
            
        except Exception as e:
            logger.error(f"Error saving monthly PnL: {e}")
    
    async def _publish_risk_alert(self, message: str, symbol: str, risk_level: RiskLevel = RiskLevel.MEDIUM):
        """리스크 알림 이벤트 발행"""
        try:
            await self._publish_event(EventType.RISK_ALERT, {
                "message": message,
                "symbol": symbol,
                "risk_level": risk_level.value,
                "timestamp": datetime.now().isoformat(),
                "component": "RiskEngine"
            })
            
        except Exception as e:
            logger.error(f"Error publishing risk alert: {e}")
    
    async def _publish_event(self, event_type: EventType, data: Dict[str, Any]):
        """이벤트 발행 헬퍼"""
        event = self.event_bus.create_event(
            event_type,
            source="RiskEngine",
            data=data
        )
        self.event_bus.publish(event)
    
    # Portfolio 관련 메서드들 (실제 구현은 포지션 매니저와 연동)
    
    async def _get_portfolio_value(self) -> Decimal:
        """포트폴리오 총 가치 조회"""
        # TODO: 실제 포트폴리오 매니저와 연동
        return Decimal('2000000')  # 임시값
    
    async def _get_cash_balance(self) -> Decimal:
        """현금 잔고 조회"""
        # TODO: 실제 브로커 클라이언트와 연동
        return Decimal('500000')  # 임시값
    
    async def _get_total_exposure(self) -> Decimal:
        """총 노출 금액 조회"""
        # TODO: 실제 포지션 매니저와 연동
        return Decimal('1500000')  # 임시값
    
    async def _get_position_count(self) -> int:
        """보유 포지션 수 조회"""
        # TODO: 실제 포지션 매니저와 연동
        return 3  # 임시값
    
    async def _get_max_position_value(self) -> Decimal:
        """최대 포지션 가치 조회"""
        # TODO: 실제 포지션 매니저와 연동
        return Decimal('600000')  # 임시값
    
    async def _calculate_risk_score(self) -> float:
        """리스크 점수 계산 (0.0 ~ 1.0)"""
        try:
            score = 0.0
            
            # 손실 기준 점수
            if self._daily_pnl < 0:
                loss_ratio = abs(float(self._daily_pnl)) / self.config['max_daily_loss']
                score += min(loss_ratio * 0.4, 0.4)
            
            # 연속 손실 기준 점수
            loss_ratio = self._consecutive_losses / self.config['max_consecutive_losses']
            score += min(loss_ratio * 0.3, 0.3)
            
            # 노출 비율 기준 점수
            portfolio_value = await self._get_portfolio_value()
            total_exposure = await self._get_total_exposure()
            if portfolio_value > 0:
                exposure_ratio = float(total_exposure / portfolio_value)
                max_exposure = self.config['max_total_exposure_ratio']
                score += min((exposure_ratio / max_exposure) * 0.3, 0.3)
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return 1.0  # 오류 시 최고 위험으로 간주