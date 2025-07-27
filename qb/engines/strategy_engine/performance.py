"""
전략 성과 추적기 모듈

전략별 성과를 실시간으로 추적하고 기록하는 시스템을 구현합니다.
거래 신호의 정확성, 수익률, 승률 등 다양한 성과 지표를 계산하고 저장합니다.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging
import numpy as np

from .base import TradingSignal
from ...utils.redis_manager import RedisManager

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """성과 지표 데이터 클래스"""
    strategy_name: str
    total_signals: int = 0
    buy_signals: int = 0
    sell_signals: int = 0
    hold_signals: int = 0
    
    # 수익률 관련
    total_return: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    
    # 승률 관련
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # 리스크 지표
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    volatility: float = 0.0
    
    # 시간 관련
    avg_hold_time: float = 0.0  # 평균 보유 시간 (시간 단위)
    last_updated: Optional[datetime] = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()


@dataclass
class SignalRecord:
    """신호 기록 데이터 클래스"""
    signal_id: str
    strategy_name: str
    symbol: str
    action: str
    confidence: float
    price: float
    quantity: int
    timestamp: datetime
    reason: str
    metadata: Dict[str, Any]
    
    # 실행 결과
    executed: bool = False
    execution_price: Optional[float] = None
    execution_time: Optional[datetime] = None
    
    # 성과 추적
    current_price: Optional[float] = None
    pnl: Optional[float] = None
    closed: bool = False
    close_price: Optional[float] = None
    close_time: Optional[datetime] = None


class StrategyPerformanceTracker:
    """
    전략 성과 추적기
    
    전략별로 생성된 신호의 성과를 실시간으로 추적하고,
    다양한 성과 지표를 계산하여 Redis에 저장합니다.
    """

    def __init__(self, redis_manager: RedisManager):
        """
        성과 추적기 초기화
        
        Args:
            redis_manager: Redis 연결 관리자
        """
        self.redis = redis_manager
        
        # Redis 키 접두사
        self.metrics_prefix = "strategy_metrics"
        self.signals_prefix = "strategy_signals"
        self.positions_prefix = "strategy_positions"
        
        # 메모리 캐시 (성능 향상용)
        self.metrics_cache: Dict[str, PerformanceMetrics] = {}
        self.signal_records: Dict[str, SignalRecord] = {}
        
        # 성과 계산 설정
        self.risk_free_rate = 0.02  # 무위험 수익률 (연 2%)
        self.trading_days_per_year = 252
        
        logger.info("StrategyPerformanceTracker initialized")

    async def record_signal(self, strategy_name: str, signal: TradingSignal) -> bool:
        """
        전략 신호 기록
        
        Args:
            strategy_name: 전략명
            signal: 거래 신호
            
        Returns:
            bool: 기록 성공 여부
        """
        try:
            # 신호 ID 생성
            signal_id = f"{strategy_name}_{signal.symbol}_{signal.timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            # 신호 기록 생성
            signal_record = SignalRecord(
                signal_id=signal_id,
                strategy_name=strategy_name,
                symbol=signal.symbol,
                action=signal.action,
                confidence=signal.confidence,
                price=signal.price or 0.0,
                quantity=signal.quantity or 0,
                timestamp=signal.timestamp,
                reason=signal.reason or "",
                metadata=signal.metadata or {}
            )
            
            # 메모리 캐시에 저장
            self.signal_records[signal_id] = signal_record
            
            # Redis에 저장
            await self._save_signal_record(signal_record)
            
            # 성과 지표 업데이트
            await self._update_strategy_metrics(strategy_name, signal)
            
            logger.debug(f"Recorded signal for strategy {strategy_name}: {signal.action} {signal.symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording signal for strategy {strategy_name}: {e}")
            return False

    async def record_signal_execution(self, signal_id: str, execution_price: float, 
                                    execution_time: Optional[datetime] = None) -> bool:
        """
        신호 실행 결과 기록
        
        Args:
            signal_id: 신호 ID
            execution_price: 실행 가격
            execution_time: 실행 시간
            
        Returns:
            bool: 기록 성공 여부
        """
        try:
            if signal_id not in self.signal_records:
                # Redis에서 신호 기록 로드
                signal_record = await self._load_signal_record(signal_id)
                if not signal_record:
                    logger.error(f"Signal record not found: {signal_id}")
                    return False
            else:
                signal_record = self.signal_records[signal_id]
            
            # 실행 정보 업데이트
            signal_record.executed = True
            signal_record.execution_price = execution_price
            signal_record.execution_time = execution_time or datetime.now()
            
            # 저장
            await self._save_signal_record(signal_record)
            
            logger.debug(f"Recorded execution for signal {signal_id}: price={execution_price}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording signal execution {signal_id}: {e}")
            return False

    async def update_position_pnl(self, signal_id: str, current_price: float) -> bool:
        """
        포지션 손익 업데이트
        
        Args:
            signal_id: 신호 ID
            current_price: 현재 가격
            
        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            if signal_id not in self.signal_records:
                signal_record = await self._load_signal_record(signal_id)
                if not signal_record:
                    logger.error(f"Signal record not found: {signal_id}")
                    return False
            else:
                signal_record = self.signal_records[signal_id]
            
            if not signal_record.executed or signal_record.closed:
                return False
            
            # 손익 계산
            execution_price = signal_record.execution_price
            if signal_record.action == 'BUY':
                pnl = (current_price - execution_price) * signal_record.quantity
            elif signal_record.action == 'SELL':
                pnl = (execution_price - current_price) * signal_record.quantity
            else:
                pnl = 0.0
            
            # 업데이트
            signal_record.current_price = current_price
            signal_record.pnl = pnl
            
            # 저장
            await self._save_signal_record(signal_record)
            
            # 전략 지표 업데이트
            await self._recalculate_strategy_metrics(signal_record.strategy_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating position PnL for signal {signal_id}: {e}")
            return False

    async def close_position(self, signal_id: str, close_price: float, 
                           close_time: Optional[datetime] = None) -> bool:
        """
        포지션 종료 기록
        
        Args:
            signal_id: 신호 ID
            close_price: 종료 가격
            close_time: 종료 시간
            
        Returns:
            bool: 기록 성공 여부
        """
        try:
            if signal_id not in self.signal_records:
                signal_record = await self._load_signal_record(signal_id)
                if not signal_record:
                    logger.error(f"Signal record not found: {signal_id}")
                    return False
            else:
                signal_record = self.signal_records[signal_id]
            
            if not signal_record.executed or signal_record.closed:
                return False
            
            # 종료 정보 업데이트
            signal_record.closed = True
            signal_record.close_price = close_price
            signal_record.close_time = close_time or datetime.now()
            
            # 최종 손익 계산
            execution_price = signal_record.execution_price
            if signal_record.action == 'BUY':
                final_pnl = (close_price - execution_price) * signal_record.quantity
            elif signal_record.action == 'SELL':
                final_pnl = (execution_price - close_price) * signal_record.quantity
            else:
                final_pnl = 0.0
            
            signal_record.pnl = final_pnl
            
            # 저장
            await self._save_signal_record(signal_record)
            
            # 전략 지표 업데이트
            await self._recalculate_strategy_metrics(signal_record.strategy_name)
            
            logger.debug(f"Closed position for signal {signal_id}: PnL={final_pnl}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing position for signal {signal_id}: {e}")
            return False

    async def get_strategy_performance(self, strategy_name: str, 
                                     timeframe: str = "1d") -> Optional[PerformanceMetrics]:
        """
        전략 성과 조회
        
        Args:
            strategy_name: 전략명
            timeframe: 시간 프레임 ('1h', '1d', '1w', '1m', 'all')
            
        Returns:
            PerformanceMetrics: 성과 지표 또는 None
        """
        try:
            # 캐시에서 확인
            if strategy_name in self.metrics_cache:
                metrics = self.metrics_cache[strategy_name]
                
                # 시간 프레임에 따른 필터링 (필요한 경우)
                if timeframe != "all":
                    metrics = await self._filter_metrics_by_timeframe(strategy_name, timeframe)
                
                return metrics
            
            # Redis에서 로드
            metrics = await self._load_strategy_metrics(strategy_name)
            if metrics:
                self.metrics_cache[strategy_name] = metrics
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting strategy performance for {strategy_name}: {e}")
            return None

    async def get_signal_history(self, strategy_name: str, 
                               limit: int = 100) -> List[SignalRecord]:
        """
        전략의 신호 히스토리 조회
        
        Args:
            strategy_name: 전략명
            limit: 조회할 신호 개수
            
        Returns:
            List[SignalRecord]: 신호 기록 리스트
        """
        try:
            # Redis에서 신호 히스토리 조회
            redis_key = f"{self.signals_prefix}:{strategy_name}:history"
            signal_ids = await self.redis.get_list_range(redis_key, 0, limit - 1)
            
            signal_records = []
            for signal_id in signal_ids:
                if signal_id in self.signal_records:
                    signal_records.append(self.signal_records[signal_id])
                else:
                    signal_record = await self._load_signal_record(signal_id)
                    if signal_record:
                        signal_records.append(signal_record)
            
            # 시간순 정렬 (최신 순)
            signal_records.sort(key=lambda x: x.timestamp, reverse=True)
            
            return signal_records[:limit]
            
        except Exception as e:
            logger.error(f"Error getting signal history for {strategy_name}: {e}")
            return []

    async def get_all_strategies_performance(self) -> Dict[str, PerformanceMetrics]:
        """모든 전략의 성과 조회"""
        try:
            # Redis에서 모든 전략명 조회
            pattern = f"{self.metrics_prefix}:*"
            keys = await self.redis.scan_keys(pattern)
            
            all_performance = {}
            for key in keys:
                strategy_name = key.split(":")[-1]
                metrics = await self.get_strategy_performance(strategy_name)
                if metrics:
                    all_performance[strategy_name] = metrics
            
            return all_performance
            
        except Exception as e:
            logger.error(f"Error getting all strategies performance: {e}")
            return {}

    async def _save_signal_record(self, signal_record: SignalRecord):
        """신호 기록을 Redis에 저장"""
        try:
            # 개별 신호 저장
            redis_key = f"{self.signals_prefix}:{signal_record.signal_id}"
            record_data = asdict(signal_record)
            
            # datetime 객체를 문자열로 변환
            for key, value in record_data.items():
                if isinstance(value, datetime):
                    record_data[key] = value.isoformat()
            
            await self.redis.set_data(redis_key, json.dumps(record_data))
            
            # 전략별 신호 히스토리에 추가
            history_key = f"{self.signals_prefix}:{signal_record.strategy_name}:history"
            await self.redis.add_to_list(history_key, signal_record.signal_id)
            
            # 히스토리 크기 제한 (최근 1000개만 유지)
            await self.redis.trim_list(history_key, 0, 999)
            
        except Exception as e:
            logger.error(f"Error saving signal record: {e}")

    async def _load_signal_record(self, signal_id: str) -> Optional[SignalRecord]:
        """Redis에서 신호 기록 로드"""
        try:
            redis_key = f"{self.signals_prefix}:{signal_id}"
            data = await self.redis.get_data(redis_key)
            
            if not data:
                return None
            
            if isinstance(data, str):
                record_data = json.loads(data)
            else:
                record_data = data
            
            # datetime 문자열을 객체로 변환
            for key in ['timestamp', 'execution_time', 'close_time']:
                if record_data.get(key):
                    record_data[key] = datetime.fromisoformat(record_data[key])
            
            signal_record = SignalRecord(**record_data)
            self.signal_records[signal_id] = signal_record
            
            return signal_record
            
        except Exception as e:
            logger.error(f"Error loading signal record {signal_id}: {e}")
            return None

    async def _update_strategy_metrics(self, strategy_name: str, signal: TradingSignal):
        """전략 지표 업데이트"""
        try:
            # 기존 지표 로드
            metrics = await self.get_strategy_performance(strategy_name)
            if not metrics:
                metrics = PerformanceMetrics(strategy_name=strategy_name)
            
            # 신호 카운트 업데이트
            metrics.total_signals += 1
            
            if signal.action == 'BUY':
                metrics.buy_signals += 1
            elif signal.action == 'SELL':
                metrics.sell_signals += 1
            else:
                metrics.hold_signals += 1
            
            metrics.last_updated = datetime.now()
            
            # 저장
            await self._save_strategy_metrics(strategy_name, metrics)
            
        except Exception as e:
            logger.error(f"Error updating strategy metrics for {strategy_name}: {e}")

    async def _recalculate_strategy_metrics(self, strategy_name: str):
        """전략 지표 재계산"""
        try:
            # 전략의 모든 신호 기록 조회
            signal_records = await self.get_signal_history(strategy_name, 10000)
            
            # 메트릭 초기화
            metrics = PerformanceMetrics(strategy_name=strategy_name)
            
            total_pnl = 0.0
            realized_pnl = 0.0
            unrealized_pnl = 0.0
            winning_trades = 0
            losing_trades = 0
            returns = []
            hold_times = []
            
            for record in signal_records:
                # 신호 카운트
                metrics.total_signals += 1
                if record.action == 'BUY':
                    metrics.buy_signals += 1
                elif record.action == 'SELL':
                    metrics.sell_signals += 1
                else:
                    metrics.hold_signals += 1
                
                # 손익 계산
                if record.executed and record.pnl is not None:
                    total_pnl += record.pnl
                    
                    if record.closed:
                        realized_pnl += record.pnl
                        if record.pnl > 0:
                            winning_trades += 1
                        elif record.pnl < 0:
                            losing_trades += 1
                        
                        # 수익률 계산
                        if record.execution_price and record.execution_price > 0:
                            return_rate = record.pnl / (record.execution_price * record.quantity)
                            returns.append(return_rate)
                        
                        # 보유 시간 계산
                        if record.execution_time and record.close_time:
                            hold_time = (record.close_time - record.execution_time).total_seconds() / 3600
                            hold_times.append(hold_time)
                    else:
                        unrealized_pnl += record.pnl
            
            # 지표 업데이트
            metrics.total_return = total_pnl
            metrics.realized_pnl = realized_pnl
            metrics.unrealized_pnl = unrealized_pnl
            metrics.winning_trades = winning_trades
            metrics.losing_trades = losing_trades
            
            # 승률 계산
            total_closed_trades = winning_trades + losing_trades
            if total_closed_trades > 0:
                metrics.win_rate = winning_trades / total_closed_trades
            
            # 평균 보유 시간
            if hold_times:
                metrics.avg_hold_time = np.mean(hold_times)
            
            # 리스크 지표 계산
            if len(returns) > 1:
                returns_array = np.array(returns)
                
                # 변동성 (연환산)
                metrics.volatility = np.std(returns_array) * np.sqrt(self.trading_days_per_year)
                
                # 샤프 비율
                avg_return = np.mean(returns_array)
                if metrics.volatility > 0:
                    excess_return = avg_return - (self.risk_free_rate / self.trading_days_per_year)
                    metrics.sharpe_ratio = excess_return / (metrics.volatility / np.sqrt(self.trading_days_per_year))
                
                # 최대 낙폭 계산
                cumulative_returns = np.cumprod(1 + returns_array) - 1
                running_max = np.maximum.accumulate(cumulative_returns)
                drawdowns = (cumulative_returns - running_max) / (1 + running_max)
                metrics.max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0.0
            
            metrics.last_updated = datetime.now()
            
            # 저장
            await self._save_strategy_metrics(strategy_name, metrics)
            
        except Exception as e:
            logger.error(f"Error recalculating strategy metrics for {strategy_name}: {e}")

    async def _save_strategy_metrics(self, strategy_name: str, metrics: PerformanceMetrics):
        """전략 지표를 Redis에 저장"""
        try:
            redis_key = f"{self.metrics_prefix}:{strategy_name}"
            metrics_data = asdict(metrics)
            
            # datetime 객체를 문자열로 변환
            if metrics_data.get('last_updated'):
                metrics_data['last_updated'] = metrics_data['last_updated'].isoformat()
            
            await self.redis.set_data(redis_key, json.dumps(metrics_data))
            
            # 캐시 업데이트
            self.metrics_cache[strategy_name] = metrics
            
        except Exception as e:
            logger.error(f"Error saving strategy metrics for {strategy_name}: {e}")

    async def _load_strategy_metrics(self, strategy_name: str) -> Optional[PerformanceMetrics]:
        """Redis에서 전략 지표 로드"""
        try:
            redis_key = f"{self.metrics_prefix}:{strategy_name}"
            data = await self.redis.get_data(redis_key)
            
            if not data:
                return None
            
            if isinstance(data, str):
                metrics_data = json.loads(data)
            else:
                metrics_data = data
            
            # datetime 문자열을 객체로 변환
            if metrics_data.get('last_updated'):
                metrics_data['last_updated'] = datetime.fromisoformat(metrics_data['last_updated'])
            
            return PerformanceMetrics(**metrics_data)
            
        except Exception as e:
            logger.error(f"Error loading strategy metrics for {strategy_name}: {e}")
            return None

    async def _filter_metrics_by_timeframe(self, strategy_name: str, 
                                         timeframe: str) -> Optional[PerformanceMetrics]:
        """시간 프레임에 따른 지표 필터링"""
        # 현재는 기본 구현만 제공 (향후 확장 가능)
        return await self.get_strategy_performance(strategy_name)

    def get_tracker_status(self) -> Dict[str, Any]:
        """추적기 상태 정보 반환"""
        return {
            'cached_strategies': len(self.metrics_cache),
            'cached_signals': len(self.signal_records),
            'risk_free_rate': self.risk_free_rate,
            'trading_days_per_year': self.trading_days_per_year
        }

    def __str__(self) -> str:
        return f"StrategyPerformanceTracker(strategies={len(self.metrics_cache)})"

    def __repr__(self) -> str:
        return f"<StrategyPerformanceTracker cached_strategies={len(self.metrics_cache)}>"