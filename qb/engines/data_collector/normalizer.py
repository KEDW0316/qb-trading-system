"""
Data Normalizer

다양한 데이터 소스의 데이터를 표준 형식으로 정규화
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal


class DataNormalizer:
    """
    데이터 정규화 클래스
    
    다양한 소스의 데이터를 표준 형식으로 변환
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 표준 필드 매핑
        self.field_mappings = {
            'test': {
                'symbol': 'symbol',
                'close': 'close',
                'volume': 'volume',
                'change': 'change',
                'timestamp': 'timestamp',
                'open': 'open',
                'high': 'high',
                'low': 'low'
            },
            'mock': {
                'symbol': 'symbol',
                'close': 'close',
                'volume': 'volume',
                'change': 'change',
                'timestamp': 'timestamp',
                'open': 'open',
                'high': 'high',
                'low': 'low'
            },
            'kis': {
                'symbol': 'symbol',  # 새로운 파싱 방식에서는 직접 symbol 키 사용
                'close': 'close',    # 새로운 파싱 방식에서는 직접 close 키 사용
                'volume': 'volume',
                'change': 'change',
                'timestamp': 'timestamp'
            },
            'naver': {
                'symbol': 'symbol',
                'close': 'nv',
                'volume': 'aq',
                'change': 'cv',
                'timestamp': 'timestamp'
            },
            'yahoo': {
                'symbol': 'symbol',
                'close': 'regularMarketPrice',
                'volume': 'regularMarketVolume',
                'change': 'regularMarketChange',
                'timestamp': 'timestamp'
            }
        }
    
    async def normalize(self, raw_data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """
        데이터 정규화
        
        Args:
            raw_data: 원본 데이터
            source: 데이터 소스 ('kis', 'naver', 'yahoo')
            
        Returns:
            정규화된 데이터
        """
        try:
            if source not in self.field_mappings:
                raise ValueError(f"Unsupported data source: {source}")
            
            # 디버그: 입력 데이터 확인 (처음 몇 개만)
            if not hasattr(self, '_input_data_logged'):
                self.logger.info(f"Normalizer input data: {raw_data}")
                self._input_data_logged = True
            
            mapping = self.field_mappings[source]
            normalized = {}
            
            # 기본 필드 매핑
            for standard_field, source_field in mapping.items():
                value = raw_data.get(source_field)
                if value is not None:
                    normalized[standard_field] = self._convert_value(standard_field, value)
            
            # 필수 필드 확인 및 기본값 설정
            normalized = self._ensure_required_fields(normalized, source)
            
            # 추가 계산 필드
            normalized = self._add_calculated_fields(normalized)
            
            # 데이터 검증
            self._validate_normalized_data(normalized)
            
            return normalized
            
        except Exception as e:
            self.logger.error(f"Failed to normalize data from {source}: {e}")
            raise
    
    def _convert_value(self, field: str, value: Any) -> Any:
        """필드별 값 변환"""
        try:
            if field == 'symbol':
                return str(value).upper()
            
            elif field in ['close', 'open', 'high', 'low', 'change']:
                # 가격 관련 필드는 float로 변환
                if isinstance(value, str):
                    # 쉼표 제거 후 변환
                    value = value.replace(',', '')
                return float(value)
            
            elif field == 'volume':
                # 거래량은 int로 변환
                if isinstance(value, str):
                    value = value.replace(',', '')
                return int(float(value))
            
            elif field == 'timestamp':
                # 타임스탬프 처리
                if isinstance(value, str):
                    try:
                        return datetime.fromisoformat(value).isoformat()
                    except ValueError:
                        # 다른 형식의 날짜 문자열 처리
                        return datetime.now().isoformat()
                elif isinstance(value, datetime):
                    return value.isoformat()
                else:
                    return datetime.now().isoformat()
            
            else:
                return value
                
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Failed to convert {field} value '{value}': {e}")
            return self._get_default_value(field)
    
    def _get_default_value(self, field: str) -> Any:
        """필드별 기본값 반환"""
        defaults = {
            'symbol': '',
            'close': 0.0,
            'open': 0.0,
            'high': 0.0,
            'low': 0.0,
            'volume': 0,
            'change': 0.0,
            'change_rate': 0.0,
            'timestamp': datetime.now().isoformat()
        }
        return defaults.get(field, None)
    
    def _ensure_required_fields(self, data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """필수 필드 확인 및 기본값 설정"""
        required_fields = ['symbol', 'timestamp', 'close']
        
        for field in required_fields:
            if field not in data or data[field] is None:
                data[field] = self._get_default_value(field)
        
        # OHLC 데이터 보완
        if 'open' not in data:
            data['open'] = data['close']
        if 'high' not in data:
            data['high'] = data['close']
        if 'low' not in data:
            data['low'] = data['close']
        if 'volume' not in data:
            data['volume'] = 0
        
        # 소스 정보 추가
        data['source'] = source
        
        return data
    
    def _add_calculated_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """계산된 필드 추가"""
        try:
            # 변화율 계산 (이전 가격이 필요하므로 여기서는 기본값)
            if 'change' in data and 'close' in data:
                if data['close'] != 0:
                    prev_close = data['close'] - data.get('change', 0)
                    if prev_close != 0:
                        data['change_rate'] = (data['change'] / prev_close) * 100
                    else:
                        data['change_rate'] = 0.0
                else:
                    data['change_rate'] = 0.0
            
            # 추가 메타데이터
            data['normalized_at'] = datetime.now().isoformat()
            
        except Exception as e:
            self.logger.warning(f"Failed to add calculated fields: {e}")
        
        return data
    
    def _validate_normalized_data(self, data: Dict[str, Any]):
        """정규화된 데이터 검증"""
        # 필수 필드 검증
        required_fields = ['symbol', 'timestamp', 'close']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # 데이터 타입 검증
        if not isinstance(data['symbol'], str) or not data['symbol']:
            self.logger.error(f"Symbol validation failed: {data.get('symbol')} (type: {type(data.get('symbol'))})")
            raise ValueError("Invalid symbol")
        
        if not isinstance(data['close'], (int, float)) or data['close'] < 0:
            raise ValueError("Invalid close price")
        
        if 'volume' in data and (not isinstance(data['volume'], int) or data['volume'] < 0):
            raise ValueError("Invalid volume")
    
    def normalize_symbol(self, symbol: str, source: str) -> str:
        """심볼 정규화"""
        try:
            symbol = symbol.upper().strip()
            
            # 소스별 심볼 변환
            if source == 'test':
                # 테스트용 소스
                return symbol
            elif source == 'mock':
                # Mock 데이터 소스
                return symbol
            elif source == 'kis':
                # 한국투자증권 형식 (6자리 숫자)
                if symbol.isdigit() and len(symbol) == 6:
                    return symbol
                # 다른 형식에서 변환
                symbol = symbol.replace('.KS', '').replace('.KQ', '')
                return symbol.zfill(6)
            
            elif source == 'naver':
                # 네이버 형식
                return symbol
            
            elif source == 'yahoo':
                # 야후 파이낸스 형식 (.KS, .KQ 등)
                if not symbol.endswith('.KS') and not symbol.endswith('.KQ'):
                    # 한국 주식은 기본적으로 .KS 추가
                    if symbol.isdigit():
                        return f"{symbol}.KS"
                return symbol
            
            return symbol
            
        except Exception as e:
            self.logger.error(f"Failed to normalize symbol {symbol} for {source}: {e}")
            return symbol
    
    def denormalize_for_source(self, normalized_data: Dict[str, Any], target_source: str) -> Dict[str, Any]:
        """
        정규화된 데이터를 특정 소스 형식으로 역변환
        
        Args:
            normalized_data: 정규화된 데이터
            target_source: 대상 소스
            
        Returns:
            소스별 형식으로 변환된 데이터
        """
        try:
            if target_source not in self.field_mappings:
                return normalized_data
            
            mapping = self.field_mappings[target_source]
            result = {}
            
            # 역매핑
            for standard_field, source_field in mapping.items():
                if standard_field in normalized_data:
                    result[source_field] = normalized_data[standard_field]
            
            # 추가 메타데이터
            result['denormalized_from'] = normalized_data.get('source', 'unknown')
            result['denormalized_at'] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to denormalize data for {target_source}: {e}")
            return normalized_data