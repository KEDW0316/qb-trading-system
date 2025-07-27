"""
Portfolio Risk Management - 포트폴리오 리스크 관리

포트폴리오 전체의 리스크를 분석하고 관리하는 시스템
"""

import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RiskCategory(Enum):
    """리스크 카테고리"""
    CONCENTRATION = "concentration"      # 집중도 리스크
    CORRELATION = "correlation"          # 상관관계 리스크
    VOLATILITY = "volatility"           # 변동성 리스크
    LIQUIDITY = "liquidity"             # 유동성 리스크
    SECTOR = "sector"                   # 섹터 리스크
    MARKET = "market"                   # 시장 리스크


@dataclass
class PortfolioRiskMetrics:
    """포트폴리오 리스크 지표"""
    timestamp: datetime
    
    # 전체 포트폴리오 지표
    portfolio_value: Decimal
    total_exposure: Decimal
    cash_ratio: float
    exposure_ratio: float
    
    # 집중도 지표
    max_position_weight: float
    top_5_concentration: float
    herfindahl_index: float
    
    # 변동성 지표
    portfolio_volatility: float
    var_95: Decimal  # 95% VaR
    expected_shortfall: Decimal  # CVaR
    
    # 상관관계 지표
    avg_correlation: float
    max_correlation: float
    correlation_risk_score: float
    
    # 섹터 분산도
    sector_count: int
    max_sector_weight: float
    sector_diversity_score: float
    
    # 유동성 지표
    avg_liquidity_score: float
    illiquid_position_ratio: float
    
    # 종합 리스크 점수
    overall_risk_score: float


@dataclass
class RiskAlert:
    """리스크 알림"""
    category: RiskCategory
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    message: str
    metric_value: float
    threshold: float
    recommendation: str
    timestamp: datetime


class PortfolioRiskManager:
    """포트폴리오 리스크 관리자"""
    
    def __init__(self, risk_engine):
        self.risk_engine = risk_engine
        self.db_manager = risk_engine.db_manager
        self.redis_manager = risk_engine.redis_manager
        self.event_bus = risk_engine.event_bus
        self.config = risk_engine.config
        
        # 리스크 임계값
        self.thresholds = {
            'max_position_weight': 0.15,          # 최대 종목 비중 15%
            'top_5_concentration': 0.50,          # 상위 5종목 비중 50%
            'max_sector_weight': 0.30,            # 최대 섹터 비중 30%
            'max_correlation': 0.80,              # 최대 상관계수 0.8
            'avg_correlation': 0.60,              # 평균 상관계수 0.6
            'portfolio_volatility': 0.25,         # 포트폴리오 변동성 25%
            'var_95_ratio': 0.05,                 # 95% VaR 비율 5%
            'illiquid_ratio': 0.20,               # 비유동성 포지션 비율 20%
        }
        
        logger.info("PortfolioRiskManager initialized")
    
    async def analyze_portfolio_risk(self) -> PortfolioRiskMetrics:
        """포트폴리오 리스크 분석"""
        try:
            logger.info("Starting portfolio risk analysis...")
            
            # 포트폴리오 기본 정보 조회
            portfolio_value = await self.risk_engine._get_portfolio_value()
            total_exposure = await self.risk_engine._get_total_exposure()
            cash_balance = await self.risk_engine._get_cash_balance()
            
            # 포지션 정보 조회
            positions = await self._get_all_positions()
            
            if not positions:
                return self._create_empty_metrics(portfolio_value, cash_balance)
            
            # 각 리스크 지표 계산
            concentration_metrics = await self._calculate_concentration_metrics(positions, portfolio_value)
            volatility_metrics = await self._calculate_volatility_metrics(positions, portfolio_value)
            correlation_metrics = await self._calculate_correlation_metrics(positions)
            sector_metrics = await self._calculate_sector_metrics(positions, portfolio_value)
            liquidity_metrics = await self._calculate_liquidity_metrics(positions)
            
            # 종합 리스크 점수 계산
            overall_risk_score = await self._calculate_overall_risk_score(
                concentration_metrics, volatility_metrics, correlation_metrics,
                sector_metrics, liquidity_metrics
            )
            
            # 리스크 메트릭 생성
            metrics = PortfolioRiskMetrics(
                timestamp=datetime.now(),
                portfolio_value=portfolio_value,
                total_exposure=total_exposure,
                cash_ratio=float(cash_balance / portfolio_value) if portfolio_value > 0 else 0.0,
                exposure_ratio=float(total_exposure / portfolio_value) if portfolio_value > 0 else 0.0,
                **concentration_metrics,
                **volatility_metrics,
                **correlation_metrics,
                **sector_metrics,
                **liquidity_metrics,
                overall_risk_score=overall_risk_score
            )
            
            # 리스크 메트릭 저장
            await self._save_risk_metrics(metrics)
            
            # 리스크 알림 확인
            alerts = await self._check_risk_thresholds(metrics)
            for alert in alerts:
                await self._publish_risk_alert(alert)
            
            logger.info(f"Portfolio risk analysis completed. Overall risk score: {overall_risk_score:.2f}")
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio risk: {e}")
            return self._create_empty_metrics(Decimal('0'), Decimal('0'))
    
    async def _get_all_positions(self) -> List[Dict[str, Any]]:
        """모든 포지션 정보 조회"""
        try:
            positions = []
            position_keys = await self.redis_manager.get_keys_by_pattern("positions:*")
            
            for key in position_keys:
                symbol = key.split(':')[1]
                position_data = await self.redis_manager.get_hash(key)
                
                if position_data:
                    quantity = int(position_data.get('quantity', 0))
                    if quantity != 0:
                        positions.append({
                            'symbol': symbol,
                            'quantity': quantity,
                            'average_price': float(position_data.get('average_price', 0)),
                            'market_price': float(position_data.get('market_price', 0)),
                            'market_value': float(position_data.get('market_value', 0)),
                            'unrealized_pnl': float(position_data.get('unrealized_pnl', 0)),
                            'weight': 0.0  # 나중에 계산
                        })
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting all positions: {e}")
            return []
    
    async def _calculate_concentration_metrics(
        self, 
        positions: List[Dict[str, Any]], 
        portfolio_value: Decimal
    ) -> Dict[str, float]:
        """집중도 지표 계산"""
        try:
            if not positions or portfolio_value <= 0:
                return {
                    'max_position_weight': 0.0,
                    'top_5_concentration': 0.0,
                    'herfindahl_index': 0.0
                }
            
            # 포지션 비중 계산
            total_value = float(portfolio_value)
            for position in positions:
                position['weight'] = position['market_value'] / total_value
            
            # 비중 순으로 정렬
            positions.sort(key=lambda x: x['weight'], reverse=True)
            
            # 최대 포지션 비중
            max_position_weight = positions[0]['weight'] if positions else 0.0
            
            # 상위 5종목 집중도
            top_5_concentration = sum(p['weight'] for p in positions[:5])
            
            # 허핀달 지수 (집중도 측정)
            herfindahl_index = sum(p['weight'] ** 2 for p in positions)
            
            return {
                'max_position_weight': max_position_weight,
                'top_5_concentration': top_5_concentration,
                'herfindahl_index': herfindahl_index
            }
            
        except Exception as e:
            logger.error(f"Error calculating concentration metrics: {e}")
            return {
                'max_position_weight': 0.0,
                'top_5_concentration': 0.0,
                'herfindahl_index': 0.0
            }
    
    async def _calculate_volatility_metrics(
        self, 
        positions: List[Dict[str, Any]], 
        portfolio_value: Decimal
    ) -> Dict[str, Any]:
        """변동성 지표 계산"""
        try:
            if not positions:
                return {
                    'portfolio_volatility': 0.0,
                    'var_95': Decimal('0'),
                    'expected_shortfall': Decimal('0')
                }
            
            # 개별 종목 변동성 조회
            volatilities = {}
            for position in positions:
                volatilities[position['symbol']] = await self._get_symbol_volatility(position['symbol'])
            
            # 포트폴리오 변동성 계산 (단순화된 버전)
            weighted_volatility = 0.0
            for position in positions:
                vol = volatilities.get(position['symbol'], 0.0)
                weighted_volatility += position['weight'] * vol
            
            # VaR 계산 (95% 신뢰수준, 정규분포 가정)
            # VaR = μ - 1.645 * σ * √t (1일 기준)
            var_95_ratio = 1.645 * weighted_volatility
            var_95 = portfolio_value * Decimal(var_95_ratio)
            
            # Expected Shortfall (CVaR) - VaR를 초과하는 손실의 기댓값
            es_ratio = 2.063 * weighted_volatility  # 정규분포에서 ES ≈ 1.25 * VaR
            expected_shortfall = portfolio_value * Decimal(es_ratio)
            
            return {
                'portfolio_volatility': weighted_volatility,
                'var_95': var_95,
                'expected_shortfall': expected_shortfall
            }
            
        except Exception as e:
            logger.error(f"Error calculating volatility metrics: {e}")
            return {
                'portfolio_volatility': 0.0,
                'var_95': Decimal('0'),
                'expected_shortfall': Decimal('0')
            }
    
    async def _calculate_correlation_metrics(self, positions: List[Dict[str, Any]]) -> Dict[str, float]:
        """상관관계 지표 계산"""
        try:
            if len(positions) < 2:
                return {
                    'avg_correlation': 0.0,
                    'max_correlation': 0.0,
                    'correlation_risk_score': 0.0
                }
            
            correlations = []
            symbols = [p['symbol'] for p in positions]
            
            # 모든 종목 쌍의 상관계수 계산
            for i, symbol1 in enumerate(symbols):
                for j, symbol2 in enumerate(symbols[i+1:], i+1):
                    correlation = await self._get_correlation(symbol1, symbol2)
                    correlations.append(abs(correlation))  # 절댓값 사용
            
            if not correlations:
                return {
                    'avg_correlation': 0.0,
                    'max_correlation': 0.0,
                    'correlation_risk_score': 0.0
                }
            
            avg_correlation = sum(correlations) / len(correlations)
            max_correlation = max(correlations)
            
            # 상관관계 리스크 점수 (높을수록 위험)
            correlation_risk_score = (avg_correlation * 0.6 + max_correlation * 0.4)
            
            return {
                'avg_correlation': avg_correlation,
                'max_correlation': max_correlation,
                'correlation_risk_score': correlation_risk_score
            }
            
        except Exception as e:
            logger.error(f"Error calculating correlation metrics: {e}")
            return {
                'avg_correlation': 0.0,
                'max_correlation': 0.0,
                'correlation_risk_score': 0.0
            }
    
    async def _calculate_sector_metrics(
        self, 
        positions: List[Dict[str, Any]], 
        portfolio_value: Decimal
    ) -> Dict[str, Any]:
        """섹터 분산도 지표 계산"""
        try:
            if not positions:
                return {
                    'sector_count': 0,
                    'max_sector_weight': 0.0,
                    'sector_diversity_score': 0.0
                }
            
            # 섹터별 비중 계산
            sector_weights = {}
            for position in positions:
                sector = await self._get_symbol_sector(position['symbol'])
                if sector not in sector_weights:
                    sector_weights[sector] = 0.0
                sector_weights[sector] += position['weight']
            
            sector_count = len(sector_weights)
            max_sector_weight = max(sector_weights.values()) if sector_weights else 0.0
            
            # 섹터 다양성 점수 (허핀달 지수의 역수)
            sector_hhi = sum(weight ** 2 for weight in sector_weights.values())
            sector_diversity_score = 1.0 / sector_hhi if sector_hhi > 0 else 0.0
            
            return {
                'sector_count': sector_count,
                'max_sector_weight': max_sector_weight,
                'sector_diversity_score': sector_diversity_score
            }
            
        except Exception as e:
            logger.error(f"Error calculating sector metrics: {e}")
            return {
                'sector_count': 0,
                'max_sector_weight': 0.0,
                'sector_diversity_score': 0.0
            }
    
    async def _calculate_liquidity_metrics(self, positions: List[Dict[str, Any]]) -> Dict[str, float]:
        """유동성 지표 계산"""
        try:
            if not positions:
                return {
                    'avg_liquidity_score': 0.0,
                    'illiquid_position_ratio': 0.0
                }
            
            liquidity_scores = []
            illiquid_weight = 0.0
            
            for position in positions:
                liquidity_score = await self._get_symbol_liquidity(position['symbol'])
                liquidity_scores.append(liquidity_score)
                
                # 유동성 점수가 낮은 경우 (0.3 미만) 비유동성으로 분류
                if liquidity_score < 0.3:
                    illiquid_weight += position['weight']
            
            avg_liquidity_score = sum(liquidity_scores) / len(liquidity_scores)
            
            return {
                'avg_liquidity_score': avg_liquidity_score,
                'illiquid_position_ratio': illiquid_weight
            }
            
        except Exception as e:
            logger.error(f"Error calculating liquidity metrics: {e}")
            return {
                'avg_liquidity_score': 0.0,
                'illiquid_position_ratio': 0.0
            }
    
    async def _calculate_overall_risk_score(
        self,
        concentration_metrics: Dict[str, float],
        volatility_metrics: Dict[str, Any],
        correlation_metrics: Dict[str, float],
        sector_metrics: Dict[str, Any],
        liquidity_metrics: Dict[str, float]
    ) -> float:
        """종합 리스크 점수 계산 (0.0 - 1.0)"""
        try:
            # 각 리스크 요소별 점수 계산 (0.0 - 1.0)
            concentration_score = min(1.0, concentration_metrics['max_position_weight'] / 0.2)
            volatility_score = min(1.0, volatility_metrics['portfolio_volatility'] / 0.3)
            correlation_score = correlation_metrics['correlation_risk_score']
            sector_score = min(1.0, sector_metrics['max_sector_weight'] / 0.4)
            liquidity_score = liquidity_metrics['illiquid_position_ratio']
            
            # 가중 평균으로 종합 점수 계산
            weights = {
                'concentration': 0.25,
                'volatility': 0.25,
                'correlation': 0.20,
                'sector': 0.15,
                'liquidity': 0.15
            }
            
            overall_score = (
                concentration_score * weights['concentration'] +
                volatility_score * weights['volatility'] +
                correlation_score * weights['correlation'] +
                sector_score * weights['sector'] +
                liquidity_score * weights['liquidity']
            )
            
            return min(1.0, max(0.0, overall_score))
            
        except Exception as e:
            logger.error(f"Error calculating overall risk score: {e}")
            return 0.5  # 기본값
    
    async def _get_symbol_volatility(self, symbol: str) -> float:
        """종목 변동성 조회"""
        try:
            # TODO: 실제 시장 데이터에서 변동성 계산
            default_volatilities = {
                '005930': 0.25,  # 삼성전자
                '000660': 0.35,  # SK하이닉스
                '035420': 0.30,  # NAVER
            }
            return default_volatilities.get(symbol, 0.30)
            
        except Exception as e:
            logger.error(f"Error getting volatility for {symbol}: {e}")
            return 0.30
    
    async def _get_correlation(self, symbol1: str, symbol2: str) -> float:
        """두 종목 간 상관계수 조회"""
        try:
            # TODO: 실제 시장 데이터에서 상관계수 계산
            # 임시로 기본값 사용
            if symbol1 == symbol2:
                return 1.0
            
            # 같은 섹터면 높은 상관관계, 다른 섹터면 낮은 상관관계
            sector1 = await self._get_symbol_sector(symbol1)
            sector2 = await self._get_symbol_sector(symbol2)
            
            if sector1 == sector2:
                return 0.6  # 같은 섹터
            else:
                return 0.3  # 다른 섹터
            
        except Exception as e:
            logger.error(f"Error getting correlation between {symbol1} and {symbol2}: {e}")
            return 0.3
    
    async def _get_symbol_sector(self, symbol: str) -> str:
        """종목 섹터 조회"""
        try:
            # TODO: 실제 종목 정보에서 섹터 조회
            sector_mapping = {
                '005930': 'Technology',
                '000660': 'Technology', 
                '035420': 'Technology',
                '051910': 'Chemical',
                '006400': 'Technology',
            }
            return sector_mapping.get(symbol, 'Other')
            
        except Exception as e:
            logger.error(f"Error getting sector for {symbol}: {e}")
            return 'Other'
    
    async def _get_symbol_liquidity(self, symbol: str) -> float:
        """종목 유동성 점수 조회 (0.0 - 1.0)"""
        try:
            # TODO: 실제 거래량 데이터에서 유동성 계산
            liquidity_scores = {
                '005930': 1.0,  # 삼성전자 - 높은 유동성
                '000660': 0.8,  # SK하이닉스
                '035420': 0.7,  # NAVER
            }
            return liquidity_scores.get(symbol, 0.5)
            
        except Exception as e:
            logger.error(f"Error getting liquidity for {symbol}: {e}")
            return 0.5
    
    async def _check_risk_thresholds(self, metrics: PortfolioRiskMetrics) -> List[RiskAlert]:
        """리스크 임계값 확인"""
        alerts = []
        
        try:
            # 집중도 체크
            if metrics.max_position_weight > self.thresholds['max_position_weight']:
                alerts.append(RiskAlert(
                    category=RiskCategory.CONCENTRATION,
                    severity='HIGH',
                    message=f"최대 종목 비중 초과: {metrics.max_position_weight:.1%}",
                    metric_value=metrics.max_position_weight,
                    threshold=self.thresholds['max_position_weight'],
                    recommendation="포지션 크기를 줄여 집중도를 낮추세요",
                    timestamp=datetime.now()
                ))
            
            # 섹터 집중도 체크
            if metrics.max_sector_weight > self.thresholds['max_sector_weight']:
                alerts.append(RiskAlert(
                    category=RiskCategory.SECTOR,
                    severity='MEDIUM',
                    message=f"최대 섹터 비중 초과: {metrics.max_sector_weight:.1%}",
                    metric_value=metrics.max_sector_weight,
                    threshold=self.thresholds['max_sector_weight'],
                    recommendation="섹터 분산을 고려한 투자를 권장합니다",
                    timestamp=datetime.now()
                ))
            
            # 상관관계 체크
            if metrics.avg_correlation > self.thresholds['avg_correlation']:
                alerts.append(RiskAlert(
                    category=RiskCategory.CORRELATION,
                    severity='MEDIUM',
                    message=f"높은 평균 상관계수: {metrics.avg_correlation:.2f}",
                    metric_value=metrics.avg_correlation,
                    threshold=self.thresholds['avg_correlation'],
                    recommendation="상관관계가 낮은 종목으로 분산투자하세요",
                    timestamp=datetime.now()
                ))
            
            # 변동성 체크
            if metrics.portfolio_volatility > self.thresholds['portfolio_volatility']:
                alerts.append(RiskAlert(
                    category=RiskCategory.VOLATILITY,
                    severity='HIGH',
                    message=f"높은 포트폴리오 변동성: {metrics.portfolio_volatility:.1%}",
                    metric_value=metrics.portfolio_volatility,
                    threshold=self.thresholds['portfolio_volatility'],
                    recommendation="변동성이 낮은 종목 비중을 늘리세요",
                    timestamp=datetime.now()
                ))
            
            # 유동성 체크
            if metrics.illiquid_position_ratio > self.thresholds['illiquid_ratio']:
                alerts.append(RiskAlert(
                    category=RiskCategory.LIQUIDITY,
                    severity='MEDIUM',
                    message=f"높은 비유동성 포지션 비율: {metrics.illiquid_position_ratio:.1%}",
                    metric_value=metrics.illiquid_position_ratio,
                    threshold=self.thresholds['illiquid_ratio'],
                    recommendation="유동성이 높은 종목 비중을 늘리세요",
                    timestamp=datetime.now()
                ))
            
        except Exception as e:
            logger.error(f"Error checking risk thresholds: {e}")
        
        return alerts
    
    async def _save_risk_metrics(self, metrics: PortfolioRiskMetrics):
        """리스크 메트릭 저장"""
        try:
            # Redis에 현재 메트릭 저장
            metrics_data = {
                'timestamp': metrics.timestamp.isoformat(),
                'portfolio_value': str(metrics.portfolio_value),
                'overall_risk_score': metrics.overall_risk_score,
                'max_position_weight': metrics.max_position_weight,
                'portfolio_volatility': metrics.portfolio_volatility,
                'avg_correlation': metrics.avg_correlation,
                'sector_count': metrics.sector_count,
                'avg_liquidity_score': metrics.avg_liquidity_score
            }
            
            await self.redis_manager.set_hash("portfolio_risk:current", metrics_data, ttl=3600)
            
            # 시간별 이력 저장
            history_key = f"portfolio_risk:history:{metrics.timestamp.strftime('%Y-%m-%d_%H')}"
            await self.redis_manager.set_hash(history_key, metrics_data, ttl=86400 * 7)
            
        except Exception as e:
            logger.error(f"Error saving risk metrics: {e}")
    
    async def _publish_risk_alert(self, alert: RiskAlert):
        """리스크 알림 발행"""
        try:
            event = self.event_bus.create_event(
                'PORTFOLIO_RISK_ALERT',
                source="PortfolioRiskManager",
                data={
                    'category': alert.category.value,
                    'severity': alert.severity,
                    'message': alert.message,
                    'metric_value': alert.metric_value,
                    'threshold': alert.threshold,
                    'recommendation': alert.recommendation,
                    'timestamp': alert.timestamp.isoformat()
                }
            )
            self.event_bus.publish(event)
            
            logger.warning(f"Portfolio Risk Alert [{alert.severity}] {alert.category.value}: {alert.message}")
            
        except Exception as e:
            logger.error(f"Error publishing risk alert: {e}")
    
    def _create_empty_metrics(self, portfolio_value: Decimal, cash_balance: Decimal) -> PortfolioRiskMetrics:
        """빈 메트릭 생성"""
        return PortfolioRiskMetrics(
            timestamp=datetime.now(),
            portfolio_value=portfolio_value,
            total_exposure=Decimal('0'),
            cash_ratio=1.0 if portfolio_value > 0 else 0.0,
            exposure_ratio=0.0,
            max_position_weight=0.0,
            top_5_concentration=0.0,
            herfindahl_index=0.0,
            portfolio_volatility=0.0,
            var_95=Decimal('0'),
            expected_shortfall=Decimal('0'),
            avg_correlation=0.0,
            max_correlation=0.0,
            correlation_risk_score=0.0,
            sector_count=0,
            max_sector_weight=0.0,
            sector_diversity_score=0.0,
            avg_liquidity_score=0.0,
            illiquid_position_ratio=0.0,
            overall_risk_score=0.0
        )
    
    async def get_risk_summary(self) -> Dict[str, Any]:
        """리스크 요약 정보 조회"""
        try:
            # 현재 리스크 메트릭 조회
            current_metrics = await self.redis_manager.get_hash("portfolio_risk:current")
            
            if not current_metrics:
                return {'error': 'No risk metrics available'}
            
            return {
                'timestamp': current_metrics.get('timestamp', ''),
                'portfolio_value': float(current_metrics.get('portfolio_value', 0)),
                'overall_risk_score': float(current_metrics.get('overall_risk_score', 0)),
                'risk_level': self._get_risk_level(float(current_metrics.get('overall_risk_score', 0))),
                'key_metrics': {
                    'max_position_weight': float(current_metrics.get('max_position_weight', 0)),
                    'portfolio_volatility': float(current_metrics.get('portfolio_volatility', 0)),
                    'avg_correlation': float(current_metrics.get('avg_correlation', 0)),
                    'sector_count': int(current_metrics.get('sector_count', 0)),
                    'avg_liquidity_score': float(current_metrics.get('avg_liquidity_score', 0))
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting risk summary: {e}")
            return {'error': str(e)}
    
    def _get_risk_level(self, risk_score: float) -> str:
        """리스크 점수를 레벨로 변환"""
        if risk_score >= 0.8:
            return 'CRITICAL'
        elif risk_score >= 0.6:
            return 'HIGH'
        elif risk_score >= 0.4:
            return 'MEDIUM'
        else:
            return 'LOW'