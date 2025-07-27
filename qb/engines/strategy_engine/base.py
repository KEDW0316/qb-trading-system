"""
전략 엔진의 기본 추상 클래스 모듈

QB Trading System의 전략 플러그인 아키텍처를 위한 기본 인터페이스를 정의합니다.
모든 거래 전략은 이 BaseStrategy 클래스를 상속받아 구현해야 합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    """거래 신호를 나타내는 데이터 클래스"""
    action: str  # 'BUY', 'SELL', 'HOLD'
    symbol: str
    confidence: float  # 0.0 ~ 1.0
    price: Optional[float] = None
    quantity: Optional[int] = None
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        # 액션 유효성 검증
        if self.action not in ['BUY', 'SELL', 'HOLD']:
            raise ValueError(f"Invalid action: {self.action}. Must be 'BUY', 'SELL', or 'HOLD'")
        
        # 신뢰도 범위 검증
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


@dataclass
class MarketData:
    """시장 데이터를 나타내는 데이터 클래스"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    interval_type: str = "1m"  # '1m', '5m', '1d'
    indicators: Optional[Dict[str, float]] = None

    def __post_init__(self):
        if self.indicators is None:
            self.indicators = {}


class BaseStrategy(ABC):
    """
    모든 거래 전략의 기본 추상 클래스
    
    전략 개발자는 이 클래스를 상속받아 analyze() 메서드를 구현해야 합니다.
    각 전략은 시장 데이터와 기술적 지표를 분석하여 거래 신호를 생성합니다.
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """
        전략 초기화
        
        Args:
            params: 전략 파라미터 딕셔너리
        """
        self.params = params or {}
        self.name = self.__class__.__name__
        self.created_at = datetime.now()
        self.last_signal_time: Optional[datetime] = None
        self.signal_count = 0
        self.enabled = True
        
        logger.info(f"Strategy {self.name} initialized with params: {self.params}")

    @abstractmethod
    async def analyze(self, market_data: MarketData) -> Optional[TradingSignal]:
        """
        시장 데이터를 분석하여 거래 신호 생성
        
        Args:
            market_data: 시장 데이터 (가격, 거래량, 기술적 지표 포함)
            
        Returns:
            TradingSignal: 거래 신호 객체 또는 None (신호 없음)
        """
        pass

    @abstractmethod
    def get_required_indicators(self) -> List[str]:
        """
        이 전략이 필요로 하는 기술적 지표 목록 반환
        
        Returns:
            List[str]: 필요한 지표명 리스트 (예: ['sma_20', 'rsi', 'macd'])
        """
        pass

    @abstractmethod
    def get_parameter_schema(self) -> Dict[str, Dict[str, Any]]:
        """
        전략 파라미터의 스키마 정보 반환
        
        Returns:
            Dict: 파라미터 스키마 정보
            예: {
                'period': {'type': int, 'default': 20, 'min': 1, 'max': 200},
                'threshold': {'type': float, 'default': 0.5, 'min': 0.0, 'max': 1.0}
            }
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        전략에 대한 설명 반환
        
        Returns:
            str: 전략 설명
        """
        pass

    def get_parameters(self) -> Dict[str, Any]:
        """현재 전략 파라미터 반환"""
        return self.params.copy()

    def set_parameters(self, params: Dict[str, Any]) -> bool:
        """
        전략 파라미터 설정
        
        Args:
            params: 설정할 파라미터 딕셔너리
            
        Returns:
            bool: 설정 성공 여부
        """
        try:
            if self.validate_parameters(params):
                self.params.update(params)
                logger.info(f"Strategy {self.name} parameters updated: {params}")
                return True
            else:
                logger.error(f"Invalid parameters for strategy {self.name}: {params}")
                return False
        except Exception as e:
            logger.error(f"Error setting parameters for strategy {self.name}: {e}")
            return False

    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """
        파라미터 유효성 검증
        
        Args:
            params: 검증할 파라미터 딕셔너리
            
        Returns:
            bool: 유효성 검증 결과
        """
        try:
            schema = self.get_parameter_schema()
            
            for param_name, value in params.items():
                if param_name not in schema:
                    logger.warning(f"Unknown parameter '{param_name}' for strategy {self.name}")
                    continue
                
                param_schema = schema[param_name]
                expected_type = param_schema.get('type')
                
                # 타입 검증
                if expected_type and not isinstance(value, expected_type):
                    logger.error(f"Parameter '{param_name}' must be of type {expected_type.__name__}")
                    return False
                
                # 범위 검증
                if 'min' in param_schema and value < param_schema['min']:
                    logger.error(f"Parameter '{param_name}' must be >= {param_schema['min']}")
                    return False
                
                if 'max' in param_schema and value > param_schema['max']:
                    logger.error(f"Parameter '{param_name}' must be <= {param_schema['max']}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating parameters for strategy {self.name}: {e}")
            return False

    def get_default_parameters(self) -> Dict[str, Any]:
        """기본 파라미터 값 반환"""
        schema = self.get_parameter_schema()
        defaults = {}
        
        for param_name, param_info in schema.items():
            if 'default' in param_info:
                defaults[param_name] = param_info['default']
        
        return defaults

    def enable(self):
        """전략 활성화"""
        self.enabled = True
        logger.info(f"Strategy {self.name} enabled")

    def disable(self):
        """전략 비활성화"""
        self.enabled = False
        logger.info(f"Strategy {self.name} disabled")

    def is_enabled(self) -> bool:
        """전략 활성화 상태 확인"""
        return self.enabled

    def get_status(self) -> Dict[str, Any]:
        """전략 상태 정보 반환"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'last_signal_time': self.last_signal_time.isoformat() if self.last_signal_time else None,
            'signal_count': self.signal_count,
            'parameters': self.params,
            'required_indicators': self.get_required_indicators(),
            'description': self.get_description()
        }

    async def process_market_data(self, market_data: MarketData) -> Optional[TradingSignal]:
        """
        시장 데이터 처리 및 신호 생성 (내부 상태 업데이트 포함)
        
        Args:
            market_data: 처리할 시장 데이터
            
        Returns:
            Optional[TradingSignal]: 생성된 거래 신호
        """
        if not self.enabled:
            return None
        
        try:
            # 필요한 지표가 모두 있는지 확인
            required_indicators = self.get_required_indicators()
            missing_indicators = [
                indicator for indicator in required_indicators 
                if indicator not in market_data.indicators
            ]
            
            if missing_indicators:
                logger.warning(
                    f"Strategy {self.name} missing indicators: {missing_indicators}"
                )
                return None
            
            # 전략 분석 실행
            signal = await self.analyze(market_data)
            
            if signal:
                # 신호 생성 시 내부 상태 업데이트
                self.last_signal_time = signal.timestamp
                self.signal_count += 1
                
                logger.info(
                    f"Strategy {self.name} generated signal: {signal.action} "
                    f"for {signal.symbol} with confidence {signal.confidence}"
                )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error processing market data in strategy {self.name}: {e}")
            return None

    def __str__(self) -> str:
        return f"{self.name}(enabled={self.enabled}, signals={self.signal_count})"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' enabled={self.enabled}>"