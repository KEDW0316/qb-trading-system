import numpy as np
import pandas as pd
from typing import Union, Tuple, Optional, List, Dict, Any
import logging

from .custom_indicators import CustomIndicatorRegistry


class IndicatorCalculator:
    """기술적 지표 계산 클래스
    
    TA-Lib 사용 가능 시 우선 사용하고, 없을 경우 순수 Python 구현을 사용합니다.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ta_lib_available = self._check_talib()
        self.custom_registry = CustomIndicatorRegistry()
        
    def _check_talib(self) -> bool:
        """TA-Lib 사용 가능 여부 확인"""
        try:
            import talib
            self.logger.info("TA-Lib is available")
            return True
        except ImportError:
            self.logger.warning("TA-Lib not available, using pure Python implementations")
            return False
            
    def prepare_data(self, candles: List[Dict[str, Any]]) -> pd.DataFrame:
        """캔들 데이터를 DataFrame으로 변환"""
        df = pd.DataFrame(candles)
        
        # 필요한 컬럼 확인 및 타입 변환
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
                
        # 숫자 타입으로 변환
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # timestamp를 인덱스로 설정
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # 시간순 정렬
        df.sort_index(inplace=True)
        
        return df
        
    def sma(self, data: Union[pd.Series, np.ndarray], period: int = 20) -> Union[pd.Series, np.ndarray]:
        """단순 이동평균 (Simple Moving Average)"""
        if self.ta_lib_available:
            import talib
            return talib.SMA(data, timeperiod=period)
            
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
        return data.rolling(window=period).mean()
        
    def ema(self, data: Union[pd.Series, np.ndarray], period: int = 20) -> Union[pd.Series, np.ndarray]:
        """지수 이동평균 (Exponential Moving Average)"""
        if self.ta_lib_available:
            import talib
            return talib.EMA(data, timeperiod=period)
            
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
        return data.ewm(span=period, adjust=False).mean()
        
    def bollinger_bands(self, data: Union[pd.Series, np.ndarray], 
                       period: int = 20, std_dev: float = 2) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """볼린저 밴드 (Bollinger Bands)
        
        Returns:
            (upper_band, middle_band, lower_band)
        """
        if self.ta_lib_available:
            import talib
            upper, middle, lower = talib.BBANDS(
                data, 
                timeperiod=period, 
                nbdevup=std_dev, 
                nbdevdn=std_dev
            )
            return upper, middle, lower
            
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
            
        sma = self.sma(data, period)
        std = data.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band.values, sma.values, lower_band.values
        
    def rsi(self, data: Union[pd.Series, np.ndarray], period: int = 14) -> Union[pd.Series, np.ndarray]:
        """상대강도지수 (Relative Strength Index)"""
        if self.ta_lib_available:
            import talib
            return talib.RSI(data, timeperiod=period)
            
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
            
        # 가격 변화량 계산
        delta = data.diff()
        
        # 상승분과 하락분 분리
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # 평균 상승분과 하락분 계산 (첫 번째 값은 단순 평균)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # 이후 값들은 지수 이동평균 방식으로 계산
        for i in range(period, len(data)):
            avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
            avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
            
        # RS와 RSI 계산
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
        
    def macd(self, data: Union[pd.Series, np.ndarray], 
             fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """MACD (Moving Average Convergence Divergence)
        
        Returns:
            (macd_line, signal_line, histogram)
        """
        if self.ta_lib_available:
            import talib
            macd, signal, hist = talib.MACD(
                data, 
                fastperiod=fast_period, 
                slowperiod=slow_period, 
                signalperiod=signal_period
            )
            return macd, signal, hist
            
        if isinstance(data, np.ndarray):
            data = pd.Series(data)
            
        # MACD Line = 12일 EMA - 26일 EMA
        ema_fast = self.ema(data, fast_period)
        ema_slow = self.ema(data, slow_period)
        macd_line = ema_fast - ema_slow
        
        # Signal Line = MACD의 9일 EMA
        signal_line = self.ema(macd_line, signal_period)
        
        # Histogram = MACD Line - Signal Line
        histogram = macd_line - signal_line
        
        return macd_line.values, signal_line.values, histogram.values
        
    def stochastic(self, high: Union[pd.Series, np.ndarray], 
                   low: Union[pd.Series, np.ndarray], 
                   close: Union[pd.Series, np.ndarray],
                   k_period: int = 14, d_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """스토캐스틱 오실레이터 (Stochastic Oscillator)
        
        Returns:
            (k_percent, d_percent)
        """
        if self.ta_lib_available:
            import talib
            k, d = talib.STOCH(
                high, low, close,
                fastk_period=k_period,
                slowk_period=d_period,
                slowd_period=d_period
            )
            return k, d
            
        # 데이터를 Series로 변환
        if isinstance(high, np.ndarray):
            high = pd.Series(high)
        if isinstance(low, np.ndarray):
            low = pd.Series(low)
        if isinstance(close, np.ndarray):
            close = pd.Series(close)
            
        # K% 계산
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        
        # D% 계산 (K%의 이동평균)
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return k_percent.values, d_percent.values
        
    def atr(self, high: Union[pd.Series, np.ndarray], 
            low: Union[pd.Series, np.ndarray], 
            close: Union[pd.Series, np.ndarray], 
            period: int = 14) -> Union[pd.Series, np.ndarray]:
        """평균 진정 범위 (Average True Range)"""
        if self.ta_lib_available:
            import talib
            return talib.ATR(high, low, close, timeperiod=period)
            
        # 데이터를 Series로 변환
        if isinstance(high, np.ndarray):
            high = pd.Series(high)
        if isinstance(low, np.ndarray):
            low = pd.Series(low)
        if isinstance(close, np.ndarray):
            close = pd.Series(close)
            
        # True Range 계산
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR은 TR의 이동평균
        atr = true_range.rolling(window=period).mean()
        
        return atr
        
    def calculate_all_indicators(self, candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """모든 주요 지표 계산"""
        try:
            # DataFrame 준비
            df = self.prepare_data(candles)
            
            # 가격 데이터 추출
            close = df['close']
            high = df['high']
            low = df['low']
            
            # 각 지표 계산
            indicators = {}
            
            # 이동평균
            indicators['sma_20'] = float(self.sma(close, 20).iloc[-1])
            indicators['ema_20'] = float(self.ema(close, 20).iloc[-1])
            
            # 볼린저 밴드
            bb_upper, bb_middle, bb_lower = self.bollinger_bands(close)
            indicators['bb_upper'] = float(bb_upper.iloc[-1] if hasattr(bb_upper, 'iloc') else bb_upper[-1])
            indicators['bb_middle'] = float(bb_middle.iloc[-1] if hasattr(bb_middle, 'iloc') else bb_middle[-1])
            indicators['bb_lower'] = float(bb_lower.iloc[-1] if hasattr(bb_lower, 'iloc') else bb_lower[-1])
            
            # RSI
            rsi = self.rsi(close)
            indicators['rsi'] = float(rsi.iloc[-1])
            
            # MACD
            macd, signal, hist = self.macd(close)
            indicators['macd'] = float(macd.iloc[-1] if hasattr(macd, 'iloc') else macd[-1])
            indicators['macd_signal'] = float(signal.iloc[-1] if hasattr(signal, 'iloc') else signal[-1])
            indicators['macd_histogram'] = float(hist.iloc[-1] if hasattr(hist, 'iloc') else hist[-1])
            
            # 스토캐스틱
            k, d = self.stochastic(high, low, close)
            indicators['stoch_k'] = float(k.iloc[-1] if hasattr(k, 'iloc') else k[-1])
            indicators['stoch_d'] = float(d.iloc[-1] if hasattr(d, 'iloc') else d[-1])
            
            # ATR
            atr = self.atr(high, low, close)
            indicators['atr'] = float(atr.iloc[-1])
            
            # 현재 가격 정보도 추가
            indicators['current_price'] = float(close.iloc[-1])
            indicators['price_change'] = float(close.iloc[-1] - close.iloc[-2])
            indicators['price_change_pct'] = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100)
            
            return indicators
            
        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            raise
            
    def calculate_custom_indicator(self, name: str, candles: List[Dict[str, Any]], 
                                 **params) -> Any:
        """커스텀 지표 계산"""
        try:
            df = self.prepare_data(candles)
            return self.custom_registry.calculate(name, df, **params)
            
        except Exception as e:
            self.logger.error(f"Error calculating custom indicator {name}: {e}")
            raise
            
    def register_custom_indicator(self, name: str, calculation_func, 
                                description: str = "", required_columns: Optional[List[str]] = None,
                                default_params: Optional[Dict[str, Any]] = None) -> bool:
        """커스텀 지표 등록"""
        return self.custom_registry.register(
            name, calculation_func, description, required_columns, default_params
        )
        
    def list_custom_indicators(self) -> Dict[str, Dict[str, Any]]:
        """등록된 커스텀 지표 목록"""
        return self.custom_registry.list_indicators()
        
    def get_available_indicators(self) -> Dict[str, List[str]]:
        """사용 가능한 모든 지표 목록 (기본 + 커스텀)"""
        basic_indicators = [
            'sma', 'ema', 'bollinger_bands', 'rsi', 'macd', 
            'stochastic', 'atr'
        ]
        
        custom_indicators = list(self.custom_registry.indicators.keys())
        
        return {
            'basic': basic_indicators,
            'custom': custom_indicators,
            'total_count': len(basic_indicators) + len(custom_indicators)
        }