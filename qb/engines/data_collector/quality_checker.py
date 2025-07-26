"""
Data Quality Checker

데이터 품질 검증 및 이상치 탐지 컴포넌트
"""

import logging
import statistics
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass
from enum import Enum


class QualityIssueType(Enum):
    """데이터 품질 이슈 타입"""
    MISSING_FIELD = "missing_field"
    INVALID_VALUE = "invalid_value"
    OUTLIER_PRICE = "outlier_price"
    OUTLIER_VOLUME = "outlier_volume"
    STALE_DATA = "stale_data"
    DUPLICATE_DATA = "duplicate_data"
    PRICE_GAP = "price_gap"
    VOLUME_SPIKE = "volume_spike"


@dataclass
class QualityIssue:
    """데이터 품질 이슈"""
    issue_type: QualityIssueType
    field: Optional[str]
    value: Any
    expected_range: Optional[Tuple[float, float]]
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str


class DataQualityChecker:
    """
    데이터 품질 검증기
    
    실시간 데이터의 품질을 검증하고 이상치를 탐지
    """
    
    def __init__(self, history_size: int = 100):
        self.logger = logging.getLogger(__name__)
        self.history_size = history_size
        
        # 심볼별 과거 데이터 저장 (이상치 탐지용)
        self.price_history: Dict[str, deque] = {}
        self.volume_history: Dict[str, deque] = {}
        self.last_data: Dict[str, Dict[str, Any]] = {}
        
        # 검증 설정
        self.config = {
            'max_price_change_percent': 30.0,  # 최대 가격 변동률 (%)
            'max_volume_multiplier': 10.0,     # 최대 거래량 배수
            'stale_data_minutes': 5,           # 오래된 데이터 기준 (분)
            'price_outlier_threshold': 3.0,   # 가격 이상치 임계값 (표준편차)
            'volume_outlier_threshold': 3.0,  # 거래량 이상치 임계값 (표준편차)
            'min_price': 1.0,                 # 최소 가격
            'max_price': 1000000.0,           # 최대 가격
            'min_volume': 0,                  # 최소 거래량
            'max_volume': 1000000000          # 최대 거래량
        }
        
        # 통계
        self.stats = {
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': 0,
            'issues_by_type': {issue_type.value: 0 for issue_type in QualityIssueType},
            'last_check_time': None
        }
    
    async def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[QualityIssue]]:
        """
        데이터 검증
        
        Args:
            data: 검증할 데이터
            
        Returns:
            (검증 통과 여부, 발견된 이슈 목록)
        """
        self.stats['total_checks'] += 1
        self.stats['last_check_time'] = datetime.now().isoformat()
        
        issues = []
        
        try:
            # 1. 필수 필드 검증
            issues.extend(self._check_required_fields(data))
            
            # 2. 데이터 타입 및 범위 검증
            issues.extend(self._check_data_types_and_ranges(data))
            
            # 3. 오래된 데이터 검증
            issues.extend(self._check_stale_data(data))
            
            # 4. 중복 데이터 검증
            issues.extend(self._check_duplicate_data(data))
            
            # 5. 가격 이상치 검증
            issues.extend(self._check_price_outliers(data))
            
            # 6. 거래량 이상치 검증
            issues.extend(self._check_volume_outliers(data))
            
            # 7. 가격 급변 검증
            issues.extend(self._check_price_gaps(data))
            
            # 이력 업데이트
            self._update_history(data)
            
            # 통계 업데이트
            if issues:
                self.stats['failed_checks'] += 1
                for issue in issues:
                    self.stats['issues_by_type'][issue.issue_type.value] += 1
            else:
                self.stats['passed_checks'] += 1
            
            # 심각한 이슈가 있는지 확인
            has_critical_issues = any(issue.severity == 'critical' for issue in issues)
            
            return not has_critical_issues, issues
            
        except Exception as e:
            self.logger.error(f"Data validation error: {e}")
            self.stats['failed_checks'] += 1
            return False, [QualityIssue(
                issue_type=QualityIssueType.INVALID_VALUE,
                field=None,
                value=None,
                expected_range=None,
                severity='critical',
                message=f"Validation error: {e}"
            )]
    
    def _check_required_fields(self, data: Dict[str, Any]) -> List[QualityIssue]:
        """필수 필드 검증"""
        issues = []
        required_fields = ['symbol', 'timestamp', 'close']
        
        for field in required_fields:
            if field not in data or data[field] is None:
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.MISSING_FIELD,
                    field=field,
                    value=None,
                    expected_range=None,
                    severity='critical',
                    message=f"Missing required field: {field}"
                ))
        
        return issues
    
    def _check_data_types_and_ranges(self, data: Dict[str, Any]) -> List[QualityIssue]:
        """데이터 타입 및 범위 검증"""
        issues = []
        
        # 심볼 검증
        if 'symbol' in data:
            symbol = data['symbol']
            if not isinstance(symbol, str) or not symbol.strip():
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.INVALID_VALUE,
                    field='symbol',
                    value=symbol,
                    expected_range=None,
                    severity='critical',
                    message="Invalid symbol format"
                ))
        
        # 가격 필드 검증
        price_fields = ['open', 'high', 'low', 'close']
        for field in price_fields:
            if field in data:
                value = data[field]
                if not isinstance(value, (int, float)):
                    issues.append(QualityIssue(
                        issue_type=QualityIssueType.INVALID_VALUE,
                        field=field,
                        value=value,
                        expected_range=(self.config['min_price'], self.config['max_price']),
                        severity='high',
                        message=f"Invalid {field} data type"
                    ))
                elif not (self.config['min_price'] <= value <= self.config['max_price']):
                    issues.append(QualityIssue(
                        issue_type=QualityIssueType.INVALID_VALUE,
                        field=field,
                        value=value,
                        expected_range=(self.config['min_price'], self.config['max_price']),
                        severity='critical',
                        message=f"Price {field} out of range: {value}"
                    ))
        
        # 거래량 검증
        if 'volume' in data:
            volume = data['volume']
            if not isinstance(volume, int):
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.INVALID_VALUE,
                    field='volume',
                    value=volume,
                    expected_range=(self.config['min_volume'], self.config['max_volume']),
                    severity='medium',
                    message="Invalid volume data type"
                ))
            elif not (self.config['min_volume'] <= volume <= self.config['max_volume']):
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.INVALID_VALUE,
                    field='volume',
                    value=volume,
                    expected_range=(self.config['min_volume'], self.config['max_volume']),
                    severity='medium',
                    message=f"Volume out of range: {volume}"
                ))
        
        # OHLC 논리 검증
        if all(field in data for field in ['open', 'high', 'low', 'close']):
            o, h, l, c = data['open'], data['high'], data['low'], data['close']
            if not (l <= o <= h and l <= c <= h):
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.INVALID_VALUE,
                    field='ohlc',
                    value={'open': o, 'high': h, 'low': l, 'close': c},
                    expected_range=None,
                    severity='high',
                    message=f"Invalid OHLC relationship: O={o}, H={h}, L={l}, C={c}"
                ))
        
        return issues
    
    def _check_stale_data(self, data: Dict[str, Any]) -> List[QualityIssue]:
        """오래된 데이터 검증"""
        issues = []
        
        if 'timestamp' in data:
            try:
                if isinstance(data['timestamp'], str):
                    timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                else:
                    timestamp = data['timestamp']
                
                age = (datetime.now() - timestamp.replace(tzinfo=None)).total_seconds() / 60
                
                if age > self.config['stale_data_minutes']:
                    issues.append(QualityIssue(
                        issue_type=QualityIssueType.STALE_DATA,
                        field='timestamp',
                        value=data['timestamp'],
                        expected_range=None,
                        severity='medium',
                        message=f"Data is {age:.1f} minutes old"
                    ))
                    
            except Exception as e:
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.INVALID_VALUE,
                    field='timestamp',
                    value=data['timestamp'],
                    expected_range=None,
                    severity='high',
                    message=f"Invalid timestamp format: {e}"
                ))
        
        return issues
    
    def _check_duplicate_data(self, data: Dict[str, Any]) -> List[QualityIssue]:
        """중복 데이터 검증"""
        issues = []
        
        symbol = data.get('symbol')
        if not symbol:
            return issues
        
        # 이전 데이터와 비교
        if symbol in self.last_data:
            last = self.last_data[symbol]
            
            # 동일한 타임스탬프와 가격인지 확인
            if (data.get('timestamp') == last.get('timestamp') and
                data.get('close') == last.get('close')):
                issues.append(QualityIssue(
                    issue_type=QualityIssueType.DUPLICATE_DATA,
                    field='data',
                    value=data,
                    expected_range=None,
                    severity='low',
                    message="Duplicate data detected"
                ))
        
        return issues
    
    def _check_price_outliers(self, data: Dict[str, Any]) -> List[QualityIssue]:
        """가격 이상치 검증"""
        issues = []
        
        symbol = data.get('symbol')
        close_price = data.get('close')
        
        if not symbol or close_price is None:
            return issues
        
        # 충분한 이력이 있을 때만 검사
        if symbol in self.price_history and len(self.price_history[symbol]) >= 10:
            prices = list(self.price_history[symbol])
            
            try:
                mean_price = statistics.mean(prices)
                stdev_price = statistics.stdev(prices)
                
                if stdev_price > 0:
                    z_score = abs(close_price - mean_price) / stdev_price
                    
                    if z_score > self.config['price_outlier_threshold']:
                        issues.append(QualityIssue(
                            issue_type=QualityIssueType.OUTLIER_PRICE,
                            field='close',
                            value=close_price,
                            expected_range=(mean_price - 2*stdev_price, mean_price + 2*stdev_price),
                            severity='medium',
                            message=f"Price outlier detected: {close_price} (z-score: {z_score:.2f})"
                        ))
                        
            except statistics.StatisticsError:
                pass  # 계산 불가능한 경우 무시
        
        return issues
    
    def _check_volume_outliers(self, data: Dict[str, Any]) -> List[QualityIssue]:
        """거래량 이상치 검증"""
        issues = []
        
        symbol = data.get('symbol')
        volume = data.get('volume')
        
        if not symbol or volume is None:
            return issues
        
        # 충분한 이력이 있을 때만 검사
        if symbol in self.volume_history and len(self.volume_history[symbol]) >= 10:
            volumes = list(self.volume_history[symbol])
            
            try:
                mean_volume = statistics.mean(volumes)
                
                if mean_volume > 0:
                    ratio = volume / mean_volume
                    
                    if ratio > self.config['max_volume_multiplier']:
                        issues.append(QualityIssue(
                            issue_type=QualityIssueType.VOLUME_SPIKE,
                            field='volume',
                            value=volume,
                            expected_range=(0, mean_volume * self.config['max_volume_multiplier']),
                            severity='medium',
                            message=f"Volume spike detected: {volume} ({ratio:.1f}x average)"
                        ))
                        
            except (statistics.StatisticsError, ZeroDivisionError):
                pass
        
        return issues
    
    def _check_price_gaps(self, data: Dict[str, Any]) -> List[QualityIssue]:
        """가격 급변 검증"""
        issues = []
        
        symbol = data.get('symbol')
        close_price = data.get('close')
        
        if not symbol or close_price is None:
            return issues
        
        # 이전 가격과 비교
        if symbol in self.last_data and 'close' in self.last_data[symbol]:
            last_price = self.last_data[symbol]['close']
            
            if last_price > 0:
                change_percent = abs((close_price - last_price) / last_price) * 100
                
                if change_percent > self.config['max_price_change_percent']:
                    issues.append(QualityIssue(
                        issue_type=QualityIssueType.PRICE_GAP,
                        field='close',
                        value=close_price,
                        expected_range=(
                            last_price * (1 - self.config['max_price_change_percent']/100),
                            last_price * (1 + self.config['max_price_change_percent']/100)
                        ),
                        severity='high',
                        message=f"Large price gap: {change_percent:.1f}% change from {last_price} to {close_price}"
                    ))
        
        return issues
    
    def _update_history(self, data: Dict[str, Any]):
        """이력 데이터 업데이트"""
        symbol = data.get('symbol')
        if not symbol:
            return
        
        # 가격 이력 업데이트
        if 'close' in data:
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=self.history_size)
            self.price_history[symbol].append(data['close'])
        
        # 거래량 이력 업데이트
        if 'volume' in data:
            if symbol not in self.volume_history:
                self.volume_history[symbol] = deque(maxlen=self.history_size)
            self.volume_history[symbol].append(data['volume'])
        
        # 마지막 데이터 저장
        self.last_data[symbol] = data.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """품질 검증 통계 반환"""
        return self.stats.copy()
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': 0,
            'issues_by_type': {issue_type.value: 0 for issue_type in QualityIssueType},
            'last_check_time': None
        }
    
    def update_config(self, new_config: Dict[str, Any]):
        """설정 업데이트"""
        self.config.update(new_config)
        self.logger.info(f"Quality checker config updated: {new_config}")
    
    def clear_history(self, symbol: Optional[str] = None):
        """이력 데이터 삭제"""
        if symbol:
            self.price_history.pop(symbol, None)
            self.volume_history.pop(symbol, None)
            self.last_data.pop(symbol, None)
        else:
            self.price_history.clear()
            self.volume_history.clear()
            self.last_data.clear()
        
        self.logger.info(f"History cleared for {symbol if symbol else 'all symbols'}")