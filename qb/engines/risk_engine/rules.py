"""
Risk Rules - 리스크 검증 규칙들

다양한 리스크 체크 규칙을 정의하고 구현합니다.
각 규칙은 주문 실행 전 특정 조건을 검증합니다.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

from .engine import RiskCheckResult, RiskLevel

logger = logging.getLogger(__name__)


class BaseRiskRule(ABC):
    """리스크 규칙 기본 클래스"""
    
    def __init__(self, risk_engine):
        self.risk_engine = risk_engine
        self.name = self.__class__.__name__
        
    @abstractmethod
    async def validate(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """
        리스크 규칙 검증
        
        Args:
            symbol: 종목 코드
            side: 매수/매도 ('BUY' or 'SELL')
            quantity: 주문 수량
            price: 주문 가격
            metadata: 추가 메타데이터
            
        Returns:
            RiskCheckResult: 검증 결과
        """
        pass
    
    def __str__(self):
        return self.name


class PositionSizeRule(BaseRiskRule):
    """포지션 크기 제한 규칙"""
    
    async def validate(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """종목당 최대 투자 비율 검증"""
        try:
            if side != 'BUY':
                return RiskCheckResult(approved=True)  # 매도는 제한 없음
            
            # 주문 금액 계산
            order_value = Decimal(quantity * price)
            
            # 현재 포트폴리오 가치 조회
            portfolio_value = await self.risk_engine._get_portfolio_value()
            
            # 현재 포지션 가치 조회
            current_position_value = await self._get_current_position_value(symbol)
            
            # 총 투자 금액 (기존 + 신규)
            total_investment = current_position_value + order_value
            
            # 최대 허용 금액
            max_position_ratio = self.risk_engine.config['max_position_size_ratio']
            max_allowed = portfolio_value * Decimal(max_position_ratio)
            
            if total_investment > max_allowed:
                # 추천 수량 계산
                available_amount = max_allowed - current_position_value
                suggested_quantity = int(available_amount / Decimal(price)) if available_amount > 0 else 0
                
                return RiskCheckResult(
                    approved=False,
                    reason=f"포지션 크기 한도 초과: {total_investment:,.0f}원 > {max_allowed:,.0f}원 "
                           f"(현재: {current_position_value:,.0f}원, 신규: {order_value:,.0f}원)",
                    risk_level=RiskLevel.HIGH,
                    suggested_quantity=suggested_quantity
                )
            
            # 경고 레벨 체크 (80% 이상)
            warning_threshold = max_allowed * Decimal('0.8')
            if total_investment > warning_threshold:
                return RiskCheckResult(
                    approved=True,
                    reason=f"포지션 크기 경고: {total_investment:,.0f}원 (한도의 {(total_investment/max_allowed)*100:.1f}%)",
                    risk_level=RiskLevel.MEDIUM
                )
            
            return RiskCheckResult(approved=True, risk_level=RiskLevel.LOW)
            
        except Exception as e:
            logger.error(f"Error in PositionSizeRule: {e}")
            return RiskCheckResult(
                approved=False,
                reason=f"포지션 크기 규칙 검증 오류: {str(e)}",
                risk_level=RiskLevel.CRITICAL
            )
    
    async def _get_current_position_value(self, symbol: str) -> Decimal:
        """현재 포지션 가치 조회"""
        try:
            # TODO: 실제 포지션 매니저와 연동
            # 임시로 Redis에서 조회
            position_key = f"positions:{symbol}"
            position_data = await self.risk_engine.redis_manager.get_hash(position_key)
            
            if position_data:
                quantity = int(position_data.get('quantity', 0))
                avg_price = float(position_data.get('average_price', 0))
                return Decimal(quantity * avg_price)
            
            return Decimal('0')
            
        except Exception as e:
            logger.error(f"Error getting current position value for {symbol}: {e}")
            return Decimal('0')


class SectorExposureRule(BaseRiskRule):
    """섹터 익스포저 제한 규칙"""
    
    async def validate(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """섹터별 최대 투자 비율 검증"""
        try:
            if side != 'BUY':
                return RiskCheckResult(approved=True)
            
            # 종목의 섹터 정보 조회
            sector = await self._get_symbol_sector(symbol)
            if not sector:
                return RiskCheckResult(approved=True)  # 섹터 정보 없으면 통과
            
            # 주문 금액 계산
            order_value = Decimal(quantity * price)
            
            # 포트폴리오 가치 조회
            portfolio_value = await self.risk_engine._get_portfolio_value()
            
            # 현재 섹터 익스포저 조회
            current_sector_exposure = await self._get_sector_exposure(sector)
            
            # 총 섹터 익스포저 (기존 + 신규)
            total_sector_exposure = current_sector_exposure + order_value
            
            # 최대 허용 금액
            max_sector_ratio = self.risk_engine.config['max_sector_exposure_ratio']
            max_allowed = portfolio_value * Decimal(max_sector_ratio)
            
            if total_sector_exposure > max_allowed:
                return RiskCheckResult(
                    approved=False,
                    reason=f"섹터 익스포저 한도 초과 ({sector}): {total_sector_exposure:,.0f}원 > {max_allowed:,.0f}원",
                    risk_level=RiskLevel.HIGH
                )
            
            # 경고 레벨 체크
            warning_threshold = max_allowed * Decimal('0.8')
            if total_sector_exposure > warning_threshold:
                return RiskCheckResult(
                    approved=True,
                    reason=f"섹터 익스포저 경고 ({sector}): {total_sector_exposure:,.0f}원 (한도의 {(total_sector_exposure/max_allowed)*100:.1f}%)",
                    risk_level=RiskLevel.MEDIUM
                )
            
            return RiskCheckResult(approved=True, risk_level=RiskLevel.LOW)
            
        except Exception as e:
            logger.error(f"Error in SectorExposureRule: {e}")
            return RiskCheckResult(
                approved=False,
                reason=f"섹터 익스포저 규칙 검증 오류: {str(e)}",
                risk_level=RiskLevel.CRITICAL
            )
    
    async def _get_symbol_sector(self, symbol: str) -> Optional[str]:
        """종목의 섹터 정보 조회"""
        try:
            # TODO: 종목 메타데이터에서 섹터 정보 조회
            # 임시로 기본 섹터 매핑 사용
            sector_mapping = {
                '005930': 'Technology',   # 삼성전자
                '000660': 'Healthcare',   # SK하이닉스
                '035420': 'Retail',       # NAVER
                '051910': 'Healthcare',   # LG화학
                '006400': 'Technology',   # 삼성SDI
            }
            return sector_mapping.get(symbol, 'Unknown')
            
        except Exception as e:
            logger.error(f"Error getting sector for {symbol}: {e}")
            return None
    
    async def _get_sector_exposure(self, sector: str) -> Decimal:
        """현재 섹터 익스포저 조회"""
        try:
            # TODO: 실제 포지션 매니저와 연동
            # 임시로 Redis에서 계산
            exposure = Decimal('0')
            
            # 모든 포지션 조회
            position_keys = await self.risk_engine.redis_manager.get_keys_by_pattern("positions:*")
            
            for key in position_keys:
                symbol = key.split(':')[1]
                symbol_sector = await self._get_symbol_sector(symbol)
                
                if symbol_sector == sector:
                    position_data = await self.risk_engine.redis_manager.get_hash(key)
                    if position_data:
                        quantity = int(position_data.get('quantity', 0))
                        avg_price = float(position_data.get('average_price', 0))
                        exposure += Decimal(quantity * avg_price)
            
            return exposure
            
        except Exception as e:
            logger.error(f"Error getting sector exposure for {sector}: {e}")
            return Decimal('0')


class DailyLossRule(BaseRiskRule):
    """일일 손실 한도 규칙"""
    
    async def validate(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """일일 손실 한도 검증"""
        try:
            # 현재 일일 손익 확인
            current_daily_pnl = self.risk_engine._daily_pnl
            max_daily_loss = Decimal(self.risk_engine.config['max_daily_loss'])
            
            # 이미 한도 초과한 경우
            if current_daily_pnl <= -max_daily_loss:
                return RiskCheckResult(
                    approved=False,
                    reason=f"일일 손실 한도 초과: {abs(current_daily_pnl):,.0f}원 >= {max_daily_loss:,.0f}원",
                    risk_level=RiskLevel.CRITICAL
                )
            
            # 경고 레벨 체크 (80% 이상 손실)
            warning_threshold = max_daily_loss * Decimal('0.8')
            current_loss = abs(current_daily_pnl) if current_daily_pnl < 0 else Decimal('0')
            
            if current_loss > warning_threshold:
                return RiskCheckResult(
                    approved=True,
                    reason=f"일일 손실 경고: {current_loss:,.0f}원 (한도의 {(current_loss/max_daily_loss)*100:.1f}%)",
                    risk_level=RiskLevel.HIGH
                )
            
            return RiskCheckResult(approved=True, risk_level=RiskLevel.LOW)
            
        except Exception as e:
            logger.error(f"Error in DailyLossRule: {e}")
            return RiskCheckResult(
                approved=False,
                reason=f"일일 손실 규칙 검증 오류: {str(e)}",
                risk_level=RiskLevel.CRITICAL
            )


class MonthlyLossRule(BaseRiskRule):
    """월간 손실 한도 규칙"""
    
    async def validate(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """월간 손실 한도 검증"""
        try:
            # 현재 월간 손익 확인
            current_monthly_pnl = self.risk_engine._monthly_pnl
            max_monthly_loss = Decimal(self.risk_engine.config['max_monthly_loss'])
            
            # 이미 한도 초과한 경우
            if current_monthly_pnl <= -max_monthly_loss:
                return RiskCheckResult(
                    approved=False,
                    reason=f"월간 손실 한도 초과: {abs(current_monthly_pnl):,.0f}원 >= {max_monthly_loss:,.0f}원",
                    risk_level=RiskLevel.CRITICAL
                )
            
            # 경고 레벨 체크 (80% 이상 손실)
            warning_threshold = max_monthly_loss * Decimal('0.8')
            current_loss = abs(current_monthly_pnl) if current_monthly_pnl < 0 else Decimal('0')
            
            if current_loss > warning_threshold:
                return RiskCheckResult(
                    approved=True,
                    reason=f"월간 손실 경고: {current_loss:,.0f}원 (한도의 {(current_loss/max_monthly_loss)*100:.1f}%)",
                    risk_level=RiskLevel.HIGH
                )
            
            return RiskCheckResult(approved=True, risk_level=RiskLevel.LOW)
            
        except Exception as e:
            logger.error(f"Error in MonthlyLossRule: {e}")
            return RiskCheckResult(
                approved=False,
                reason=f"월간 손실 규칙 검증 오류: {str(e)}",
                risk_level=RiskLevel.CRITICAL
            )


class CashReserveRule(BaseRiskRule):
    """현금 보유량 규칙"""
    
    async def validate(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """현금 보유량 검증"""
        try:
            if side != 'BUY':
                return RiskCheckResult(approved=True)  # 매도는 제한 없음
            
            # 주문 금액 계산
            order_value = Decimal(quantity * price)
            
            # 현재 현금 잔고와 포트폴리오 가치 조회
            cash_balance = await self.risk_engine._get_cash_balance()
            portfolio_value = await self.risk_engine._get_portfolio_value()
            
            # 주문 후 현금 잔고
            remaining_cash = cash_balance - order_value
            
            # 최소 현금 보유 비율
            min_cash_ratio = self.risk_engine.config['min_cash_reserve_ratio']
            min_required_cash = portfolio_value * Decimal(min_cash_ratio)
            
            if remaining_cash < min_required_cash:
                # 최대 가능 주문 금액 계산
                max_order_value = cash_balance - min_required_cash
                suggested_quantity = int(max_order_value / Decimal(price)) if max_order_value > 0 else 0
                
                return RiskCheckResult(
                    approved=False,
                    reason=f"현금 보유량 부족: 주문 후 잔고 {remaining_cash:,.0f}원 < 최소 요구 {min_required_cash:,.0f}원",
                    risk_level=RiskLevel.HIGH,
                    suggested_quantity=suggested_quantity
                )
            
            # 경고 레벨 체크 (최소 요구량의 120% 미만)
            warning_threshold = min_required_cash * Decimal('1.2')
            if remaining_cash < warning_threshold:
                return RiskCheckResult(
                    approved=True,
                    reason=f"현금 보유량 경고: 주문 후 잔고 {remaining_cash:,.0f}원",
                    risk_level=RiskLevel.MEDIUM
                )
            
            return RiskCheckResult(approved=True, risk_level=RiskLevel.LOW)
            
        except Exception as e:
            logger.error(f"Error in CashReserveRule: {e}")
            return RiskCheckResult(
                approved=False,
                reason=f"현금 보유량 규칙 검증 오류: {str(e)}",
                risk_level=RiskLevel.CRITICAL
            )


class TradeFrequencyRule(BaseRiskRule):
    """거래 빈도 제한 규칙"""
    
    async def validate(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """거래 빈도 제한 검증"""
        try:
            # 일일 거래 횟수 체크
            max_trades_per_day = self.risk_engine.config['max_trades_per_day']
            
            if self.risk_engine._trade_count_today >= max_trades_per_day:
                return RiskCheckResult(
                    approved=False,
                    reason=f"일일 거래 한도 초과: {self.risk_engine._trade_count_today}회 >= {max_trades_per_day}회",
                    risk_level=RiskLevel.HIGH
                )
            
            # 경고 레벨 체크 (90% 이상)
            warning_threshold = int(max_trades_per_day * 0.9)
            if self.risk_engine._trade_count_today >= warning_threshold:
                return RiskCheckResult(
                    approved=True,
                    reason=f"일일 거래 경고: {self.risk_engine._trade_count_today}회 (한도의 {(self.risk_engine._trade_count_today/max_trades_per_day)*100:.1f}%)",
                    risk_level=RiskLevel.MEDIUM
                )
            
            return RiskCheckResult(approved=True, risk_level=RiskLevel.LOW)
            
        except Exception as e:
            logger.error(f"Error in TradeFrequencyRule: {e}")
            return RiskCheckResult(
                approved=False,
                reason=f"거래 빈도 규칙 검증 오류: {str(e)}",
                risk_level=RiskLevel.CRITICAL
            )


class ConsecutiveLossRule(BaseRiskRule):
    """연속 손실 제한 규칙"""
    
    async def validate(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """연속 손실 제한 검증"""
        try:
            max_consecutive_losses = self.risk_engine.config['max_consecutive_losses']
            current_consecutive = self.risk_engine._consecutive_losses
            
            if current_consecutive >= max_consecutive_losses:
                return RiskCheckResult(
                    approved=False,
                    reason=f"연속 손실 한도 초과: {current_consecutive}회 >= {max_consecutive_losses}회",
                    risk_level=RiskLevel.CRITICAL
                )
            
            # 경고 레벨 체크 (80% 이상)
            warning_threshold = int(max_consecutive_losses * 0.8)
            if current_consecutive >= warning_threshold:
                return RiskCheckResult(
                    approved=True,
                    reason=f"연속 손실 경고: {current_consecutive}회 (한도의 {(current_consecutive/max_consecutive_losses)*100:.1f}%)",
                    risk_level=RiskLevel.HIGH
                )
            
            return RiskCheckResult(approved=True, risk_level=RiskLevel.LOW)
            
        except Exception as e:
            logger.error(f"Error in ConsecutiveLossRule: {e}")
            return RiskCheckResult(
                approved=False,
                reason=f"연속 손실 규칙 검증 오류: {str(e)}",
                risk_level=RiskLevel.CRITICAL
            )


class TotalExposureRule(BaseRiskRule):
    """총 익스포저 제한 규칙"""
    
    async def validate(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """총 익스포저 제한 검증"""
        try:
            if side != 'BUY':
                return RiskCheckResult(approved=True)
            
            # 주문 금액 계산
            order_value = Decimal(quantity * price)
            
            # 현재 총 익스포저와 포트폴리오 가치 조회
            current_exposure = await self.risk_engine._get_total_exposure()
            portfolio_value = await self.risk_engine._get_portfolio_value()
            
            # 주문 후 총 익스포저
            total_exposure = current_exposure + order_value
            
            # 최대 허용 익스포저
            max_exposure_ratio = self.risk_engine.config['max_total_exposure_ratio']
            max_allowed_exposure = portfolio_value * Decimal(max_exposure_ratio)
            
            if total_exposure > max_allowed_exposure:
                return RiskCheckResult(
                    approved=False,
                    reason=f"총 익스포저 한도 초과: {total_exposure:,.0f}원 > {max_allowed_exposure:,.0f}원 "
                           f"(포트폴리오의 {(total_exposure/portfolio_value)*100:.1f}%)",
                    risk_level=RiskLevel.HIGH
                )
            
            # 경고 레벨 체크 (90% 이상)
            warning_threshold = max_allowed_exposure * Decimal('0.9')
            if total_exposure > warning_threshold:
                return RiskCheckResult(
                    approved=True,
                    reason=f"총 익스포저 경고: {total_exposure:,.0f}원 (한도의 {(total_exposure/max_allowed_exposure)*100:.1f}%)",
                    risk_level=RiskLevel.MEDIUM
                )
            
            return RiskCheckResult(approved=True, risk_level=RiskLevel.LOW)
            
        except Exception as e:
            logger.error(f"Error in TotalExposureRule: {e}")
            return RiskCheckResult(
                approved=False,
                reason=f"총 익스포저 규칙 검증 오류: {str(e)}",
                risk_level=RiskLevel.CRITICAL
            )


def get_risk_rules(risk_engine) -> List[BaseRiskRule]:
    """
    리스크 규칙 목록 반환
    
    Args:
        risk_engine: RiskEngine 인스턴스
        
    Returns:
        List[BaseRiskRule]: 활성화된 리스크 규칙들
    """
    rules = [
        # 핵심 리스크 규칙들 (우선순위 순)
        DailyLossRule(risk_engine),           # 1. 일일 손실 한도
        MonthlyLossRule(risk_engine),         # 2. 월간 손실 한도
        ConsecutiveLossRule(risk_engine),     # 3. 연속 손실 제한
        CashReserveRule(risk_engine),         # 4. 현금 보유량
        TotalExposureRule(risk_engine),       # 5. 총 익스포저 제한
        PositionSizeRule(risk_engine),        # 6. 포지션 크기 제한
        SectorExposureRule(risk_engine),      # 7. 섹터 익스포저 제한
        TradeFrequencyRule(risk_engine),      # 8. 거래 빈도 제한
    ]
    
    logger.info(f"Initialized {len(rules)} risk rules")
    return rules