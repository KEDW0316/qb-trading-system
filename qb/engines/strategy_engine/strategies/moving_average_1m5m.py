"""
1분봉_5분봉 전략 (Moving Average 1M5M Strategy)

Made by Beyonse 2025.01.11 기반으로 구현
1분봉 종가와 최근 5분간 1분봉 종가의 평균을 비교하여 매매 신호를 생성하는 전략
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, time
import logging

from ..base import BaseStrategy, MarketData, TradingSignal

logger = logging.getLogger(__name__)


class MovingAverage1M5MStrategy(BaseStrategy):
    """
    1분봉_5분봉 전략
    
    매수 조건: 1분봉 종가 > 최근 5분간 1분봉 종가의 평균
    매도 조건: 1분봉 종가 <= 최근 5분간 1분봉 종가의 평균
    
    특징:
    - 이미 보유한 경우 추가 매수 안함 (홀딩)
    - 15:20 장마감시 강제 매도
    - 끼 있는 종목 (최근 6개월간 15% 이상 상승 경험) 대상
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "ma_period": 5,  # 이동평균 기간 (5분)
            "confidence_threshold": 0.7,  # 신호 신뢰도 임계값
            "market_close_time": "15:20",  # 장마감 시간
            "enable_forced_sell": True,  # 장마감 강제매도 활성화
            "weight_multiplier": 1.0,  # 가중치 승수 (향후 고도화용)
            "min_volume_threshold": 30_000_000_000,  # 최소 거래대금 (300억원)
            "enable_volume_filter": True,  # 거래대금 필터 활성화
        }
        super().__init__(params or default_params)
        
        # 포지션 상태 추적
        self.current_position = {}  # symbol -> {'quantity': int, 'entry_price': float, 'entry_time': datetime}
        
        # 장마감 시간 파싱
        self.market_close_time = self._parse_time(self.params.get("market_close_time", "15:20"))

    def _parse_time(self, time_str: str) -> time:
        """시간 문자열을 time 객체로 변환"""
        try:
            hour, minute = map(int, time_str.split(":"))
            return time(hour, minute)
        except:
            return time(15, 20)  # 기본값

    async def analyze(self, market_data: MarketData) -> Optional[TradingSignal]:
        """
        시장 데이터 분석 및 거래 신호 생성
        
        Args:
            market_data: 1분봉 시장 데이터
            
        Returns:
            TradingSignal: 거래 신호 또는 None
        """
        try:
            symbol = market_data.symbol
            current_time = market_data.timestamp
            current_price = market_data.close
            
            # 1분봉 데이터가 아닌 경우 무시
            if market_data.interval_type != "1m":
                return None
            
            # 필요한 지표 데이터 확인
            indicators = market_data.indicators or {}
            ma_5m = indicators.get(f"sma_{self.params['ma_period']}")
            
            if ma_5m is None:
                logger.warning(f"Missing MA data for {symbol}")
                return None
            
            # 거래대금 필터 확인 (활성화된 경우)
            if self.params.get("enable_volume_filter", True):
                avg_volume = indicators.get("avg_volume_5d", 0)
                if avg_volume < self.params.get("min_volume_threshold", 30_000_000_000):
                    return None
            
            # 장마감 시간 체크 - 강제 매도
            if self._is_market_close_time(current_time):
                return await self._handle_market_close(symbol, current_price, current_time)
            
            # 현재 포지션 상태 확인
            has_position = symbol in self.current_position
            
            # 가중치 적용 (향후 고도화용)
            weighted_ma = ma_5m * self.params.get("weight_multiplier", 1.0)
            
            # 매매 신호 생성
            if current_price > weighted_ma:
                # 매수 신호
                if not has_position:
                    return await self._generate_buy_signal(symbol, current_price, current_time, ma_5m)
                else:
                    # 이미 보유 중 - 홀딩
                    logger.debug(f"Holding position for {symbol} (price: {current_price} > MA: {ma_5m})")
                    return None
            
            elif current_price <= weighted_ma:
                # 매도 신호
                if has_position:
                    return await self._generate_sell_signal(symbol, current_price, current_time, ma_5m)
                else:
                    # 포지션 없음 - 관망
                    logger.debug(f"Watching {symbol} (price: {current_price} <= MA: {ma_5m})")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing market data for {market_data.symbol}: {e}")
            return None

    async def _generate_buy_signal(self, symbol: str, price: float, 
                                 timestamp: datetime, ma_value: float) -> TradingSignal:
        """매수 신호 생성"""
        
        # 신뢰도 계산 (가격이 이동평균을 얼마나 상회하는지)
        price_ratio = price / ma_value
        confidence = min(0.95, max(0.5, (price_ratio - 1.0) * 10 + 0.7))
        
        # 포지션 기록
        self.current_position[symbol] = {
            'quantity': 0,  # 실제 수량은 주문 엔진에서 결정
            'entry_price': price,
            'entry_time': timestamp
        }
        
        return TradingSignal(
            action='BUY',
            symbol=symbol,
            confidence=confidence,
            price=price,
            quantity=None,  # 주문 엔진에서 결정
            reason=f"1분봉 종가({price}) > 5분 평균({ma_value:.2f})",
            metadata={
                'strategy': '1분봉_5분봉',
                'current_price': price,
                'ma_5m': ma_value,
                'price_ratio': price_ratio,
                'signal_type': 'momentum_buy'
            },
            timestamp=timestamp
        )

    async def _generate_sell_signal(self, symbol: str, price: float,
                                  timestamp: datetime, ma_value: float) -> TradingSignal:
        """매도 신호 생성"""
        
        position = self.current_position.get(symbol, {})
        entry_price = position.get('entry_price', price)
        
        # 수익률 계산
        return_rate = (price - entry_price) / entry_price if entry_price > 0 else 0
        
        # 신뢰도 계산
        confidence = 0.8 if return_rate > 0 else 0.9  # 손실시 더 높은 신뢰도로 매도
        
        # 포지션 제거
        if symbol in self.current_position:
            del self.current_position[symbol]
        
        return TradingSignal(
            action='SELL',
            symbol=symbol,
            confidence=confidence,
            price=price,
            quantity=None,  # 보유 수량 전체
            reason=f"1분봉 종가({price}) <= 5분 평균({ma_value:.2f})",
            metadata={
                'strategy': '1분봉_5분봉',
                'current_price': price,
                'ma_5m': ma_value,
                'entry_price': entry_price,
                'return_rate': return_rate,
                'signal_type': 'momentum_sell'
            },
            timestamp=timestamp
        )

    async def _handle_market_close(self, symbol: str, price: float, 
                                 timestamp: datetime) -> Optional[TradingSignal]:
        """장마감 시간 처리 - 강제 매도"""
        
        if not self.params.get("enable_forced_sell", True):
            return None
        
        if symbol not in self.current_position:
            return None
        
        position = self.current_position[symbol]
        entry_price = position.get('entry_price', price)
        return_rate = (price - entry_price) / entry_price if entry_price > 0 else 0
        
        # 포지션 제거
        del self.current_position[symbol]
        
        return TradingSignal(
            action='SELL',
            symbol=symbol,
            confidence=1.0,  # 강제 매도는 최고 신뢰도
            price=None,  # 시장가
            quantity=None,  # 보유 수량 전체
            reason=f"장마감 강제매도 (15:20)",
            metadata={
                'strategy': '1분봉_5분봉',
                'current_price': price,
                'entry_price': entry_price,
                'return_rate': return_rate,
                'signal_type': 'forced_market_close_sell',
                'order_type': 'market'
            },
            timestamp=timestamp
        )

    def _is_market_close_time(self, current_time: datetime) -> bool:
        """장마감 시간인지 확인"""
        current_time_only = current_time.time()
        return current_time_only >= self.market_close_time

    def get_required_indicators(self) -> List[str]:
        """필요한 기술적 지표 목록 반환"""
        return [
            f"sma_{self.params['ma_period']}",  # 5분 단순이동평균
            "avg_volume_5d",  # 5일 평균 거래대금
            "price_change_6m_max",  # 6개월 최대 상승률 (끼 있는 종목 필터용)
        ]

    def get_parameter_schema(self) -> Dict[str, Dict[str, Any]]:
        """파라미터 스키마 정보 반환"""
        return {
            'ma_period': {
                'type': int,
                'default': 5,
                'min': 2,
                'max': 20,
                'description': '이동평균 기간 (분)'
            },
            'confidence_threshold': {
                'type': float,
                'default': 0.7,
                'min': 0.1,
                'max': 1.0,
                'description': '신호 신뢰도 임계값'
            },
            'market_close_time': {
                'type': str,
                'default': '15:20',
                'description': '장마감 시간 (HH:MM 형식)'
            },
            'enable_forced_sell': {
                'type': bool,
                'default': True,
                'description': '장마감 강제매도 활성화'
            },
            'weight_multiplier': {
                'type': float,
                'default': 1.0,
                'min': 0.8,
                'max': 1.5,
                'description': '이동평균 가중치 승수'
            },
            'min_volume_threshold': {
                'type': int,
                'default': 30_000_000_000,
                'min': 1_000_000_000,
                'max': 100_000_000_000,
                'description': '최소 거래대금 (원)'
            },
            'enable_volume_filter': {
                'type': bool,
                'default': True,
                'description': '거래대금 필터 활성화'
            }
        }

    def get_description(self) -> str:
        """전략 설명 반환"""
        ma_period = self.params.get('ma_period', 5)
        weight = self.params.get('weight_multiplier', 1.0)
        
        description = f"1분봉_5분봉 전략 - "
        description += f"1분봉 종가와 {ma_period}분 이동평균 비교 전략"
        
        if weight != 1.0:
            description += f" (가중치: {weight})"
        
        description += f"\n• 매수: 1분봉 > {ma_period}분 평균"
        description += f"\n• 매도: 1분봉 <= {ma_period}분 평균"
        description += f"\n• 장마감: {self.params.get('market_close_time', '15:20')} 강제매도"
        
        if self.params.get('enable_volume_filter', True):
            volume_threshold = self.params.get('min_volume_threshold', 30_000_000_000)
            description += f"\n• 거래대금 필터: {volume_threshold:,}원 이상"
        
        return description

    def get_position_status(self) -> Dict[str, Any]:
        """현재 포지션 상태 반환"""
        return {
            'total_positions': len(self.current_position),
            'positions': dict(self.current_position),
            'strategy_name': self.name
        }

    def force_close_position(self, symbol: str) -> bool:
        """특정 심볼의 포지션 강제 종료"""
        if symbol in self.current_position:
            del self.current_position[symbol]
            logger.info(f"Forced close position for {symbol}")
            return True
        return False

    def force_close_all_positions(self) -> int:
        """모든 포지션 강제 종료"""
        count = len(self.current_position)
        self.current_position.clear()
        logger.info(f"Forced close all {count} positions")
        return count