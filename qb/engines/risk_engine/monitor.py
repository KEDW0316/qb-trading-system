"""
Risk Monitor - 리스크 모니터링 시스템

실시간 리스크 지표 모니터링 및 알림 시스템
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class RiskMonitor:
    """
    리스크 모니터링 시스템
    
    주요 기능:
    1. 실시간 리스크 지표 업데이트
    2. 리스크 임계값 모니터링
    3. 리스크 알림 발행
    4. 리스크 보고서 생성
    """
    
    def __init__(self, risk_engine):
        self.risk_engine = risk_engine
        self.redis_manager = risk_engine.redis_manager
        self.event_bus = risk_engine.event_bus
        self.config = risk_engine.config
        
        # 모니터링 메트릭
        self.metrics = {
            'last_update': None,
            'portfolio_value': Decimal('0'),
            'total_exposure': Decimal('0'),
            'cash_balance': Decimal('0'),
            'risk_score': 0.0,
            'daily_pnl': Decimal('0'),
            'position_count': 0
        }
        
        # 알림 스로틀링 - 같은 유형의 알림은 최소 30초 간격
        self.last_alert_times: Dict[str, datetime] = {}
        self.alert_cooldown_seconds = 30
        
        logger.info("RiskMonitor initialized")
    
    async def update_metrics(self):
        """리스크 지표 업데이트"""
        try:
            # 포트폴리오 메트릭 업데이트
            await self._update_portfolio_metrics()
            
            # 익스포저 메트릭 업데이트
            await self._update_exposure_metrics()
            
            # 손익 메트릭 업데이트
            await self._update_pnl_metrics()
            
            # 리스크 임계값 확인
            await self._check_risk_thresholds()
            
            # 메트릭 저장
            await self._save_metrics()
            
            self.metrics['last_update'] = datetime.now()
            
        except Exception as e:
            logger.error(f"Error updating risk metrics: {e}")
    
    async def get_risk_report(self) -> Dict[str, Any]:
        """리스크 보고서 생성"""
        try:
            return {
                'timestamp': datetime.now().isoformat(),
                'metrics': {
                    'portfolio_value': float(self.metrics['portfolio_value']),
                    'total_exposure': float(self.metrics['total_exposure']),
                    'cash_balance': float(self.metrics['cash_balance']),
                    'exposure_ratio': float(self.metrics['total_exposure'] / self.metrics['portfolio_value']) if self.metrics['portfolio_value'] > 0 else 0.0,
                    'cash_ratio': float(self.metrics['cash_balance'] / self.metrics['portfolio_value']) if self.metrics['portfolio_value'] > 0 else 0.0,
                    'risk_score': self.metrics['risk_score'],
                    'daily_pnl': float(self.metrics['daily_pnl']),
                    'position_count': self.metrics['position_count']
                },
                'alerts': await self._get_active_alerts(),
                'recommendations': await self._get_risk_recommendations()
            }
            
        except Exception as e:
            logger.error(f"Error generating risk report: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    # Private Methods
    
    async def _update_portfolio_metrics(self):
        """포트폴리오 메트릭 업데이트"""
        try:
            self.metrics['portfolio_value'] = await self.risk_engine._get_portfolio_value()
            self.metrics['cash_balance'] = await self.risk_engine._get_cash_balance()
            self.metrics['position_count'] = await self.risk_engine._get_position_count()
            
        except Exception as e:
            logger.error(f"Error updating portfolio metrics: {e}")
    
    async def _update_exposure_metrics(self):
        """익스포저 메트릭 업데이트"""
        try:
            self.metrics['total_exposure'] = await self.risk_engine._get_total_exposure()
            
        except Exception as e:
            logger.error(f"Error updating exposure metrics: {e}")
    
    async def _update_pnl_metrics(self):
        """손익 메트릭 업데이트"""
        try:
            self.metrics['daily_pnl'] = self.risk_engine._daily_pnl
            self.metrics['risk_score'] = await self.risk_engine._calculate_risk_score()
            
        except Exception as e:
            logger.error(f"Error updating PnL metrics: {e}")
    
    def _should_send_alert(self, alert_type: str) -> bool:
        """알림 스로틀링 체크"""
        now = datetime.now()
        last_alert_time = self.last_alert_times.get(alert_type)
        
        if last_alert_time is None:
            self.last_alert_times[alert_type] = now
            return True
        
        time_since_last = (now - last_alert_time).total_seconds()
        if time_since_last >= self.alert_cooldown_seconds:
            self.last_alert_times[alert_type] = now
            return True
        
        return False
    
    async def _check_risk_thresholds(self):
        """리스크 임계값 확인"""
        try:
            # 익스포저 비율 체크
            if self.metrics['portfolio_value'] > 0:
                exposure_ratio = float(self.metrics['total_exposure'] / self.metrics['portfolio_value'])
                max_exposure = self.config.get('max_total_exposure_ratio', 0.9)
                
                if exposure_ratio > max_exposure * 0.9:  # 90% 도달 시 경고
                    if self._should_send_alert("HIGH_EXPOSURE"):
                        await self._publish_risk_alert(
                            f"높은 익스포저 비율: {exposure_ratio:.1%} (한도: {max_exposure:.1%})",
                            "PORTFOLIO",
                            "HIGH"
                        )
            
            # 리스크 점수 체크
            if self.metrics['risk_score'] > 0.8:
                if self._should_send_alert("HIGH_RISK_SCORE"):
                    await self._publish_risk_alert(
                        f"높은 리스크 점수: {self.metrics['risk_score']:.2f}",
                        "RISK_SCORE",
                        "HIGH"
                    )
            
        except Exception as e:
            logger.error(f"Error checking risk thresholds: {e}")
    
    async def _save_metrics(self):
        """메트릭 Redis에 저장"""
        try:
            metrics_data = {
                'portfolio_value': str(self.metrics['portfolio_value']),
                'total_exposure': str(self.metrics['total_exposure']),
                'cash_balance': str(self.metrics['cash_balance']),
                'risk_score': self.metrics['risk_score'],
                'daily_pnl': str(self.metrics['daily_pnl']),
                'position_count': self.metrics['position_count'],
                'timestamp': datetime.now().isoformat()
            }
            
            self.redis_manager.set_hash("risk_metrics:current", metrics_data, ttl=3600)
            
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    async def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """활성 알림 조회"""
        try:
            alerts = []
            
            # Redis에서 최근 알림 조회 (최근 1시간)
            alert_key = "risk_alerts:recent"
            recent_alerts = await self.redis_manager.get_list(alert_key)
            
            current_time = datetime.now()
            
            for alert_data in recent_alerts[-20:]:  # 최근 20개
                try:
                    alert_time = datetime.fromisoformat(alert_data.get('timestamp', ''))
                    # 1시간 이내 알림만 포함
                    if current_time - alert_time < timedelta(hours=1):
                        alerts.append({
                            'message': alert_data.get('message', ''),
                            'category': alert_data.get('category', 'UNKNOWN'),
                            'severity': alert_data.get('severity', 'LOW'),
                            'timestamp': alert_data.get('timestamp', ''),
                            'age_minutes': int((current_time - alert_time).total_seconds() / 60)
                        })
                except Exception:
                    continue
            
            # 심각도 순으로 정렬 (CRITICAL > HIGH > MEDIUM > LOW)
            severity_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
            alerts.sort(key=lambda x: severity_order.get(x['severity'], 0), reverse=True)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []
    
    async def _get_risk_recommendations(self) -> List[str]:
        """리스크 권장사항 생성"""
        try:
            recommendations = []
            
            # 익스포저 비율 기반 권장사항
            if self.metrics['portfolio_value'] > 0:
                exposure_ratio = float(self.metrics['total_exposure'] / self.metrics['portfolio_value'])
                
                if exposure_ratio > 0.8:
                    recommendations.append("포지션 크기를 줄여 익스포저를 감소시키세요")
                
                cash_ratio = float(self.metrics['cash_balance'] / self.metrics['portfolio_value'])
                if cash_ratio < 0.1:
                    recommendations.append("현금 보유량을 늘려 유동성을 확보하세요")
            
            # 리스크 점수 기반 권장사항
            if self.metrics['risk_score'] > 0.7:
                recommendations.append("리스크 점수가 높습니다. 신중한 거래를 권장합니다")
            
            # 손실 기반 권장사항
            if self.metrics['daily_pnl'] < 0:
                loss_ratio = abs(float(self.metrics['daily_pnl'])) / self.config.get('max_daily_loss', 50000)
                if loss_ratio > 0.5:
                    recommendations.append("일일 손실이 큽니다. 거래를 중단하고 전략을 재검토하세요")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating risk recommendations: {e}")
            return ["리스크 권장사항 생성 중 오류가 발생했습니다"]
    
    async def _publish_risk_alert(self, message: str, category: str, severity: str):
        """리스크 알림 발행"""
        try:
            alert_data = {
                'message': message,
                'category': category,
                'severity': severity,
                'timestamp': datetime.now().isoformat()
            }
            
            # 이벤트 버스로 발행
            from ...utils.event_bus import EventType
            event = self.event_bus.create_event(
                EventType.RISK_ALERT,
                source="RiskMonitor",
                data=alert_data
            )
            self.event_bus.publish(event)
            
            # Redis에 알림 기록 저장
            await self._store_alert(alert_data)
            
            logger.warning(f"Risk Alert [{severity}] {category}: {message}")
            
        except Exception as e:
            logger.error(f"Error publishing risk alert: {e}")
    
    async def _store_alert(self, alert_data: Dict[str, Any]):
        """알림 기록 저장"""
        try:
            alert_key = "risk_alerts:recent"
            self.redis_manager.list_push(alert_key, alert_data, max_items=100)
            
            # 일별 알림 통계
            date_key = f"risk_alerts:daily:{datetime.now().strftime('%Y-%m-%d')}"
            self.redis_manager.redis.incr(date_key)
            self.redis_manager.redis.expire(date_key, 86400 * 7)  # 7일 보관
            
        except Exception as e:
            logger.error(f"Error storing alert: {e}")
    
    async def start_monitoring(self):
        """모니터링 시작"""
        try:
            logger.info("Starting risk monitoring...")
            while True:
                await self.update_metrics()
                await asyncio.sleep(30)  # 30초마다 업데이트
                
        except asyncio.CancelledError:
            logger.info("Risk monitoring stopped")
        except Exception as e:
            logger.error(f"Error in risk monitoring loop: {e}")
    
    async def stop_monitoring(self):
        """모니터링 중지"""
        try:
            logger.info("Stopping risk monitoring...")
            
        except Exception as e:
            logger.error(f"Error stopping risk monitoring: {e}")
    
    async def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """메트릭 이력 조회"""
        try:
            history = []
            
            # Redis에서 시간별 메트릭 조회
            for hour in range(hours):
                timestamp = datetime.now() - timedelta(hours=hour)
                history_key = f"risk_metrics:history:{timestamp.strftime('%Y-%m-%d_%H')}"
                metrics_data = await self.redis_manager.get_hash(history_key)
                
                if metrics_data:
                    history.append({
                        'timestamp': timestamp.isoformat(),
                        'portfolio_value': float(metrics_data.get('portfolio_value', 0)),
                        'total_exposure': float(metrics_data.get('total_exposure', 0)),
                        'risk_score': float(metrics_data.get('risk_score', 0)),
                        'daily_pnl': float(metrics_data.get('daily_pnl', 0))
                    })
            
            return list(reversed(history))  # 시간순 정렬
            
        except Exception as e:
            logger.error(f"Error getting metrics history: {e}")
            return []