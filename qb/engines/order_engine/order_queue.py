"""
주문 큐 (Order Queue) 구현

QB Trading System의 주문 순서 관리 및 동시 주문 처리를 위한 큐 시스템입니다.
우선순위 기반 주문 처리와 Redis 기반 영속성을 제공합니다.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import heapq
from dataclasses import dataclass, field
import json

from .base import BaseOrderQueue, Order, OrderType, OrderSide, OrderStatus
from ...utils.redis_manager import RedisManager

logger = logging.getLogger(__name__)


@dataclass
class PriorityOrder:
    """우선순위 포함 주문 래퍼"""
    priority: int  # 낮을수록 높은 우선순위
    timestamp: datetime
    order: Order
    
    def __lt__(self, other):
        """우선순위 큐를 위한 비교 연산자"""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp


class OrderQueue(BaseOrderQueue):
    """
    주문 큐 관리 시스템
    
    주요 기능:
    1. 우선순위 기반 주문 처리
    2. Redis 기반 영속성
    3. 동시 주문 제한
    4. 주문 중복 방지
    """
    
    def __init__(
        self,
        redis_manager: RedisManager,
        config: Optional[Dict[str, Any]] = None
    ):
        self.redis_manager = redis_manager
        self.config = config or {}
        
        # 설정값
        self.max_queue_size = self.config.get("max_queue_size", 1000)
        self.max_concurrent_orders = self.config.get("max_concurrent_orders", 10)
        self.priority_timeout = self.config.get("priority_timeout", 300)  # 5분
        
        # Redis 키
        self.queue_key = "order_queue:pending"
        self.processing_key = "order_queue:processing"
        self.history_key = "order_queue:history"
        
        # 인메모리 우선순위 큐
        self._priority_queue: List[PriorityOrder] = []
        self._queue_lock = asyncio.Lock()
        self._processing_orders: Dict[str, Order] = {}
        
        # 주문 중복 방지
        self._order_ids: set = set()
        
        logger.info("OrderQueue initialized")
    
    async def initialize(self):
        """큐 초기화 - Redis에서 미처리 주문 로드"""
        try:
            # Redis에서 미처리 주문들 로드
            await self._load_pending_orders_from_redis()
            await self._load_processing_orders_from_redis()
            
            logger.info(f"OrderQueue initialized with {len(self._priority_queue)} pending orders")
            
        except Exception as e:
            logger.error(f"Error initializing OrderQueue: {e}")
            raise
    
    async def add_order(self, order: Order) -> bool:
        """
        주문 큐에 추가
        
        Args:
            order: 추가할 주문
            
        Returns:
            bool: 성공 여부
        """
        try:
            async with self._queue_lock:
                # 중복 주문 확인
                if order.order_id in self._order_ids:
                    logger.warning(f"Duplicate order ID: {order.order_id}")
                    return False
                
                # 큐 크기 제한 확인
                if len(self._priority_queue) >= self.max_queue_size:
                    logger.warning(f"Queue size limit reached: {len(self._priority_queue)} >= {self.max_queue_size}")
                    return False
                
                # 우선순위 계산
                priority = await self._calculate_priority(order)
                
                # 우선순위 주문 생성
                priority_order = PriorityOrder(
                    priority=priority,
                    timestamp=datetime.now(),
                    order=order
                )
                
                # 우선순위 큐에 추가
                heapq.heappush(self._priority_queue, priority_order)
                self._order_ids.add(order.order_id)
                
                # Redis에 저장
                await self._save_order_to_redis(order, "pending")
                
                logger.info(f"Order added to queue: {order.order_id} (priority: {priority})")
                return True
                
        except Exception as e:
            logger.error(f"Error adding order to queue: {e}")
            return False
    
    async def get_next_order(self) -> Optional[Order]:
        """
        다음 처리할 주문 반환
        
        Returns:
            Optional[Order]: 다음 주문 (없으면 None)
        """
        try:
            async with self._queue_lock:
                # 동시 처리 한도 확인
                if len(self._processing_orders) >= self.max_concurrent_orders:
                    return None
                
                # 우선순위 큐에서 다음 주문 가져오기
                while self._priority_queue:
                    priority_order = heapq.heappop(self._priority_queue)
                    order = priority_order.order
                    
                    # 주문 만료 확인
                    if await self._is_order_expired(order):
                        logger.info(f"Order expired, skipping: {order.order_id}")
                        await self._remove_order_from_redis(order.order_id, "pending")
                        self._order_ids.discard(order.order_id)
                        continue
                    
                    # 처리 중 상태로 이동
                    self._processing_orders[order.order_id] = order
                    await self._move_order_to_processing(order)
                    
                    logger.info(f"Next order retrieved: {order.order_id}")
                    return order
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting next order: {e}")
            return None
    
    async def remove_order(self, order_id: str) -> bool:
        """
        주문 큐에서 제거
        
        Args:
            order_id: 제거할 주문 ID
            
        Returns:
            bool: 성공 여부
        """
        try:
            async with self._queue_lock:
                # 처리 중인 주문에서 제거
                if order_id in self._processing_orders:
                    order = self._processing_orders.pop(order_id)
                    await self._move_order_to_history(order)
                    logger.info(f"Order removed from processing: {order_id}")
                    return True
                
                # 대기 중인 주문에서 제거
                if order_id in self._order_ids:
                    # 우선순위 큐에서 제거 (실제로는 만료 체크에서 처리됨)
                    self._order_ids.discard(order_id)
                    await self._remove_order_from_redis(order_id, "pending")
                    logger.info(f"Order removed from pending: {order_id}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error removing order: {e}")
            return False
    
    async def get_pending_orders(self) -> List[Order]:
        """
        대기 중인 주문 목록
        
        Returns:
            List[Order]: 대기 중인 주문들
        """
        try:
            async with self._queue_lock:
                return [po.order for po in self._priority_queue]
                
        except Exception as e:
            logger.error(f"Error getting pending orders: {e}")
            return []
    
    async def get_processing_orders(self) -> List[Order]:
        """
        처리 중인 주문 목록
        
        Returns:
            List[Order]: 처리 중인 주문들
        """
        return list(self._processing_orders.values())
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """
        큐 상태 정보
        
        Returns:
            Dict[str, Any]: 큐 상태
        """
        return {
            "pending_count": len(self._priority_queue),
            "processing_count": len(self._processing_orders),
            "max_queue_size": self.max_queue_size,
            "max_concurrent_orders": self.max_concurrent_orders,
            "queue_utilization": len(self._priority_queue) / self.max_queue_size,
            "processing_utilization": len(self._processing_orders) / self.max_concurrent_orders
        }
    
    async def _calculate_priority(self, order: Order) -> int:
        """
        주문 우선순위 계산
        
        낮은 숫자가 높은 우선순위
        
        Args:
            order: 우선순위를 계산할 주문
            
        Returns:
            int: 우선순위 값
        """
        base_priority = 100
        
        # 주문 타입별 우선순위
        if order.order_type == OrderType.MARKET:
            base_priority -= 20  # 시장가 주문이 높은 우선순위
        elif order.order_type == OrderType.STOP:
            base_priority -= 10  # 스탑 주문이 다음 우선순위
        
        # 주문 방향별 우선순위
        if order.side == OrderSide.SELL:
            base_priority -= 5  # 매도 주문이 매수보다 높은 우선순위
        
        # 전략별 우선순위
        strategy_priorities = self.config.get("strategy_priorities", {})
        if order.strategy_name in strategy_priorities:
            base_priority += strategy_priorities[order.strategy_name]
        
        # 메타데이터에서 우선순위 조정
        if order.metadata and "priority_adjustment" in order.metadata:
            base_priority += order.metadata["priority_adjustment"]
        
        return max(1, base_priority)  # 최소 우선순위 1
    
    async def _is_order_expired(self, order: Order) -> bool:
        """주문 만료 확인"""
        try:
            # DAY 주문은 장 마감시간까지
            if order.time_in_force.value == "DAY":
                # 15:30 이후면 만료 (한국 시장 기준)
                now = datetime.now()
                market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
                if now > market_close:
                    return True
            
            # 우선순위 타임아웃 확인
            if (datetime.now() - order.created_at).total_seconds() > self.priority_timeout:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking order expiry: {e}")
            return False
    
    async def _save_order_to_redis(self, order: Order, queue_type: str):
        """Redis에 주문 저장"""
        try:
            order_data = {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "quantity": order.quantity,
                "price": order.price,
                "stop_price": order.stop_price,
                "time_in_force": order.time_in_force.value,
                "strategy_name": order.strategy_name,
                "status": order.status.value,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
                "metadata": order.metadata
            }
            
            key = f"order_queue:{queue_type}"
            await self.redis_manager.hash_set(key, order.order_id, order_data)
            
        except Exception as e:
            logger.error(f"Error saving order to Redis: {e}")
    
    async def _remove_order_from_redis(self, order_id: str, queue_type: str):
        """Redis에서 주문 제거"""
        try:
            key = f"order_queue:{queue_type}"
            await self.redis_manager.hash_delete(key, order_id)
            
        except Exception as e:
            logger.error(f"Error removing order from Redis: {e}")
    
    async def _move_order_to_processing(self, order: Order):
        """주문을 처리 중 상태로 이동"""
        try:
            # pending에서 제거
            await self._remove_order_from_redis(order.order_id, "pending")
            
            # processing에 추가
            await self._save_order_to_redis(order, "processing")
            
        except Exception as e:
            logger.error(f"Error moving order to processing: {e}")
    
    async def _move_order_to_history(self, order: Order):
        """주문을 히스토리로 이동"""
        try:
            # processing에서 제거
            await self._remove_order_from_redis(order.order_id, "processing")
            
            # history에 추가
            await self._save_order_to_redis(order, "history")
            
            # 히스토리 크기 제한 (최근 1000개만 유지)
            history_key = f"order_queue:history"
            await self.redis_manager.list_trim(history_key, -1000, -1)
            
        except Exception as e:
            logger.error(f"Error moving order to history: {e}")
    
    async def _load_pending_orders_from_redis(self):
        """Redis에서 대기 중인 주문들 로드"""
        try:
            key = f"order_queue:pending"
            order_data_dict = await self.redis_manager.hash_get_all(key)
            
            for order_id, order_data in order_data_dict.items():
                try:
                    order = self._create_order_from_data(order_data)
                    if order and not await self._is_order_expired(order):
                        priority = await self._calculate_priority(order)
                        priority_order = PriorityOrder(
                            priority=priority,
                            timestamp=order.created_at,
                            order=order
                        )
                        heapq.heappush(self._priority_queue, priority_order)
                        self._order_ids.add(order.order_id)
                    else:
                        # 만료된 주문은 제거
                        await self._remove_order_from_redis(order_id, "pending")
                        
                except Exception as e:
                    logger.error(f"Error loading order {order_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error loading pending orders from Redis: {e}")
    
    async def _load_processing_orders_from_redis(self):
        """Redis에서 처리 중인 주문들 로드"""
        try:
            key = f"order_queue:processing"
            order_data_dict = await self.redis_manager.hash_get_all(key)
            
            for order_id, order_data in order_data_dict.items():
                try:
                    order = self._create_order_from_data(order_data)
                    if order:
                        self._processing_orders[order_id] = order
                        
                except Exception as e:
                    logger.error(f"Error loading processing order {order_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error loading processing orders from Redis: {e}")
    
    def _create_order_from_data(self, order_data: Dict[str, Any]) -> Optional[Order]:
        """주문 데이터에서 Order 객체 생성"""
        try:
            from .base import OrderType, OrderSide, OrderStatus, TimeInForce
            
            order = Order(
                symbol=order_data["symbol"],
                side=OrderSide(order_data["side"]),
                order_type=OrderType(order_data["order_type"]),
                quantity=int(order_data["quantity"]),
                price=float(order_data["price"]) if order_data["price"] else None,
                stop_price=float(order_data["stop_price"]) if order_data["stop_price"] else None,
                time_in_force=TimeInForce(order_data["time_in_force"]),
                strategy_name=order_data["strategy_name"],
                order_id=order_data["order_id"],
                status=OrderStatus(order_data["status"]),
                created_at=datetime.fromisoformat(order_data["created_at"]),
                updated_at=datetime.fromisoformat(order_data["updated_at"]),
                metadata=order_data.get("metadata", {})
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error creating order from data: {e}")
            return None
    
    async def cleanup_expired_orders(self):
        """만료된 주문들 정리"""
        try:
            async with self._queue_lock:
                # 우선순위 큐 재구성 (만료된 주문 제거)
                valid_orders = []
                while self._priority_queue:
                    priority_order = heapq.heappop(self._priority_queue)
                    if not await self._is_order_expired(priority_order.order):
                        valid_orders.append(priority_order)
                    else:
                        # 만료된 주문 제거
                        await self._remove_order_from_redis(priority_order.order.order_id, "pending")
                        self._order_ids.discard(priority_order.order.order_id)
                
                # 유효한 주문들로 큐 재구성
                self._priority_queue = valid_orders
                heapq.heapify(self._priority_queue)
                
                logger.info(f"Cleaned up expired orders. Remaining: {len(self._priority_queue)}")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired orders: {e}")