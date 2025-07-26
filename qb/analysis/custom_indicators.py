import inspect
import importlib
from typing import Dict, Any, Callable, List, Optional, Union
import pandas as pd
import numpy as np
import logging
from datetime import datetime


class CustomIndicatorRegistry:
    """커스텀 지표 등록 및 관리 시스템
    
    사용자 정의 기술적 지표를 등록하고 계산할 수 있는 프레임워크입니다.
    """
    
    def __init__(self):
        self.indicators: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
        
    def register(self, name: str, calculation_func: Callable, 
                description: str = "", required_columns: Optional[List[str]] = None,
                default_params: Optional[Dict[str, Any]] = None) -> bool:
        """커스텀 지표 등록
        
        Args:
            name: 지표 이름
            calculation_func: 계산 함수
            description: 지표 설명
            required_columns: 필요한 데이터 컬럼들 (예: ['close', 'volume'])
            default_params: 기본 파라미터
            
        Returns:
            등록 성공 여부
        """
        try:
            # 함수 시그니처 검증
            if not self._validate_function_signature(calculation_func):
                raise ValueError(f"Invalid function signature for indicator: {name}")
                
            self.indicators[name] = {
                'function': calculation_func,
                'description': description,
                'required_columns': required_columns or ['close'],
                'default_params': default_params or {},
                'registered_at': datetime.now().isoformat(),
                'module': calculation_func.__module__,
                'function_name': calculation_func.__name__
            }
            
            self.logger.info(f"Registered custom indicator: {name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register indicator {name}: {e}")
            return False
            
    def unregister(self, name: str) -> bool:
        """커스텀 지표 등록 해제"""
        try:
            if name in self.indicators:
                del self.indicators[name]
                self.logger.info(f"Unregistered custom indicator: {name}")
                return True
            else:
                self.logger.warning(f"Indicator {name} not found for unregistration")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to unregister indicator {name}: {e}")
            return False
            
    def get_indicator(self, name: str) -> Optional[Callable]:
        """등록된 커스텀 지표 함수 조회"""
        indicator_info = self.indicators.get(name)
        if indicator_info:
            return indicator_info['function']
        return None
        
    def calculate(self, name: str, data: Union[pd.DataFrame, Dict[str, Any]], 
                 **params) -> Any:
        """커스텀 지표 계산
        
        Args:
            name: 지표 이름
            data: 가격 데이터 (DataFrame 또는 Dict)
            **params: 지표별 파라미터
            
        Returns:
            계산된 지표 값
        """
        try:
            indicator_info = self.indicators.get(name)
            if not indicator_info:
                raise ValueError(f"Unknown indicator: {name}")
                
            calculation_func = indicator_info['function']
            required_columns = indicator_info['required_columns']
            default_params = indicator_info['default_params']
            
            # 기본 파라미터와 사용자 파라미터 병합
            merged_params = {**default_params, **params}
            
            # 데이터 검증
            if isinstance(data, dict):
                # Dict를 DataFrame으로 변환
                data = pd.DataFrame([data] if not isinstance(list(data.values())[0], list) else data)
                
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns for {name}: {missing_columns}")
                
            # 지표 계산
            result = calculation_func(data, **merged_params)
            
            self.logger.debug(f"Calculated custom indicator {name}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating custom indicator {name}: {e}")
            raise
            
    def list_indicators(self) -> Dict[str, Dict[str, Any]]:
        """등록된 모든 커스텀 지표 목록 반환"""
        return {
            name: {
                'description': info['description'],
                'required_columns': info['required_columns'],
                'default_params': info['default_params'],
                'registered_at': info['registered_at']
            }
            for name, info in self.indicators.items()
        }
        
    def get_indicator_info(self, name: str) -> Optional[Dict[str, Any]]:
        """특정 지표의 상세 정보 조회"""
        indicator_info = self.indicators.get(name)
        if indicator_info:
            return {
                'name': name,
                'description': indicator_info['description'],
                'required_columns': indicator_info['required_columns'],
                'default_params': indicator_info['default_params'],
                'registered_at': indicator_info['registered_at'],
                'module': indicator_info['module'],
                'function_name': indicator_info['function_name']
            }
        return None
        
    def load_indicators_from_module(self, module_path: str) -> int:
        """모듈에서 지표들을 자동으로 로드
        
        Args:
            module_path: 모듈 경로 (예: 'custom_indicators.my_indicators')
            
        Returns:
            로드된 지표 개수
        """
        try:
            module = importlib.import_module(module_path)
            loaded_count = 0
            
            # 모듈에서 함수들을 찾아서 자동 등록
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if hasattr(obj, '_is_indicator') and obj._is_indicator:
                    # 함수에 메타데이터가 있는 경우
                    description = getattr(obj, '_description', '')
                    required_columns = getattr(obj, '_required_columns', ['close'])
                    default_params = getattr(obj, '_default_params', {})
                    
                    if self.register(name, obj, description, required_columns, default_params):
                        loaded_count += 1
                        
            self.logger.info(f"Loaded {loaded_count} indicators from module {module_path}")
            return loaded_count
            
        except Exception as e:
            self.logger.error(f"Failed to load indicators from module {module_path}: {e}")
            return 0
            
    def _validate_function_signature(self, func: Callable) -> bool:
        """함수 시그니처 검증"""
        try:
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            
            # 첫 번째 파라미터는 data여야 함
            if not params or params[0] != 'data':
                return False
                
            return True
            
        except Exception:
            return False
            
    def export_indicators(self, file_path: str) -> bool:
        """등록된 지표들을 파일로 내보내기"""
        try:
            import json
            
            export_data = {
                'indicators': {},
                'exported_at': datetime.now().isoformat()
            }
            
            for name, info in self.indicators.items():
                export_data['indicators'][name] = {
                    'description': info['description'],
                    'required_columns': info['required_columns'],
                    'default_params': info['default_params'],
                    'module': info['module'],
                    'function_name': info['function_name']
                }
                
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"Exported {len(self.indicators)} indicators to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export indicators: {e}")
            return False


def indicator(description: str = "", required_columns: Optional[List[str]] = None,
             default_params: Optional[Dict[str, Any]] = None):
    """커스텀 지표 데코레이터
    
    사용 예:
    @indicator(description="커스텀 RSI", required_columns=['close'], default_params={'period': 14})
    def custom_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
        # RSI 계산 로직
        pass
    """
    def decorator(func):
        func._is_indicator = True
        func._description = description
        func._required_columns = required_columns or ['close']
        func._default_params = default_params or {}
        return func
    return decorator


class PrebuiltCustomIndicators:
    """미리 구현된 커스텀 지표들"""
    
    @staticmethod
    @indicator(
        description="가격과 거래량을 결합한 모멘텀 지표",
        required_columns=['close', 'volume'],
        default_params={'period': 14}
    )
    def price_volume_momentum(data: pd.DataFrame, period: int = 14) -> pd.Series:
        """가격-거래량 모멘텀 지표"""
        price_change = data['close'].pct_change()
        volume_change = data['volume'].pct_change()
        
        momentum = (price_change * volume_change).rolling(window=period).mean()
        return momentum
        
    @staticmethod
    @indicator(
        description="변동성 조정 RSI",
        required_columns=['high', 'low', 'close'],
        default_params={'period': 14, 'volatility_period': 20}
    )
    def volatility_adjusted_rsi(data: pd.DataFrame, period: int = 14, 
                               volatility_period: int = 20) -> pd.Series:
        """변동성을 고려한 RSI"""
        # 기본 RSI 계산
        close = data['close']
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # 변동성 계산 (ATR 기반)
        high = data['high']
        low = data['low']
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=volatility_period).mean()
        volatility = atr / close
        
        # 변동성으로 RSI 조정
        volatility_factor = 1 + volatility
        adjusted_rsi = rsi / volatility_factor
        
        return adjusted_rsi
        
    @staticmethod
    @indicator(
        description="캔들 패턴 강도 지표",
        required_columns=['open', 'high', 'low', 'close'],
        default_params={'lookback': 5}
    )
    def candle_pattern_strength(data: pd.DataFrame, lookback: int = 5) -> pd.Series:
        """캔들 패턴 강도 측정"""
        open_price = data['open']
        high = data['high']
        low = data['low']
        close = data['close']
        
        # 캔들 바디와 꼬리 크기 계산
        body_size = abs(close - open_price)
        upper_shadow = high - np.maximum(close, open_price)
        lower_shadow = np.minimum(close, open_price) - low
        total_range = high - low
        
        # 패턴 강도 계산
        body_ratio = body_size / total_range
        shadow_ratio = (upper_shadow + lower_shadow) / total_range
        
        # 최근 캔들들과 비교한 상대적 강도
        relative_body = body_size / body_size.rolling(window=lookback).mean()
        relative_range = total_range / total_range.rolling(window=lookback).mean()
        
        pattern_strength = (body_ratio * relative_body + shadow_ratio * relative_range) / 2
        
        return pattern_strength