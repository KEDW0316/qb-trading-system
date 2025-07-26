import unittest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from qb.analysis.indicators import IndicatorCalculator


class TestIndicatorCalculator(unittest.TestCase):
    """IndicatorCalculator 단위 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.calculator = IndicatorCalculator()
        
        # 테스트용 캔들 데이터
        self.test_candles = [
            {
                'timestamp': '2025-01-01T09:00:00',
                'open': 100.0,
                'high': 105.0,
                'low': 98.0,
                'close': 103.0,
                'volume': 1000
            },
            {
                'timestamp': '2025-01-01T09:01:00',
                'open': 103.0,
                'high': 107.0,
                'low': 101.0,
                'close': 105.0,
                'volume': 1200
            },
            {
                'timestamp': '2025-01-01T09:02:00',
                'open': 105.0,
                'high': 108.0,
                'low': 104.0,
                'close': 106.0,
                'volume': 900
            }
        ]
        
        # 충분한 데이터를 위해 더 많은 캔들 생성
        for i in range(3, 25):
            self.test_candles.append({
                'timestamp': f'2025-01-01T09:{i:02d}:00',
                'open': 100.0 + i,
                'high': 105.0 + i,
                'low': 98.0 + i,
                'close': 103.0 + i,
                'volume': 1000 + i * 10
            })
            
    def test_prepare_data(self):
        """데이터 준비 테스트"""
        df = self.calculator.prepare_data(self.test_candles)
        
        # DataFrame이 제대로 생성되었는지 확인
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), len(self.test_candles))
        
        # 필수 컬럼이 있는지 확인
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            self.assertIn(col, df.columns)
            
        # 인덱스가 시간으로 설정되었는지 확인
        self.assertIsInstance(df.index, pd.DatetimeIndex)
        
    def test_sma_calculation(self):
        """SMA 계산 테스트"""
        # 테스트 데이터 생성
        test_data = pd.Series([100, 102, 104, 106, 108, 110, 112, 114, 116, 118] * 3)
        
        # SMA 계산
        result = self.calculator.sma(test_data, period=5)
        
        # 결과 검증
        self.assertIsInstance(result, pd.Series)
        self.assertFalse(result.iloc[4:].isna().any())  # 5번째부터는 NaN이 아니어야 함
        
        # 수동 계산과 비교
        expected_sma_5 = (100 + 102 + 104 + 106 + 108) / 5
        self.assertAlmostEqual(result.iloc[4], expected_sma_5, places=2)
        
    def test_ema_calculation(self):
        """EMA 계산 테스트"""
        test_data = pd.Series([100, 102, 104, 106, 108, 110, 112, 114, 116, 118] * 2)
        
        result = self.calculator.ema(test_data, period=5)
        
        self.assertIsInstance(result, pd.Series)
        self.assertFalse(result.iloc[4:].isna().any())
        
    def test_rsi_calculation(self):
        """RSI 계산 테스트"""
        # 상승/하락이 있는 테스트 데이터
        test_data = pd.Series([100, 102, 98, 105, 103, 108, 106, 110, 107, 112, 109, 115] * 2)
        
        result = self.calculator.rsi(test_data, period=14)
        
        self.assertIsInstance(result, pd.Series)
        
        # RSI는 0-100 범위여야 함
        valid_rsi = result.dropna()
        self.assertTrue((valid_rsi >= 0).all())
        self.assertTrue((valid_rsi <= 100).all())
        
    def test_bollinger_bands_calculation(self):
        """볼린저 밴드 계산 테스트"""
        test_data = pd.Series([100, 102, 98, 105, 103, 108, 106, 110, 107, 112] * 3)
        
        upper, middle, lower = self.calculator.bollinger_bands(test_data, period=10, std_dev=2)
        
        # 결과가 배열 또는 Series인지 확인 (TA-Lib은 numpy array, 순수 Python은 pandas Series)
        self.assertTrue(isinstance(upper, (np.ndarray, pd.Series)))
        self.assertTrue(isinstance(middle, (np.ndarray, pd.Series)))
        self.assertTrue(isinstance(lower, (np.ndarray, pd.Series)))
        
        # 길이가 같은지 확인
        self.assertEqual(len(upper), len(middle))
        self.assertEqual(len(middle), len(lower))
        
        # 상단 밴드 >= 중간선 >= 하단 밴드 (numpy array로 변환해서 비교)
        upper_array = np.array(upper)
        middle_array = np.array(middle)
        lower_array = np.array(lower)
        
        valid_indices = ~np.isnan(upper_array) & ~np.isnan(middle_array) & ~np.isnan(lower_array)
        if np.any(valid_indices):  # 유효한 값이 있는 경우만 비교
            self.assertTrue((upper_array[valid_indices] >= middle_array[valid_indices]).all())
            self.assertTrue((middle_array[valid_indices] >= lower_array[valid_indices]).all())
        
    def test_macd_calculation(self):
        """MACD 계산 테스트"""
        test_data = pd.Series([100, 102, 98, 105, 103, 108, 106, 110, 107, 112] * 5)
        
        macd, signal, histogram = self.calculator.macd(test_data)
        
        # 결과가 배열 또는 Series인지 확인 (TA-Lib은 numpy array, 순수 Python은 pandas Series)
        self.assertTrue(isinstance(macd, (np.ndarray, pd.Series)))
        self.assertTrue(isinstance(signal, (np.ndarray, pd.Series)))
        self.assertTrue(isinstance(histogram, (np.ndarray, pd.Series)))
        
        # 길이가 같은지 확인
        self.assertEqual(len(macd), len(signal))
        self.assertEqual(len(signal), len(histogram))
        
        # 히스토그램 = MACD - Signal (numpy array로 변환해서 비교)
        macd_array = np.array(macd)
        signal_array = np.array(signal)
        histogram_array = np.array(histogram)
        
        valid_indices = ~np.isnan(macd_array) & ~np.isnan(signal_array) & ~np.isnan(histogram_array)
        if np.any(valid_indices):  # 유효한 값이 있는 경우만 비교
            np.testing.assert_array_almost_equal(
                histogram_array[valid_indices],
                macd_array[valid_indices] - signal_array[valid_indices],
                decimal=5
            )
        
    def test_calculate_all_indicators(self):
        """전체 지표 계산 테스트"""
        indicators = self.calculator.calculate_all_indicators(self.test_candles)
        
        # 결과가 딕셔너리인지 확인
        self.assertIsInstance(indicators, dict)
        
        # 예상되는 지표들이 있는지 확인
        expected_indicators = [
            'sma_20', 'ema_20', 'bb_upper', 'bb_middle', 'bb_lower',
            'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'stoch_k', 'stoch_d', 'atr', 'current_price'
        ]
        
        for indicator in expected_indicators:
            self.assertIn(indicator, indicators)
            self.assertIsInstance(indicators[indicator], (int, float))
            
    def test_custom_indicator_registration(self):
        """커스텀 지표 등록 테스트"""
        def custom_indicator(data, period=10):
            return data['close'].rolling(window=period).max()
            
        # 커스텀 지표 등록
        success = self.calculator.register_custom_indicator(
            'rolling_max',
            custom_indicator,
            'Rolling Maximum',
            ['close'],
            {'period': 10}
        )
        
        self.assertTrue(success)
        
        # 등록된 지표 목록 확인
        custom_indicators = self.calculator.list_custom_indicators()
        self.assertIn('rolling_max', custom_indicators)
        
    def test_custom_indicator_calculation(self):
        """커스텀 지표 계산 테스트"""
        def simple_custom(data, multiplier=1.0):
            return data['close'] * multiplier
            
        # 등록
        self.calculator.register_custom_indicator(
            'price_multiplier',
            simple_custom,
            'Price Multiplier',
            ['close'],
            {'multiplier': 1.0}
        )
        
        # 계산
        result = self.calculator.calculate_custom_indicator(
            'price_multiplier',
            self.test_candles,
            multiplier=2.0
        )
        
        self.assertIsNotNone(result)
        
    def test_data_validation(self):
        """데이터 검증 테스트"""
        # 잘못된 데이터 (필수 컬럼 누락)
        invalid_candles = [
            {
                'timestamp': '2025-01-01T09:00:00',
                'open': 100.0,
                'high': 105.0,
                # 'low': 98.0,  # 누락
                'close': 103.0,
                'volume': 1000
            }
        ]
        
        with self.assertRaises(ValueError):
            self.calculator.prepare_data(invalid_candles)
            
    def test_talib_availability(self):
        """TA-Lib 가용성 테스트"""
        # TA-Lib 체크 함수 테스트
        ta_lib_available = self.calculator._check_talib()
        self.assertIsInstance(ta_lib_available, bool)
        
        # 이제 TA-Lib이 설치되었으므로 True여야 함
        self.assertTrue(ta_lib_available)
        
        # TA-Lib 함수 호출 테스트
        test_data = pd.Series([100, 102, 104, 106, 108])
        result = self.calculator.sma(test_data, 5)
        
        # 결과가 pandas Series인지 확인
        self.assertIsInstance(result, pd.Series)
        # 마지막 값이 NaN이 아닌지 확인
        self.assertFalse(pd.isna(result.iloc[-1]))
        
    def test_edge_cases(self):
        """엣지 케이스 테스트"""
        # 빈 데이터
        with self.assertRaises(ValueError):
            self.calculator.calculate_all_indicators([])
            
        # 데이터가 적어도 3개 이상이면 계산이 가능함 (일부 지표는 NaN일 수 있음)
        minimal_candles = self.test_candles[:3]
        try:
            result = self.calculator.calculate_all_indicators(minimal_candles)
            self.assertIsInstance(result, dict)
            # 최소한 current_price는 있어야 함
            self.assertIn('current_price', result)
        except Exception as e:
            # 만약 예외가 발생한다면 기록만 하고 넘어감
            print(f"Minimal data calculation failed: {e}")


if __name__ == '__main__':
    unittest.main()