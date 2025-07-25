import json
import zlib
import base64
import pickle
import logging
from typing import Any, Optional, Union, Dict
from enum import Enum
import lz4.frame
import snappy
import numpy as np
import pandas as pd
from datetime import datetime, date


class SerializationFormat(Enum):
    """지원하는 직렬화 포맷"""
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"


class CompressionAlgorithm(Enum):
    """지원하는 압축 알고리즘"""
    NONE = "none"
    ZLIB = "zlib"
    LZ4 = "lz4"
    SNAPPY = "snappy"


class DataSerializer:
    """Redis 데이터 직렬화/역직렬화 및 압축 유틸리티"""
    
    def __init__(self, 
                 default_format: SerializationFormat = SerializationFormat.JSON,
                 default_compression: CompressionAlgorithm = CompressionAlgorithm.ZLIB,
                 compression_level: int = 6):
        """
        초기화
        
        Args:
            default_format: 기본 직렬화 포맷
            default_compression: 기본 압축 알고리즘
            compression_level: 압축 레벨 (1-9, zlib에만 적용)
        """
        self.default_format = default_format
        self.default_compression = default_compression
        self.compression_level = compression_level
        self.logger = logging.getLogger(__name__)
        
        # msgpack 동적 로드
        self.msgpack = None
        try:
            import msgpack
            self.msgpack = msgpack
        except ImportError:
            self.logger.warning("msgpack not installed. MSGPACK format will not be available.")
    
    def serialize(self, 
                  data: Any, 
                  format: Optional[SerializationFormat] = None,
                  compression: Optional[CompressionAlgorithm] = None) -> bytes:
        """
        데이터를 직렬화하고 선택적으로 압축
        
        Args:
            data: 직렬화할 데이터
            format: 직렬화 포맷 (None이면 기본값 사용)
            compression: 압축 알고리즘 (None이면 기본값 사용)
            
        Returns:
            직렬화(및 압축)된 바이트 데이터
        """
        format = format or self.default_format
        compression = compression or self.default_compression
        
        # 1. 직렬화
        serialized = self._serialize_data(data, format)
        
        # 2. 압축 (선택적)
        if compression != CompressionAlgorithm.NONE:
            compressed = self._compress_data(serialized, compression)
            # 메타데이터 추가 (역직렬화시 필요)
            metadata = f"{format.value}:{compression.value}::".encode()
            return metadata + compressed
        else:
            # 압축하지 않는 경우에도 메타데이터 추가
            metadata = f"{format.value}:none::".encode()
            return metadata + serialized
    
    def deserialize(self, data: bytes) -> Any:
        """
        직렬화된(압축된) 데이터를 역직렬화
        
        Args:
            data: 역직렬화할 바이트 데이터
            
        Returns:
            역직렬화된 원본 데이터
        """
        try:
            # 메타데이터 파싱
            header_end = data.find(b'::', 0)
            if header_end == -1:
                # 레거시 포맷 (메타데이터 없음) - JSON으로 가정
                return json.loads(data.decode('utf-8'))
            
            header = data[:header_end].decode('utf-8')
            parts = header.split(':')
            
            if len(parts) >= 2:
                format_str = parts[0]
                compression_str = parts[1]
                
                format = SerializationFormat(format_str)
                compression = CompressionAlgorithm(compression_str)
                
                payload = data[header_end + 2:]
                
                # 1. 압축 해제
                if compression != CompressionAlgorithm.NONE:
                    decompressed = self._decompress_data(payload, compression)
                else:
                    decompressed = payload
                
                # 2. 역직렬화
                return self._deserialize_data(decompressed, format)
            else:
                raise ValueError(f"Invalid metadata header: {header}")
                
        except Exception as e:
            self.logger.error(f"Deserialization failed: {e}")
            raise
    
    def _serialize_data(self, data: Any, format: SerializationFormat) -> bytes:
        """데이터 타입별 직렬화"""
        try:
            if format == SerializationFormat.JSON:
                # JSON 직렬화 - 커스텀 인코더 사용
                json_str = json.dumps(data, cls=ExtendedJSONEncoder)
                return json_str.encode('utf-8')
                
            elif format == SerializationFormat.PICKLE:
                # Pickle 직렬화
                return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
                
            elif format == SerializationFormat.MSGPACK:
                if self.msgpack is None:
                    raise ImportError("msgpack is not installed")
                # MessagePack 직렬화
                return self.msgpack.packb(data, use_bin_type=True)
                
            else:
                raise ValueError(f"Unsupported format: {format}")
                
        except Exception as e:
            self.logger.error(f"Serialization failed for format {format}: {e}")
            raise
    
    def _deserialize_data(self, data: bytes, format: SerializationFormat) -> Any:
        """데이터 타입별 역직렬화"""
        try:
            if format == SerializationFormat.JSON:
                # JSON 역직렬화
                json_str = data.decode('utf-8')
                return json.loads(json_str, cls=ExtendedJSONDecoder)
                
            elif format == SerializationFormat.PICKLE:
                # Pickle 역직렬화
                return pickle.loads(data)
                
            elif format == SerializationFormat.MSGPACK:
                if self.msgpack is None:
                    raise ImportError("msgpack is not installed")
                # MessagePack 역직렬화
                return self.msgpack.unpackb(data, raw=False)
                
            else:
                raise ValueError(f"Unsupported format: {format}")
                
        except Exception as e:
            self.logger.error(f"Deserialization failed for format {format}: {e}")
            raise
    
    def _compress_data(self, data: bytes, algorithm: CompressionAlgorithm) -> bytes:
        """데이터 압축"""
        try:
            if algorithm == CompressionAlgorithm.ZLIB:
                return zlib.compress(data, level=self.compression_level)
                
            elif algorithm == CompressionAlgorithm.LZ4:
                return lz4.frame.compress(data, compression_level=self.compression_level)
                
            elif algorithm == CompressionAlgorithm.SNAPPY:
                return snappy.compress(data)
                
            else:
                raise ValueError(f"Unsupported compression: {algorithm}")
                
        except Exception as e:
            self.logger.error(f"Compression failed for algorithm {algorithm}: {e}")
            raise
    
    def _decompress_data(self, data: bytes, algorithm: CompressionAlgorithm) -> bytes:
        """데이터 압축 해제"""
        try:
            if algorithm == CompressionAlgorithm.ZLIB:
                return zlib.decompress(data)
                
            elif algorithm == CompressionAlgorithm.LZ4:
                return lz4.frame.decompress(data)
                
            elif algorithm == CompressionAlgorithm.SNAPPY:
                return snappy.decompress(data)
                
            else:
                raise ValueError(f"Unsupported compression: {algorithm}")
                
        except Exception as e:
            self.logger.error(f"Decompression failed for algorithm {algorithm}: {e}")
            raise
    
    def get_compression_ratio(self, data: Any, 
                            format: Optional[SerializationFormat] = None,
                            compression: Optional[CompressionAlgorithm] = None) -> Dict[str, Any]:
        """
        압축률 계산
        
        Args:
            data: 분석할 데이터
            format: 직렬화 포맷
            compression: 압축 알고리즘
            
        Returns:
            압축 통계 정보
        """
        format = format or self.default_format
        compression = compression or self.default_compression
        
        # 원본 직렬화
        serialized = self._serialize_data(data, format)
        original_size = len(serialized)
        
        # 압축
        if compression != CompressionAlgorithm.NONE:
            compressed = self._compress_data(serialized, compression)
            compressed_size = len(compressed)
            ratio = (1 - compressed_size / original_size) * 100
        else:
            compressed_size = original_size
            ratio = 0
        
        return {
            'original_size': original_size,
            'compressed_size': compressed_size,
            'compression_ratio': round(ratio, 2),
            'format': format.value,
            'algorithm': compression.value
        }


class ExtendedJSONEncoder(json.JSONEncoder):
    """확장 JSON 인코더 - numpy, pandas, datetime 등 지원"""
    
    def default(self, obj):
        # NumPy 타입
        if isinstance(obj, np.ndarray):
            return {'__numpy__': True, 'data': obj.tolist(), 'dtype': str(obj.dtype)}
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        
        # Pandas 타입
        elif isinstance(obj, pd.DataFrame):
            return {
                '__pandas_df__': True,
                'data': obj.to_dict('records'),
                'index': obj.index.tolist(),
                'columns': obj.columns.tolist()
            }
        elif isinstance(obj, pd.Series):
            return {
                '__pandas_series__': True,
                'data': obj.tolist(),
                'index': obj.index.tolist(),
                'name': obj.name
            }
        
        # 날짜/시간 타입
        elif isinstance(obj, datetime):
            return {'__datetime__': True, 'value': obj.isoformat()}
        elif isinstance(obj, date):
            return {'__date__': True, 'value': obj.isoformat()}
        
        # bytes 타입
        elif isinstance(obj, bytes):
            return {'__bytes__': True, 'value': base64.b64encode(obj).decode('ascii')}
        
        return super().default(obj)


class ExtendedJSONDecoder(json.JSONDecoder):
    """확장 JSON 디코더"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)
    
    def object_hook(self, obj):
        # NumPy 타입
        if '__numpy__' in obj:
            arr = np.array(obj['data'])
            if 'dtype' in obj:
                arr = arr.astype(obj['dtype'])
            return arr
        
        # Pandas DataFrame
        elif '__pandas_df__' in obj:
            df = pd.DataFrame(obj['data'], index=obj['index'], columns=obj['columns'])
            return df
        
        # Pandas Series
        elif '__pandas_series__' in obj:
            series = pd.Series(obj['data'], index=obj['index'], name=obj.get('name'))
            return series
        
        # 날짜/시간 타입
        elif '__datetime__' in obj:
            return datetime.fromisoformat(obj['value'])
        elif '__date__' in obj:
            return date.fromisoformat(obj['value'])
        
        # bytes 타입
        elif '__bytes__' in obj:
            return base64.b64decode(obj['value'])
        
        return obj


# Redis 특화 직렬화 헬퍼 함수들
def serialize_for_redis(data: Any, compress: bool = True) -> bytes:
    """Redis 저장을 위한 간편 직렬화"""
    serializer = DataSerializer(
        default_compression=CompressionAlgorithm.LZ4 if compress else CompressionAlgorithm.NONE
    )
    return serializer.serialize(data)


def deserialize_from_redis(data: bytes) -> Any:
    """Redis에서 읽은 데이터의 간편 역직렬화"""
    serializer = DataSerializer()
    return serializer.deserialize(data)


def get_optimal_compression(data: Any) -> Dict[str, Any]:
    """데이터에 대한 최적 압축 알고리즘 찾기"""
    serializer = DataSerializer()
    results = []
    
    for algo in CompressionAlgorithm:
        if algo == CompressionAlgorithm.NONE:
            continue
            
        try:
            stats = serializer.get_compression_ratio(
                data, 
                format=SerializationFormat.JSON,
                compression=algo
            )
            results.append(stats)
        except:
            pass
    
    # 압축률이 가장 높은 알고리즘 반환
    return max(results, key=lambda x: x['compression_ratio']) if results else None