"""
Emergency Stop System

비상 정지 시스템
극한 상황에서 모든 거래를 즉시 중단하는 안전장치
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EmergencyReason(Enum):
    """비상 정지 사유"""
    DAILY_LOSS_LIMIT = "daily_loss_limit"           # 일일 손실 한도 초과
    MONTHLY_LOSS_LIMIT = "monthly_loss_limit"       # 월간 손실 한도 초과
    CONSECUTIVE_LOSSES = "consecutive_losses"       # 연속 손실 발생
    SYSTEM_ANOMALY = "system_anomaly"              # 시스템 이상 감지
    MANUAL_STOP = "manual_stop"                    # 수동 정지
    MARKET_CRASH = "market_crash"                  # 시장 급락 감지
    API_CONNECTION_LOST = "api_connection_lost"    # API 연결 끊김
    EXCESSIVE_DRAWDOWN = "excessive_drawdown"      # 과도한 손실
    RISK_THRESHOLD_BREACH = "risk_threshold_breach" # 리스크 임계값 위반


@dataclass
class EmergencyEvent:
    """비상 정지 이벤트"""
    reason: EmergencyReason
    message: str
    triggered_at: datetime
    severity: str  # 'WARNING', 'CRITICAL', 'EMERGENCY'
    metrics: Dict[str, Any]
    auto_triggered: bool = True


class EmergencyStop:
    """
    비상 정지 시스템
    
    주요 기능:
    1. 다양한 비상 정지 조건 모니터링
    2. 자동 비상 정지 트리거
    3. 모든 거래 활동 즉시 중단
    4. 비상 상황 알림 및 로깅
    5. 수동 복구 및 재개 기능
    """
    
    def __init__(self, risk_engine):
        self.risk_engine = risk_engine
        self.db_manager = risk_engine.db_manager
        self.redis_manager = risk_engine.redis_manager
        self.event_bus = risk_engine.event_bus
        self.config = risk_engine.config
        
        # 비상 정지 상태
        self.is_active = False
        self.reason: Optional[EmergencyReason] = None
        self.triggered_at: Optional[datetime] = None
        self.emergency_events: List[EmergencyEvent] = []
        
        # 모니터링 상태
        self._last_api_check = datetime.now()
        self._consecutive_api_failures = 0
        self._system_health_score = 1.0
        
        logger.info("EmergencyStop system initialized")
    
    async def check_conditions(self) -> bool:
        """
        비상 정지 조건 확인
        
        Returns:
            bool: 비상 정지 활성화 여부
        """
        try:
            if self.is_active:
                return True
            
            # 1. 일일 손실 한도 초과 확인
            if await self._check_daily_loss_limit():
                return await self._activate(EmergencyReason.DAILY_LOSS_LIMIT, "일일 손실 한도 초과")
            
            # 2. 월간 손실 한도 초과 확인
            if await self._check_monthly_loss_limit():
                return await self._activate(EmergencyReason.MONTHLY_LOSS_LIMIT, "월간 손실 한도 초과")
            
            # 3. 연속 손실 확인
            if await self._check_consecutive_losses():
                return await self._activate(EmergencyReason.CONSECUTIVE_LOSSES, "연속 손실 임계값 초과")
            
            # 4. 과도한 드로우다운 확인
            if await self._check_excessive_drawdown():
                return await self._activate(EmergencyReason.EXCESSIVE_DRAWDOWN, "과도한 포트폴리오 손실")
            
            # 5. 시스템 이상 확인
            if await self._check_system_anomalies():
                return await self._activate(EmergencyReason.SYSTEM_ANOMALY, "시스템 이상 감지")
            
            # 6. API 연결 상태 확인
            if await self._check_api_connection():
                return await self._activate(EmergencyReason.API_CONNECTION_LOST, "API 연결 중단")
            
            # 7. 시장 급락 감지
            if await self._check_market_crash():
                return await self._activate(EmergencyReason.MARKET_CRASH, "시장 급락 감지")
            
            # 8. 리스크 점수 임계값 확인
            if await self._check_risk_threshold():
                return await self._activate(EmergencyReason.RISK_THRESHOLD_BREACH, "리스크 임계값 위반")
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking emergency conditions: {e}")
            # 오류 발생 시 안전을 위해 비상 정지
            return await self._activate(EmergencyReason.SYSTEM_ANOMALY, f"비상 조건 체크 오류: {str(e)}")
    
    async def manual_activate(self, reason: str = "Manual emergency stop") -> bool:
        """
        수동 비상 정지 활성화
        
        Args:
            reason: 정지 사유
            
        Returns:
            bool: 활성화 성공 여부
        """
        try:
            return await self._activate(EmergencyReason.MANUAL_STOP, reason, auto_triggered=False)
            
        except Exception as e:
            logger.error(f"Error manually activating emergency stop: {e}")
            return False
    
    async def reset(self, admin_key: Optional[str] = None) -> bool:
        """
        비상 정지 해제 (관리자 권한 필요)
        
        Args:
            admin_key: 관리자 인증 키
            
        Returns:
            bool: 해제 성공 여부
        """
        try:
            # 관리자 인증 (실제 환경에서는 더 강력한 인증 필요)
            if admin_key != self.config.get('emergency_admin_key', 'EMERGENCY_RESET_2024'):
                logger.warning("Invalid admin key for emergency reset")
                return False
            
            if not self.is_active:
                logger.info("Emergency stop is not active")
                return True
            
            # 상태 초기화
            old_reason = self.reason
            old_triggered_at = self.triggered_at
            
            self.is_active = False
            self.reason = None
            self.triggered_at = None
            self._consecutive_api_failures = 0
            self._system_health_score = 1.0
            
            # Redis에서 비상 정지 상태 제거
            await self.redis_manager.delete("emergency_stop:active")
            
            # 해제 이벤트 발행
            await self._publish_emergency_event({
                'type': 'emergency_stop_reset',
                'message': f'비상 정지 해제 (이전 사유: {old_reason.value if old_reason else "unknown"})',
                'previous_reason': old_reason.value if old_reason else None,
                'previous_triggered_at': old_triggered_at.isoformat() if old_triggered_at else None,
                'reset_at': datetime.now().isoformat(),
                'reset_by': 'admin'
            })
            
            logger.info(f"Emergency stop reset by admin (previous reason: {old_reason})")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting emergency stop: {e}")
            return False
    
    async def get_status(self) -> Dict[str, Any]:
        """비상 정지 상태 조회"""
        try:
            return {
                'is_active': self.is_active,
                'reason': self.reason.value if self.reason else None,
                'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
                'system_health_score': self._system_health_score,
                'consecutive_api_failures': self._consecutive_api_failures,
                'last_api_check': self._last_api_check.isoformat(),
                'recent_events': [
                    {
                        'reason': event.reason.value,
                        'message': event.message,
                        'triggered_at': event.triggered_at.isoformat(),
                        'severity': event.severity,
                        'auto_triggered': event.auto_triggered
                    }
                    for event in self.emergency_events[-10:]  # 최근 10개 이벤트
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting emergency stop status: {e}")
            return {'error': str(e)}
    
    # Private Methods
    
    async def _activate(self, reason: EmergencyReason, message: str, auto_triggered: bool = True) -> bool:
        """비상 정지 활성화"""
        try:
            if self.is_active:
                return True
            
            self.is_active = True
            self.reason = reason
            self.triggered_at = datetime.now()
            
            # 비상 이벤트 기록
            emergency_event = EmergencyEvent(
                reason=reason,
                message=message,
                triggered_at=self.triggered_at,
                severity='EMERGENCY',
                metrics=await self._collect_emergency_metrics(),
                auto_triggered=auto_triggered
            )
            self.emergency_events.append(emergency_event)
            
            # Redis에 비상 정지 상태 저장
            await self._save_emergency_state()
            
            # 비상 정지 이벤트 발행
            await self._publish_emergency_event({
                'type': 'emergency_stop_activated',
                'reason': reason.value,
                'message': message,
                'triggered_at': self.triggered_at.isoformat(),
                'auto_triggered': auto_triggered,
                'metrics': emergency_event.metrics
            })
            
            # 모든 활성 주문 취소 요청
            await self._emergency_cancel_all_orders()
            
            logger.critical(f"🚨 EMERGENCY STOP ACTIVATED: {reason.value} - {message}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error activating emergency stop: {e}")
            return False
    
    async def _check_daily_loss_limit(self) -> bool:
        """일일 손실 한도 초과 확인"""
        try:
            current_daily_pnl = self.risk_engine._daily_pnl
            max_daily_loss = Decimal(self.config['max_daily_loss'])
            
            return current_daily_pnl <= -max_daily_loss
            
        except Exception as e:
            logger.error(f"Error checking daily loss limit: {e}")
            return True  # 오류 시 안전을 위해 True 반환
    
    async def _check_monthly_loss_limit(self) -> bool:
        """월간 손실 한도 초과 확인"""
        try:
            current_monthly_pnl = self.risk_engine._monthly_pnl
            max_monthly_loss = Decimal(self.config['max_monthly_loss'])
            
            return current_monthly_pnl <= -max_monthly_loss
            
        except Exception as e:
            logger.error(f"Error checking monthly loss limit: {e}")
            return True
    
    async def _check_consecutive_losses(self) -> bool:
        """연속 손실 확인"""
        try:
            max_consecutive = self.config['max_consecutive_losses']
            current_consecutive = self.risk_engine._consecutive_losses
            
            return current_consecutive >= max_consecutive
            
        except Exception as e:
            logger.error(f"Error checking consecutive losses: {e}")
            return True
    
    async def _check_excessive_drawdown(self) -> bool:
        """과도한 드로우다운 확인"""
        try:
            # 포트폴리오 가치 대비 손실 비율 확인
            portfolio_value = await self.risk_engine._get_portfolio_value()
            current_daily_loss = abs(self.risk_engine._daily_pnl) if self.risk_engine._daily_pnl < 0 else Decimal('0')
            
            if portfolio_value <= 0:
                return True
            
            drawdown_ratio = float(current_daily_loss / portfolio_value)
            max_drawdown_ratio = 0.15  # 15% 이상 손실 시 비상 정지
            
            return drawdown_ratio >= max_drawdown_ratio
            
        except Exception as e:
            logger.error(f"Error checking excessive drawdown: {e}")
            return True
    
    async def _check_system_anomalies(self) -> bool:
        """시스템 이상 확인"""
        try:
            # 시스템 헬스 점수가 임계값 이하인 경우
            health_threshold = 0.3
            
            if self._system_health_score <= health_threshold:
                return True
            
            # 메모리 사용량 확인
            memory_stats = await self.redis_manager.get_memory_stats()
            if memory_stats:
                used_memory = memory_stats.get('used_memory_human', '0MB')
                if 'GB' in used_memory:  # 1GB 이상 사용 시 경고
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking system anomalies: {e}")
            return True
    
    async def _check_api_connection(self) -> bool:
        """API 연결 상태 확인"""
        try:
            # Redis 연결 확인
            if not await self.redis_manager.ping():
                self._consecutive_api_failures += 1
            else:
                self._consecutive_api_failures = 0
            
            self._last_api_check = datetime.now()
            
            # 연속 실패 횟수가 임계값 초과 시
            max_failures = 5
            if self._consecutive_api_failures >= max_failures:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking API connection: {e}")
            self._consecutive_api_failures += 1
            return self._consecutive_api_failures >= 3
    
    async def _check_market_crash(self) -> bool:
        """시장 급락 감지"""
        try:
            # 보유 종목들의 급락 확인 (임시 구현)
            # 실제로는 시장 지수나 보유 종목들의 가격 변화를 확인
            
            # 예: 포트폴리오 가치가 하루 동안 10% 이상 하락
            portfolio_value = await self.risk_engine._get_portfolio_value()
            daily_pnl = self.risk_engine._daily_pnl
            
            if portfolio_value > 0:
                daily_loss_ratio = float(abs(daily_pnl) / portfolio_value) if daily_pnl < 0 else 0.0
                crash_threshold = 0.10  # 10% 이상 하락 시 급락으로 간주
                
                return daily_loss_ratio >= crash_threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking market crash: {e}")
            return False
    
    async def _check_risk_threshold(self) -> bool:
        """리스크 점수 임계값 확인"""
        try:
            risk_score = await self.risk_engine._calculate_risk_score()
            risk_threshold = 0.95  # 95% 이상 위험 시 비상 정지
            
            return risk_score >= risk_threshold
            
        except Exception as e:
            logger.error(f"Error checking risk threshold: {e}")
            return True
    
    async def _collect_emergency_metrics(self) -> Dict[str, Any]:
        """비상 상황 시 메트릭 수집"""
        try:
            return {
                'portfolio_value': float(await self.risk_engine._get_portfolio_value()),
                'cash_balance': float(await self.risk_engine._get_cash_balance()),
                'daily_pnl': float(self.risk_engine._daily_pnl),
                'monthly_pnl': float(self.risk_engine._monthly_pnl),
                'consecutive_losses': self.risk_engine._consecutive_losses,
                'trade_count_today': self.risk_engine._trade_count_today,
                'system_health_score': self._system_health_score,
                'api_failures': self._consecutive_api_failures,
                'risk_score': await self.risk_engine._calculate_risk_score(),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error collecting emergency metrics: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    async def _save_emergency_state(self):
        """비상 정지 상태 저장"""
        try:
            emergency_data = {
                'is_active': self.is_active,
                'reason': self.reason.value if self.reason else None,
                'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
                'system_health_score': self._system_health_score
            }
            
            await self.redis_manager.set_hash("emergency_stop:active", emergency_data, ttl=86400)
            
        except Exception as e:
            logger.error(f"Error saving emergency state: {e}")
    
    async def _emergency_cancel_all_orders(self):
        """비상 시 모든 주문 취소"""
        try:
            # 주문 엔진에 전체 주문 취소 요청
            await self._publish_emergency_event({
                'type': 'emergency_cancel_all_orders',
                'reason': 'emergency_stop_activated',
                'timestamp': datetime.now().isoformat()
            })
            
            logger.warning("Emergency: All orders cancellation requested")
            
        except Exception as e:
            logger.error(f"Error requesting emergency order cancellation: {e}")
    
    async def _publish_emergency_event(self, event_data: Dict[str, Any]):
        """비상 이벤트 발행"""
        try:
            event = self.event_bus.create_event(
                'EMERGENCY_STOP',
                source="EmergencyStop",
                data=event_data
            )
            self.event_bus.publish(event)
            
            # 추가로 critical 로깅
            logger.critical(f"Emergency Event: {event_data}")
            
        except Exception as e:
            logger.error(f"Error publishing emergency event: {e}")
    
    def update_system_health_score(self, score: float):
        """시스템 헬스 점수 업데이트"""
        try:
            self._system_health_score = max(0.0, min(1.0, score))
            logger.debug(f"System health score updated: {self._system_health_score}")
            
        except Exception as e:
            logger.error(f"Error updating system health score: {e}")