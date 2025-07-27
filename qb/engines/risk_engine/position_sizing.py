"""
Position Sizing Algorithms - 포지션 크기 관리 알고리즘

다양한 포지션 크기 계산 알고리즘을 제공합니다.
리스크 기반, 변동성 기반, 목표 기반 포지션 크기 계산
"""

import logging
import math
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class PositionSizeResult:
    """포지션 크기 계산 결과"""
    recommended_quantity: int
    risk_amount: Decimal
    position_value: Decimal
    risk_ratio: float
    stop_loss_price: Optional[Decimal]
    reasoning: str
    confidence: float  # 0.0 - 1.0


class BasePositionSizer(ABC):
    """포지션 크기 계산 기본 클래스"""
    
    def __init__(self, risk_engine):
        self.risk_engine = risk_engine
        self.name = self.__class__.__name__
        
    @abstractmethod
    async def calculate_position_size(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        target_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PositionSizeResult:
        """포지션 크기 계산"""
        pass


class FixedRiskPositionSizer(BasePositionSizer):
    """고정 리스크 기반 포지션 크기 계산"""
    
    async def calculate_position_size(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        target_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PositionSizeResult:
        """
        고정 리스크 비율 기반 포지션 크기 계산
        
        포트폴리오의 일정 비율만큼 리스크를 감수하도록 포지션 크기 계산
        """
        try:
            entry_decimal = Decimal(str(entry_price))
            
            # 포트폴리오 가치 조회
            portfolio_value = await self.risk_engine._get_portfolio_value()
            
            # 리스크 비율 설정 (기본 1%)
            risk_ratio = self.risk_engine.config.get('position_risk_ratio', 0.01)
            max_risk_amount = portfolio_value * Decimal(risk_ratio)
            
            # 스탑로스가 없으면 기본 스탑로스 비율 사용
            if stop_loss_price is None:
                stop_loss_pct = self.risk_engine.config.get('default_stop_loss_pct', 3.0)
                if side == 'BUY':
                    stop_loss_price = float(entry_decimal * (1 - Decimal(stop_loss_pct / 100)))
                else:
                    stop_loss_price = float(entry_decimal * (1 + Decimal(stop_loss_pct / 100)))
            
            stop_loss_decimal = Decimal(str(stop_loss_price))
            
            # 주당 리스크 계산
            price_diff = abs(entry_decimal - stop_loss_decimal)
            if price_diff == 0:
                return PositionSizeResult(
                    recommended_quantity=0,
                    risk_amount=Decimal('0'),
                    position_value=Decimal('0'),
                    risk_ratio=0.0,
                    stop_loss_price=stop_loss_decimal,
                    reasoning="스탑로스와 진입가가 동일하여 계산 불가",
                    confidence=0.0
                )
            
            # 포지션 크기 계산
            recommended_quantity = int(max_risk_amount / price_diff)
            
            # 최대/최소 제한 적용
            max_position_value = portfolio_value * Decimal(
                self.risk_engine.config.get('max_position_size_ratio', 0.1)
            )
            max_quantity_by_value = int(max_position_value / entry_decimal)
            recommended_quantity = min(recommended_quantity, max_quantity_by_value)
            
            # 최소 수량 확인
            min_quantity = self.risk_engine.config.get('min_position_quantity', 1)
            if recommended_quantity < min_quantity:
                recommended_quantity = 0
            
            # 결과 계산
            position_value = entry_decimal * recommended_quantity
            actual_risk = price_diff * recommended_quantity
            actual_risk_ratio = float(actual_risk / portfolio_value) if portfolio_value > 0 else 0.0
            
            reasoning = f"고정 리스크 {risk_ratio:.1%} 기반 계산 (스탑로스: {stop_loss_price:,.0f})"
            confidence = 0.9 if recommended_quantity > 0 else 0.3
            
            return PositionSizeResult(
                recommended_quantity=recommended_quantity,
                risk_amount=actual_risk,
                position_value=position_value,
                risk_ratio=actual_risk_ratio,
                stop_loss_price=stop_loss_decimal,
                reasoning=reasoning,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error in FixedRiskPositionSizer: {e}")
            return PositionSizeResult(
                recommended_quantity=0,
                risk_amount=Decimal('0'),
                position_value=Decimal('0'),
                risk_ratio=0.0,
                stop_loss_price=None,
                reasoning=f"계산 오류: {str(e)}",
                confidence=0.0
            )


class VolatilityBasedPositionSizer(BasePositionSizer):
    """변동성 기반 포지션 크기 계산"""
    
    async def calculate_position_size(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        target_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PositionSizeResult:
        """
        변동성(ATR) 기반 포지션 크기 계산
        
        종목의 변동성에 따라 포지션 크기를 조정
        """
        try:
            entry_decimal = Decimal(str(entry_price))
            
            # 포트폴리오 가치 조회
            portfolio_value = await self.risk_engine._get_portfolio_value()
            
            # 변동성 조회 (ATR)
            volatility = await self._get_volatility(symbol)
            if volatility <= 0:
                # 변동성 정보가 없으면 고정 리스크 방식으로 fallback
                fixed_sizer = FixedRiskPositionSizer(self.risk_engine)
                return await fixed_sizer.calculate_position_size(
                    symbol, side, entry_price, stop_loss_price, target_price, metadata
                )
            
            # 변동성 기반 리스크 조정
            base_risk_ratio = self.risk_engine.config.get('position_risk_ratio', 0.01)
            volatility_multiplier = min(2.0, max(0.5, 1.0 / volatility))  # 변동성이 높으면 포지션 축소
            
            adjusted_risk_ratio = base_risk_ratio * volatility_multiplier
            max_risk_amount = portfolio_value * Decimal(adjusted_risk_ratio)
            
            # ATR 기반 스탑로스 계산
            if stop_loss_price is None:
                atr_multiplier = 2.0  # ATR의 2배
                if side == 'BUY':
                    stop_loss_price = float(entry_decimal - Decimal(volatility * atr_multiplier))
                else:
                    stop_loss_price = float(entry_decimal + Decimal(volatility * atr_multiplier))
            
            stop_loss_decimal = Decimal(str(stop_loss_price))
            
            # 포지션 크기 계산
            price_diff = abs(entry_decimal - stop_loss_decimal)
            if price_diff == 0:
                return PositionSizeResult(
                    recommended_quantity=0,
                    risk_amount=Decimal('0'),
                    position_value=Decimal('0'),
                    risk_ratio=0.0,
                    stop_loss_price=stop_loss_decimal,
                    reasoning="스탑로스 계산 오류",
                    confidence=0.0
                )
            
            recommended_quantity = int(max_risk_amount / price_diff)
            
            # 제한 적용
            max_position_value = portfolio_value * Decimal(
                self.risk_engine.config.get('max_position_size_ratio', 0.1)
            )
            max_quantity_by_value = int(max_position_value / entry_decimal)
            recommended_quantity = min(recommended_quantity, max_quantity_by_value)
            
            if recommended_quantity < 1:
                recommended_quantity = 0
            
            # 결과 계산
            position_value = entry_decimal * recommended_quantity
            actual_risk = price_diff * recommended_quantity
            actual_risk_ratio = float(actual_risk / portfolio_value) if portfolio_value > 0 else 0.0
            
            reasoning = f"변동성 기반 계산 (ATR: {volatility:.2f}, 조정 비율: {volatility_multiplier:.2f})"
            confidence = 0.8 if recommended_quantity > 0 else 0.3
            
            return PositionSizeResult(
                recommended_quantity=recommended_quantity,
                risk_amount=actual_risk,
                position_value=position_value,
                risk_ratio=actual_risk_ratio,
                stop_loss_price=stop_loss_decimal,
                reasoning=reasoning,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error in VolatilityBasedPositionSizer: {e}")
            return PositionSizeResult(
                recommended_quantity=0,
                risk_amount=Decimal('0'),
                position_value=Decimal('0'),
                risk_ratio=0.0,
                stop_loss_price=None,
                reasoning=f"변동성 기반 계산 오류: {str(e)}",
                confidence=0.0
            )
    
    async def _get_volatility(self, symbol: str) -> float:
        """종목의 변동성(ATR) 조회"""
        try:
            # TODO: 실제 시장 데이터에서 ATR 계산
            # 임시로 기본값 사용
            default_volatility = {
                '005930': 0.03,  # 삼성전자
                '000660': 0.05,  # SK하이닉스
                '035420': 0.04,  # NAVER
            }
            return default_volatility.get(symbol, 0.04)  # 기본 4%
            
        except Exception as e:
            logger.error(f"Error getting volatility for {symbol}: {e}")
            return 0.04


class KellyPositionSizer(BasePositionSizer):
    """켈리 공식 기반 포지션 크기 계산"""
    
    async def calculate_position_size(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        target_price: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PositionSizeResult:
        """
        켈리 공식 기반 포지션 크기 계산
        
        f = (bp - q) / b
        f: 베팅 비율
        b: 승률
        p: 승리 확률
        q: 패배 확률 (1-p)
        """
        try:
            entry_decimal = Decimal(str(entry_price))
            
            # 포트폴리오 가치 조회
            portfolio_value = await self.risk_engine._get_portfolio_value()
            
            # 승률과 손익비 조회
            win_rate, avg_win_loss_ratio = await self._get_strategy_stats(symbol)
            
            if win_rate <= 0 or avg_win_loss_ratio <= 0:
                # 통계가 없으면 고정 리스크 방식으로 fallback
                fixed_sizer = FixedRiskPositionSizer(self.risk_engine)
                return await fixed_sizer.calculate_position_size(
                    symbol, side, entry_price, stop_loss_price, target_price, metadata
                )
            
            # 켈리 공식 계산
            p = win_rate  # 승리 확률
            q = 1 - p     # 패배 확률
            b = avg_win_loss_ratio  # 평균 손익비
            
            kelly_fraction = (b * p - q) / b
            
            # 켈리 비율 제한 (최대 25%)
            kelly_fraction = max(0, min(0.25, kelly_fraction))
            
            # 보수적 조정 (켈리의 25%만 사용)
            conservative_kelly = kelly_fraction * 0.25
            
            max_position_value = portfolio_value * Decimal(conservative_kelly)
            
            # 스탑로스 설정
            if stop_loss_price is None:
                stop_loss_pct = self.risk_engine.config.get('default_stop_loss_pct', 3.0)
                if side == 'BUY':
                    stop_loss_price = float(entry_decimal * (1 - Decimal(stop_loss_pct / 100)))
                else:
                    stop_loss_price = float(entry_decimal * (1 + Decimal(stop_loss_pct / 100)))
            
            stop_loss_decimal = Decimal(str(stop_loss_price))
            
            # 포지션 크기 계산
            recommended_quantity = int(max_position_value / entry_decimal)
            
            # 제한 적용
            max_position_ratio = self.risk_engine.config.get('max_position_size_ratio', 0.1)
            max_quantity_by_ratio = int(portfolio_value * Decimal(max_position_ratio) / entry_decimal)
            recommended_quantity = min(recommended_quantity, max_quantity_by_ratio)
            
            if recommended_quantity < 1:
                recommended_quantity = 0
            
            # 결과 계산
            position_value = entry_decimal * recommended_quantity
            price_diff = abs(entry_decimal - stop_loss_decimal)
            actual_risk = price_diff * recommended_quantity
            actual_risk_ratio = float(actual_risk / portfolio_value) if portfolio_value > 0 else 0.0
            
            reasoning = f"켈리 공식 기반 (승률: {win_rate:.1%}, 손익비: {avg_win_loss_ratio:.2f}, 켈리: {kelly_fraction:.1%})"
            confidence = 0.7 if recommended_quantity > 0 else 0.2
            
            return PositionSizeResult(
                recommended_quantity=recommended_quantity,
                risk_amount=actual_risk,
                position_value=position_value,
                risk_ratio=actual_risk_ratio,
                stop_loss_price=stop_loss_decimal,
                reasoning=reasoning,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error in KellyPositionSizer: {e}")
            return PositionSizeResult(
                recommended_quantity=0,
                risk_amount=Decimal('0'),
                position_value=Decimal('0'),
                risk_ratio=0.0,
                stop_loss_price=None,
                reasoning=f"켈리 공식 계산 오류: {str(e)}",
                confidence=0.0
            )
    
    async def _get_strategy_stats(self, symbol: str) -> Tuple[float, float]:
        """전략 통계 조회 (승률, 평균 손익비)"""
        try:
            # TODO: 실제 거래 이력에서 통계 계산
            # 임시로 기본값 사용
            default_stats = {
                '005930': (0.55, 1.2),  # 승률 55%, 손익비 1.2
                '000660': (0.52, 1.1),  # 승률 52%, 손익비 1.1
                '035420': (0.58, 1.3),  # 승률 58%, 손익비 1.3
            }
            return default_stats.get(symbol, (0.50, 1.0))  # 기본값
            
        except Exception as e:
            logger.error(f"Error getting strategy stats for {symbol}: {e}")
            return (0.50, 1.0)


class PositionSizeManager:
    """포지션 크기 관리자"""
    
    def __init__(self, risk_engine):
        self.risk_engine = risk_engine
        self.sizers = {
            'fixed_risk': FixedRiskPositionSizer(risk_engine),
            'volatility': VolatilityBasedPositionSizer(risk_engine),
            'kelly': KellyPositionSizer(risk_engine)
        }
        
        logger.info("PositionSizeManager initialized")
    
    async def calculate_optimal_position_size(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss_price: Optional[float] = None,
        target_price: Optional[float] = None,
        strategy: str = 'fixed_risk',
        metadata: Optional[Dict[str, Any]] = None
    ) -> PositionSizeResult:
        """
        최적 포지션 크기 계산
        
        Args:
            symbol: 종목 코드
            side: 매수/매도 ('BUY' or 'SELL')
            entry_price: 진입 가격
            stop_loss_price: 손절 가격
            target_price: 목표 가격
            strategy: 계산 전략 ('fixed_risk', 'volatility', 'kelly')
            metadata: 추가 메타데이터
            
        Returns:
            PositionSizeResult: 포지션 크기 계산 결과
        """
        try:
            # 선택된 전략으로 계산
            if strategy in self.sizers:
                sizer = self.sizers[strategy]
            else:
                logger.warning(f"Unknown strategy '{strategy}', using fixed_risk")
                sizer = self.sizers['fixed_risk']
            
            result = await sizer.calculate_position_size(
                symbol, side, entry_price, stop_loss_price, target_price, metadata
            )
            
            # 최종 검증
            result = await self._validate_position_size(result, symbol, side, entry_price)
            
            logger.info(f"Position size calculated for {symbol}: {result.recommended_quantity} shares "
                       f"(strategy: {strategy}, confidence: {result.confidence:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return PositionSizeResult(
                recommended_quantity=0,
                risk_amount=Decimal('0'),
                position_value=Decimal('0'),
                risk_ratio=0.0,
                stop_loss_price=None,
                reasoning=f"포지션 크기 계산 오류: {str(e)}",
                confidence=0.0
            )
    
    async def _validate_position_size(
        self,
        result: PositionSizeResult,
        symbol: str,
        side: str,
        entry_price: float
    ) -> PositionSizeResult:
        """포지션 크기 최종 검증"""
        try:
            if result.recommended_quantity <= 0:
                return result
            
            # 현금 잔고 확인
            cash_balance = await self.risk_engine._get_cash_balance()
            required_cash = result.position_value
            
            if required_cash > cash_balance:
                # 현금 부족 시 수량 조정
                max_quantity = int(cash_balance / Decimal(str(entry_price)))
                result.recommended_quantity = max_quantity
                result.position_value = Decimal(str(entry_price)) * max_quantity
                result.reasoning += f" (현금 부족으로 수량 조정: {max_quantity})"
                result.confidence *= 0.8
            
            # 최소 주문 단위 확인
            min_quantity = self.risk_engine.config.get('min_position_quantity', 1)
            if result.recommended_quantity < min_quantity:
                result.recommended_quantity = 0
                result.position_value = Decimal('0')
                result.reasoning += " (최소 주문 단위 미달)"
                result.confidence = 0.0
            
            return result
            
        except Exception as e:
            logger.error(f"Error validating position size: {e}")
            result.reasoning += f" (검증 오류: {str(e)})"
            result.confidence *= 0.5
            return result
    
    async def get_current_position_sizes(self) -> Dict[str, Dict[str, Any]]:
        """현재 포지션 크기 정보 조회"""
        try:
            positions = {}
            
            # Redis에서 모든 포지션 조회
            position_keys = await self.risk_engine.redis_manager.get_keys_by_pattern("positions:*")
            
            for key in position_keys:
                symbol = key.split(':')[1]
                position_data = await self.risk_engine.redis_manager.get_hash(key)
                
                if position_data:
                    quantity = int(position_data.get('quantity', 0))
                    if quantity != 0:
                        positions[symbol] = {
                            'quantity': quantity,
                            'average_price': float(position_data.get('average_price', 0)),
                            'market_value': float(position_data.get('market_value', 0)),
                            'unrealized_pnl': float(position_data.get('unrealized_pnl', 0)),
                            'updated_at': position_data.get('updated_at', '')
                        }
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting current position sizes: {e}")
            return {}