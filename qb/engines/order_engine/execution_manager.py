"""
체결 관리 시스템 (Execution Manager)

QB Trading System의 부분/완전 체결 처리 및 미체결 주문 추적 시스템입니다.
복잡한 체결 시나리오를 관리하고 체결 완료까지 추적합니다.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from .base import Order, Fill, OrderStatus, OrderSide, OrderType
from .event_handler import OrderEventHandler
from ...utils.redis_manager import RedisManager
from ...utils.event_bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class ExecutionTracker:
    """체결 추적기"""
    order_id: str
    symbol: str
    total_quantity: int
    filled_quantity: int = 0
    average_fill_price: float = 0.0
    total_commission: float = 0.0
    fills: List[Fill] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_fill_at: Optional[datetime] = None
    
    @property
    def remaining_quantity(self) -> int:
        """미체결 수량"""
        return self.total_quantity - self.filled_quantity
    
    @property
    def fill_ratio(self) -> float:
        """체결률"""
        return self.filled_quantity / self.total_quantity if self.total_quantity > 0 else 0.0
    
    @property
    def is_fully_filled(self) -> bool:
        """완전 체결 여부"""
        return self.filled_quantity >= self.total_quantity
    
    @property
    def is_partially_filled(self) -> bool:
        """부분 체결 여부"""
        return 0 < self.filled_quantity < self.total_quantity
    
    def add_fill(self, fill: Fill):
        """체결 추가"""
        if self.filled_quantity + fill.quantity > self.total_quantity:
            raise ValueError(f"Fill quantity exceeds remaining: {fill.quantity} > {self.remaining_quantity}")
        
        # 평균 체결가 계산
        if self.filled_quantity == 0:
            self.average_fill_price = fill.price
        else:
            total_value = (self.average_fill_price * self.filled_quantity) + (fill.price * fill.quantity)
            self.average_fill_price = total_value / (self.filled_quantity + fill.quantity)
        
        self.filled_quantity += fill.quantity
        self.total_commission += fill.commission
        self.fills.append(fill)
        self.last_fill_at = fill.timestamp


class ExecutionManager:
    """
    체결 관리 시스템
    
    주요 기능:
    1. 부분 체결 추적 및 관리
    2. 미체결 주문 모니터링
    3. 체결 완료 알림
    4. 체결 통계 및 분석
    5. 비정상 체결 감지
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        redis_manager: RedisManager,
        event_handler: OrderEventHandler,
        config: Optional[Dict[str, Any]] = None
    ):
        self.event_bus = event_bus
        self.redis_manager = redis_manager
        self.event_handler = event_handler
        self.config = config or {}
        
        # 설정값
        self.max_partial_fill_time = self.config.get("max_partial_fill_time", 300)  # 5분
        self.min_fill_size = self.config.get("min_fill_size", 1)
        self.max_fills_per_order = self.config.get("max_fills_per_order", 100)
        
        # 체결 추적기들
        self._execution_trackers: Dict[str, ExecutionTracker] = {}
        self._tracker_lock = asyncio.Lock()
        
        # 통계
        self._daily_stats = defaultdict(int)
        self._unusual_executions: List[Dict[str, Any]] = []
        
        # Redis 키
        self.execution_key_prefix = "executions"
        self.stats_key_prefix = "execution_stats"
        
        logger.info("ExecutionManager initialized")
    
    async def start(self):
        """체결 관리자 시작"""
        try:
            # 이벤트 구독
            self.event_bus.subscribe("order_executed", self._handle_order_executed)
            self.event_bus.subscribe("order_placed", self._handle_order_placed)
            self.event_bus.subscribe("order_cancelled", self._handle_order_cancelled)
            
            # 주기적 작업 시작
            asyncio.create_task(self._monitor_partial_fills())
            asyncio.create_task(self._update_daily_stats())
            
            # Redis에서 기존 추적기들 로드
            await self._load_execution_trackers()
            
            logger.info("ExecutionManager started")
            
        except Exception as e:
            logger.error(f"Error starting ExecutionManager: {e}")
            raise
    
    async def stop(self):
        """체결 관리자 중지"""
        try:
            # 이벤트 구독 해제
            self.event_bus.unsubscribe("order_executed", self._handle_order_executed)
            self.event_bus.unsubscribe("order_placed", self._handle_order_placed)
            self.event_bus.unsubscribe("order_cancelled", self._handle_order_cancelled)
            
            # 모든 추적기를 Redis에 저장
            await self._save_all_trackers()
            
            logger.info("ExecutionManager stopped")
            
        except Exception as e:
            logger.error(f"Error stopping ExecutionManager: {e}")
    
    async def get_execution_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """체결 상태 조회"""
        try:
            tracker = self._execution_trackers.get(order_id)
            if not tracker:
                return None
            
            return {
                "order_id": tracker.order_id,
                "symbol": tracker.symbol,
                "total_quantity": tracker.total_quantity,
                "filled_quantity": tracker.filled_quantity,
                "remaining_quantity": tracker.remaining_quantity,
                "fill_ratio": tracker.fill_ratio,
                "average_fill_price": tracker.average_fill_price,
                "total_commission": tracker.total_commission,
                "fill_count": len(tracker.fills),
                "is_fully_filled": tracker.is_fully_filled,
                "is_partially_filled": tracker.is_partially_filled,
                "created_at": tracker.created_at.isoformat(),
                "last_fill_at": tracker.last_fill_at.isoformat() if tracker.last_fill_at else None
            }
            
        except Exception as e:
            logger.error(f"Error getting execution status: {e}")
            return None
    
    async def _handle_order_placed(self, event_data: Dict[str, Any]):
        """주문 제출 이벤트 처리"""
        try:
            order_id = event_data.get("order_id")
            symbol = event_data.get("symbol")
            quantity = event_data.get("quantity")
            
            if order_id and symbol and quantity:
                # 새로운 체결 추적기 생성
                async with self._tracker_lock:
                    tracker = ExecutionTracker(
                        order_id=order_id,
                        symbol=symbol,
                        total_quantity=quantity
                    )
                    self._execution_trackers[order_id] = tracker
                
                logger.info(f"Execution tracker created: {order_id} - {symbol} {quantity}")
                
        except Exception as e:
            logger.error(f"Error handling order placed: {e}")
    
    async def _handle_order_executed(self, event_data: Dict[str, Any]):
        """주문 체결 이벤트 처리"""
        try:
            fill_data = event_data.get("fill", {})
            order_id = fill_data.get("order_id")
            
            if not order_id:
                logger.warning("Order ID not found in fill data")
                return
            
            # Fill 객체 복원
            fill = Fill(
                fill_id=fill_data.get("fill_id", ""),
                order_id=order_id,
                symbol=fill_data.get("symbol", ""),
                side=OrderSide(fill_data.get("side", "BUY")),
                quantity=int(fill_data.get("quantity", 0)),
                price=float(fill_data.get("price", 0.0)),
                commission=float(fill_data.get("commission", 0.0)),
                timestamp=datetime.fromisoformat(fill_data.get("timestamp"))
                if fill_data.get("timestamp") else datetime.now(),
                broker_fill_id=fill_data.get("broker_fill_id"),
                metadata=fill_data.get("metadata", {})
            )
            
            # 체결 추적기에 추가
            await self._process_fill(fill)
            
        except Exception as e:
            logger.error(f"Error handling order executed: {e}")
    
    async def _handle_order_cancelled(self, event_data: Dict[str, Any]):
        """주문 취소 이벤트 처리"""
        try:
            order_id = event_data.get("order_id")
            
            if order_id and order_id in self._execution_trackers:
                async with self._tracker_lock:
                    tracker = self._execution_trackers[order_id]
                    
                    # 부분 체결 상태에서 취소된 경우 특별 처리
                    if tracker.is_partially_filled:
                        await self._handle_partial_fill_cancellation(tracker)
                    
                    # 활성 추적기에서 제거
                    del self._execution_trackers[order_id]
                
                logger.info(f"Execution tracker removed for cancelled order: {order_id}")
                
        except Exception as e:
            logger.error(f"Error handling order cancelled: {e}")
    
    async def _process_fill(self, fill: Fill):
        """체결 처리"""
        try:
            async with self._tracker_lock:
                tracker = self._execution_trackers.get(fill.order_id)
                
                if not tracker:
                    logger.warning(f"Execution tracker not found for order: {fill.order_id}")
                    return
                
                # 중복 체결 확인
                if any(f.fill_id == fill.fill_id for f in tracker.fills):
                    logger.warning(f"Duplicate fill detected: {fill.fill_id}")
                    return
                
                # 체결 추가
                tracker.add_fill(fill)
                
                # 통계 업데이트
                self._daily_stats["total_fills"] += 1
                self._daily_stats["total_quantity"] += fill.quantity
                
                # 체결 상태에 따른 처리
                if tracker.is_fully_filled:
                    await self._handle_full_execution(tracker)
                else:
                    await self._handle_partial_execution(tracker, fill)
                
                logger.info(f"Fill processed: {fill.order_id} - {fill.quantity}@{fill.price} "
                          f"({tracker.filled_quantity}/{tracker.total_quantity})")
                
        except Exception as e:
            logger.error(f"Error processing fill: {e}")
    
    async def _handle_full_execution(self, tracker: ExecutionTracker):
        """완전 체결 처리"""
        try:
            # 완전 체결 이벤트 발행
            await self.event_bus.publish("order_fully_executed", {
                "order_id": tracker.order_id,
                "symbol": tracker.symbol,
                "total_quantity": tracker.total_quantity,
                "average_price": tracker.average_fill_price,
                "total_commission": tracker.total_commission,
                "fill_count": len(tracker.fills),
                "execution_time": (tracker.last_fill_at - tracker.created_at).total_seconds(),
                "timestamp": datetime.now().isoformat()
            })
            
            # 통계 업데이트
            self._daily_stats["fully_executed_orders"] += 1
            
            # 활성 추적기에서 제거
            del self._execution_trackers[tracker.order_id]
            
            logger.info(f"Order fully executed: {tracker.order_id} - "
                       f"{tracker.total_quantity}@{tracker.average_fill_price:.2f}")
            
        except Exception as e:
            logger.error(f"Error handling full execution: {e}")
    
    async def _handle_partial_execution(self, tracker: ExecutionTracker, fill: Fill):
        """부분 체결 처리"""
        try:
            # 부분 체결 이벤트 발행
            await self.event_bus.publish("order_partially_executed", {
                "order_id": tracker.order_id,
                "symbol": tracker.symbol,
                "filled_quantity": tracker.filled_quantity,
                "remaining_quantity": tracker.remaining_quantity,
                "fill_ratio": tracker.fill_ratio,
                "latest_fill": {
                    "quantity": fill.quantity,
                    "price": fill.price,
                    "timestamp": fill.timestamp.isoformat()
                },
                "timestamp": datetime.now().isoformat()
            })
            
            # 통계 업데이트
            self._daily_stats["partially_executed_orders"] += 1
            
            logger.info(f"Order partially executed: {tracker.order_id} - "
                       f"{tracker.filled_quantity}/{tracker.total_quantity} ({tracker.fill_ratio:.1%})")
            
        except Exception as e:
            logger.error(f"Error handling partial execution: {e}")
    
    async def _handle_partial_fill_cancellation(self, tracker: ExecutionTracker):
        """부분 체결 후 취소 처리"""
        try:
            # 부분 체결 취소 이벤트 발행
            await self.event_bus.publish("partial_fill_cancelled", {
                "order_id": tracker.order_id,
                "symbol": tracker.symbol,
                "filled_quantity": tracker.filled_quantity,
                "cancelled_quantity": tracker.remaining_quantity,
                "average_fill_price": tracker.average_fill_price,
                "total_commission": tracker.total_commission,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Partial fill cancelled: {tracker.order_id} - "
                       f"Filled: {tracker.filled_quantity}, Cancelled: {tracker.remaining_quantity}")
            
        except Exception as e:
            logger.error(f"Error handling partial fill cancellation: {e}")
    
    async def _monitor_partial_fills(self):
        """부분 체결 모니터링"""
        while True:
            try:
                await asyncio.sleep(60)  # 1분마다 체크
                
                current_time = datetime.now()
                stale_trackers = []
                
                async with self._tracker_lock:
                    for order_id, tracker in self._execution_trackers.items():
                        if tracker.is_partially_filled:
                            time_since_last_fill = current_time - (tracker.last_fill_at or tracker.created_at)
                            
                            if time_since_last_fill.total_seconds() > self.max_partial_fill_time:
                                stale_trackers.append(order_id)
                
                # 오래된 부분 체결 경고
                for order_id in stale_trackers:
                    await self._alert_stale_partial_fill(order_id)
                
            except Exception as e:
                logger.error(f"Error monitoring partial fills: {e}")
                await asyncio.sleep(60)
    
    async def _alert_stale_partial_fill(self, order_id: str):
        """오래된 부분 체결 경고"""
        try:
            tracker = self._execution_trackers.get(order_id)
            if not tracker:
                return
            
            await self.event_bus.publish("stale_partial_fill_alert", {
                "order_id": order_id,
                "symbol": tracker.symbol,
                "filled_quantity": tracker.filled_quantity,
                "remaining_quantity": tracker.remaining_quantity,
                "time_since_last_fill": (datetime.now() - (tracker.last_fill_at or tracker.created_at)).total_seconds(),
                "threshold": self.max_partial_fill_time,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.warning(f"Stale partial fill detected: {order_id} - "
                          f"{tracker.filled_quantity}/{tracker.total_quantity}")
            
        except Exception as e:
            logger.error(f"Error alerting stale partial fill: {e}")
    
    async def _update_daily_stats(self):
        """일일 통계 업데이트"""
        while True:
            try:
                await asyncio.sleep(300)  # 5분마다 업데이트
                
                today = datetime.now().strftime("%Y-%m-%d")
                stats_key = f"{self.stats_key_prefix}:{today}"
                
                # Redis에 통계 저장
                for stat_name, value in self._daily_stats.items():
                    await self.redis_manager.hash_set(stats_key, stat_name, value)
                
                # 24시간 후 만료
                await self.redis_manager.expire_key(stats_key, 24 * 3600)
                
            except Exception as e:
                logger.error(f"Error updating daily stats: {e}")
                await asyncio.sleep(300)
    
    async def _load_execution_trackers(self):
        """Redis에서 추적기들 로드"""
        try:
            pattern = f"{self.execution_key_prefix}:*"
            tracker_keys = await self.redis_manager.scan_keys(pattern)
            
            for key in tracker_keys:
                try:
                    tracker_data = await self.redis_manager.get_hash(key)
                    if tracker_data:
                        order_id = tracker_data["order_id"]
                        tracker = ExecutionTracker(
                            order_id=order_id,
                            symbol=tracker_data["symbol"],
                            total_quantity=int(tracker_data["total_quantity"]),
                            filled_quantity=int(tracker_data["filled_quantity"]),
                            average_fill_price=float(tracker_data["average_fill_price"]),
                            total_commission=float(tracker_data["total_commission"]),
                            created_at=datetime.fromisoformat(tracker_data["created_at"])
                        )
                        
                        if tracker_data["last_fill_at"]:
                            tracker.last_fill_at = datetime.fromisoformat(tracker_data["last_fill_at"])
                        
                        self._execution_trackers[order_id] = tracker
                        
                except Exception as e:
                    logger.error(f"Error loading tracker from {key}: {e}")
            
            logger.info(f"Loaded {len(self._execution_trackers)} execution trackers from Redis")
            
        except Exception as e:
            logger.error(f"Error loading execution trackers: {e}")
    
    async def _save_all_trackers(self):
        """모든 추적기를 Redis에 저장"""
        try:
            for tracker in self._execution_trackers.values():
                tracker_key = f"{self.execution_key_prefix}:{tracker.order_id}"
                tracker_data = {
                    "order_id": tracker.order_id,
                    "symbol": tracker.symbol,
                    "total_quantity": tracker.total_quantity,
                    "filled_quantity": tracker.filled_quantity,
                    "average_fill_price": tracker.average_fill_price,
                    "total_commission": tracker.total_commission,
                    "fill_count": len(tracker.fills),
                    "created_at": tracker.created_at.isoformat(),
                    "last_fill_at": tracker.last_fill_at.isoformat() if tracker.last_fill_at else None,
                    "updated_at": datetime.now().isoformat()
                }
                
                await self.redis_manager.set_hash(tracker_key, tracker_data)
                
        except Exception as e:
            logger.error(f"Error saving all trackers: {e}")
    
    async def get_daily_execution_stats(self) -> Dict[str, Any]:
        """일일 체결 통계"""
        try:
            return dict(self._daily_stats)
            
        except Exception as e:
            logger.error(f"Error getting daily execution stats: {e}")
            return {}
    
    async def get_active_partial_fills(self) -> List[Dict[str, Any]]:
        """현재 부분 체결 목록"""
        try:
            partial_fills = []
            
            for tracker in self._execution_trackers.values():
                if tracker.is_partially_filled:
                    partial_fills.append({
                        "order_id": tracker.order_id,
                        "symbol": tracker.symbol,
                        "filled_quantity": tracker.filled_quantity,
                        "remaining_quantity": tracker.remaining_quantity,
                        "fill_ratio": tracker.fill_ratio,
                        "time_since_last_fill": (datetime.now() - (tracker.last_fill_at or tracker.created_at)).total_seconds()
                    })
            
            return partial_fills
            
        except Exception as e:
            logger.error(f"Error getting active partial fills: {e}")
            return []