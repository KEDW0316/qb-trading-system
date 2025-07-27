"""
주문 엔진 (Order Engine) 구현

QB Trading System의 핵심 주문 처리 엔진입니다.
이벤트 기반으로 거래 신호를 받아 실제 주문으로 변환하고 실행합니다.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict

from .base import (
    Order, OrderResult, Fill, Position, OrderType, OrderSide, OrderStatus, TimeInForce,
    BaseBrokerClient, BaseOrderQueue, BasePositionManager, BaseCommissionCalculator
)
from ..strategy_engine.base import TradingSignal
from ..event_bus import EnhancedEventBus, EventType, EventFilter
from ..event_bus.adapters import OrderEventPublisher, EngineEventMixin
from ...utils.redis_manager import RedisManager

logger = logging.getLogger(__name__)


class OrderEngine(EngineEventMixin):
    """
    주문 엔진 - 이벤트 기반 주문 처리 시스템
    
    주요 기능:
    1. trading_signal 이벤트 구독 및 주문 생성
    2. 주문 실행 및 상태 관리
    3. 체결 처리 및 포지션 업데이트
    4. 주문 관련 이벤트 발행
    """
    
    def __init__(
        self,
        broker_client: BaseBrokerClient,
        order_queue: BaseOrderQueue,
        position_manager: BasePositionManager,
        commission_calculator: BaseCommissionCalculator,
        event_bus: EnhancedEventBus,
        redis_manager: RedisManager,
        config: Optional[Dict[str, Any]] = None
    ):
        self.broker_client = broker_client
        self.order_queue = order_queue
        self.position_manager = position_manager
        self.commission_calculator = commission_calculator
        self.event_bus = event_bus
        self.redis_manager = redis_manager
        
        # Event Bus 초기화
        self.init_event_bus(event_bus, "OrderEngine")
        
        # 전용 발행자 초기화
        self.order_publisher = OrderEventPublisher(event_bus, "OrderEngine")
        
        # 설정 기본값
        self.config = config or {}
        self.max_order_value = self.config.get("max_order_value", 1_000_000)  # 최대 주문 금액
        self.max_position_count = self.config.get("max_position_count", 10)  # 최대 포지션 수
        self.order_timeout = self.config.get("order_timeout", 300)  # 주문 타임아웃 (초)
        self.enable_partial_fills = self.config.get("enable_partial_fills", True)
        
        # 런타임 상태
        self._running = False
        self._active_orders: Dict[str, Order] = {}
        self._order_history: List[Order] = []
        self._fill_history: List[Fill] = []
        self._processing_lock = asyncio.Lock()
        
        # 이벤트 핸들러
        self._event_handlers: Dict[str, Callable] = {
            EventType.TRADING_SIGNAL.value: self._handle_trading_signal,
            EventType.ORDER_EXECUTED.value: self._handle_order_executed,
            EventType.MARKET_DATA_RECEIVED.value: self._handle_market_data,
        }
        
        logger.info("OrderEngine initialized")
    
    async def start(self):
        """주문 엔진 시작"""
        if self._running:
            logger.warning("OrderEngine is already running")
            return
        
        try:
            # 이벤트 구독
            for event_type, handler in self._event_handlers.items():
                self.event_bus.subscribe(event_type, handler)
            
            # 주문 처리 태스크 시작
            asyncio.create_task(self._process_orders())
            asyncio.create_task(self._monitor_orders())
            
            self._running = True
            logger.info("OrderEngine started successfully")
            
            # 시작 이벤트 발행
            await self.event_bus.publish(EventType.SYSTEM_STATUS.value, {
                "component": "OrderEngine",
                "status": "started",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to start OrderEngine: {e}")
            raise
    
    async def stop(self):
        """주문 엔진 중지"""
        if not self._running:
            return
        
        self._running = False
        
        try:
            # 활성 주문 취소
            await self._cancel_all_active_orders()
            
            # 이벤트 구독 해제
            for event_type, handler in self._event_handlers.items():
                self.event_bus.unsubscribe(event_type, handler)
            
            logger.info("OrderEngine stopped successfully")
            
            # 중지 이벤트 발행
            await self.event_bus.publish(EventType.SYSTEM_STATUS.value, {
                "component": "OrderEngine",
                "status": "stopped",
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error stopping OrderEngine: {e}")
    
    async def _handle_trading_signal(self, event_data: Dict[str, Any]):
        """거래 신호 이벤트 처리"""
        try:
            # TradingSignal 객체 복원
            signal_data = event_data.get("signal", {})
            signal = TradingSignal(
                action=signal_data.get("action"),
                symbol=signal_data.get("symbol"),
                confidence=signal_data.get("confidence"),
                price=signal_data.get("price"),
                quantity=signal_data.get("quantity"),
                reason=signal_data.get("reason"),
                metadata=signal_data.get("metadata", {}),
                timestamp=datetime.fromisoformat(signal_data.get("timestamp"))
                if signal_data.get("timestamp") else datetime.now()
            )
            
            logger.info(f"Processing trading signal: {signal.action} {signal.symbol} @ {signal.price}")
            
            # 신호를 주문으로 변환
            order = await self._signal_to_order(signal)
            if order:
                # 주문 사전 검증
                if await self._validate_order(order):
                    # 주문 큐에 추가
                    await self.order_queue.add_order(order)
                    logger.info(f"Order created and queued: {order.order_id}")
                else:
                    logger.warning(f"Order validation failed for signal: {signal.symbol}")
            
        except Exception as e:
            logger.error(f"Error handling trading signal: {e}")
            await self._publish_error("trading_signal_handling", str(e))
    
    async def _signal_to_order(self, signal: TradingSignal) -> Optional[Order]:
        """거래 신호를 주문으로 변환"""
        try:
            if signal.action == "HOLD":
                return None
            
            # 주문 방향 결정
            side = OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL
            
            # 주문 수량 계산
            quantity = await self._calculate_order_quantity(signal)
            if quantity <= 0:
                logger.warning(f"Invalid order quantity calculated: {quantity}")
                return None
            
            # 주문 타입 및 가격 결정
            order_type, price, stop_price = await self._determine_order_details(signal)
            
            # 주문 생성
            order = Order(
                symbol=signal.symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                time_in_force=TimeInForce.DAY,
                strategy_name=signal.metadata.get("strategy_name") if signal.metadata else None,
                metadata={
                    "signal_confidence": signal.confidence,
                    "signal_reason": signal.reason,
                    "signal_timestamp": signal.timestamp.isoformat(),
                    **(signal.metadata if signal.metadata else {})
                }
            )
            
            return order
            
        except Exception as e:
            logger.error(f"Error converting signal to order: {e}")
            return None
    
    async def _calculate_order_quantity(self, signal: TradingSignal) -> int:
        """주문 수량 계산"""
        try:
            # 신호에 수량이 명시된 경우
            if signal.quantity and signal.quantity > 0:
                return signal.quantity
            
            # 계좌 잔고 기준 수량 계산
            account_balance = await self.broker_client.get_account_balance()
            available_cash = account_balance.get("available_cash", 0)
            
            # 현재 포지션 확인
            current_position = await self.position_manager.get_position(signal.symbol)
            
            # 기본 주문 금액 (계좌의 10%)
            base_order_value = min(available_cash * 0.1, self.max_order_value)
            
            # 신뢰도 기반 조정
            confidence_multiplier = signal.confidence * 1.5  # 0.0 ~ 1.5
            adjusted_order_value = base_order_value * confidence_multiplier
            
            # 가격 기준 수량 계산
            price = signal.price or await self._get_current_price(signal.symbol)
            if not price or price <= 0:
                logger.warning(f"Invalid price for quantity calculation: {price}")
                return 0
            
            quantity = int(adjusted_order_value / price)
            
            # 최소/최대 수량 제한
            min_quantity = self.config.get("min_order_quantity", 1)
            max_quantity = self.config.get("max_order_quantity", 1000)
            
            return max(min_quantity, min(quantity, max_quantity))
            
        except Exception as e:
            logger.error(f"Error calculating order quantity: {e}")
            return 0
    
    async def _determine_order_details(self, signal: TradingSignal) -> tuple[OrderType, Optional[float], Optional[float]]:
        """주문 타입 및 가격 결정"""
        try:
            # 기본적으로 시장가 주문
            order_type = OrderType.MARKET
            price = None
            stop_price = None
            
            # 신호에 가격이 명시된 경우 지정가 주문
            if signal.price:
                order_type = OrderType.LIMIT
                price = signal.price
            
            # 메타데이터에서 주문 타입 확인
            if signal.metadata:
                order_type_str = signal.metadata.get("order_type", "MARKET")
                try:
                    order_type = OrderType(order_type_str.upper())
                except ValueError:
                    logger.warning(f"Invalid order type in metadata: {order_type_str}")
                
                # 스탑 가격 설정
                if "stop_price" in signal.metadata:
                    stop_price = float(signal.metadata["stop_price"])
            
            return order_type, price, stop_price
            
        except Exception as e:
            logger.error(f"Error determining order details: {e}")
            return OrderType.MARKET, None, None
    
    async def _validate_order(self, order: Order) -> bool:
        """주문 사전 검증"""
        try:
            # 기본 유효성 검증
            if order.quantity <= 0:
                logger.warning(f"Invalid order quantity: {order.quantity}")
                return False
            
            # 최대 주문 금액 검증
            if order.price:
                order_value = order.quantity * order.price
                if order_value > self.max_order_value:
                    logger.warning(f"Order value exceeds limit: {order_value} > {self.max_order_value}")
                    return False
            
            # 최대 포지션 수 검증
            current_positions = await self.position_manager.get_all_positions()
            active_symbols = {pos.symbol for pos in current_positions if not pos.is_flat}
            
            if order.symbol not in active_symbols and len(active_symbols) >= self.max_position_count:
                logger.warning(f"Maximum position count reached: {len(active_symbols)} >= {self.max_position_count}")
                return False
            
            # 계좌 잔고 검증
            account_balance = await self.broker_client.get_account_balance()
            available_cash = account_balance.get("available_cash", 0)
            
            if order.side == OrderSide.BUY:
                required_cash = order.quantity * (order.price or await self._get_current_price(order.symbol))
                if required_cash > available_cash:
                    logger.warning(f"Insufficient cash: {required_cash} > {available_cash}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating order: {e}")
            return False
    
    async def _process_orders(self):
        """주문 처리 루프"""
        while self._running:
            try:
                async with self._processing_lock:
                    # 다음 주문 가져오기
                    order = await self.order_queue.get_next_order()
                    if order:
                        await self._execute_order(order)
                
                # 짧은 대기
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in order processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _execute_order(self, order: Order):
        """주문 실행"""
        try:
            logger.info(f"Executing order: {order.order_id} - {order.side.value} {order.quantity} {order.symbol}")
            
            # 주문 상태 업데이트
            order.update_status(OrderStatus.SUBMITTED)
            self._active_orders[order.order_id] = order
            
            # 브로커에 주문 제출
            result = await self.broker_client.place_order(order)
            
            if result.success:
                # 성공 시 주문 이벤트 발행
                await self.event_bus.publish(EventType.ORDER_PLACED.value, {
                    "order_id": order.order_id,
                    "broker_order_id": result.broker_order_id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "quantity": order.quantity,
                    "price": order.price,
                    "timestamp": datetime.now().isoformat(),
                    "strategy_name": order.strategy_name
                })
                
                logger.info(f"Order placed successfully: {order.order_id}")
                
            else:
                # 실패 시 처리
                order.update_status(OrderStatus.FAILED)
                self._active_orders.pop(order.order_id, None)
                self._order_history.append(order)
                
                await self.event_bus.publish(EventType.ORDER_FAILED.value, {
                    "order_id": order.order_id,
                    "symbol": order.symbol,
                    "error_message": result.message,
                    "error_code": result.error_code,
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.error(f"Order placement failed: {order.order_id} - {result.message}")
            
        except Exception as e:
            logger.error(f"Error executing order {order.order_id}: {e}")
            order.update_status(OrderStatus.FAILED)
            self._active_orders.pop(order.order_id, None)
            await self._publish_error("order_execution", str(e), {"order_id": order.order_id})
    
    async def _handle_order_executed(self, event_data: Dict[str, Any]):
        """주문 체결 이벤트 처리"""
        try:
            fill_data = event_data.get("fill", {})
            order_id = fill_data.get("order_id")
            
            if not order_id or order_id not in self._active_orders:
                logger.warning(f"Received fill for unknown order: {order_id}")
                return
            
            order = self._active_orders[order_id]
            
            # Fill 객체 생성
            fill = Fill(
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=fill_data.get("quantity", 0),
                price=fill_data.get("price", 0.0),
                commission=fill_data.get("commission", 0.0),
                timestamp=datetime.fromisoformat(fill_data.get("timestamp"))
                if fill_data.get("timestamp") else datetime.now(),
                broker_fill_id=fill_data.get("broker_fill_id"),
                metadata=fill_data.get("metadata", {})
            )
            
            # 수수료 계산 (브로커에서 제공하지 않는 경우)
            if fill.commission == 0.0:
                fill.commission = self.commission_calculator.calculate_commission(
                    order, fill.price, fill.quantity
                )
            
            # 주문에 체결 정보 추가
            order.add_fill(fill.quantity, fill.price, fill.commission)
            
            # 포지션 업데이트
            await self.position_manager.update_position(order.symbol, fill)
            
            # Fill 히스토리에 추가
            self._fill_history.append(fill)
            
            # 주문 완전 체결 시 처리
            if order.is_filled:
                self._active_orders.pop(order_id, None)
                self._order_history.append(order)
                
                logger.info(f"Order fully filled: {order_id} - {order.filled_quantity}/{order.quantity}")
            else:
                logger.info(f"Order partially filled: {order_id} - {order.filled_quantity}/{order.quantity}")
            
            # Redis에 체결 정보 저장
            await self._save_fill_to_redis(fill)
            
        except Exception as e:
            logger.error(f"Error handling order executed event: {e}")
    
    async def _handle_market_data(self, event_data: Dict[str, Any]):
        """시장 데이터 이벤트 처리 - 포지션 시장가 업데이트"""
        try:
            market_data = event_data.get("market_data", {})
            symbol = market_data.get("symbol")
            close_price = market_data.get("close")
            
            if symbol and close_price:
                position = await self.position_manager.get_position(symbol)
                if position and not position.is_flat:
                    position.update_market_price(close_price)
                    
                    # Redis에 포지션 정보 업데이트
                    await self._save_position_to_redis(position)
            
        except Exception as e:
            logger.error(f"Error handling market data event: {e}")
    
    async def _monitor_orders(self):
        """주문 모니터링 루프 - 타임아웃 및 상태 확인"""
        while self._running:
            try:
                current_time = datetime.now()
                timeout_threshold = current_time - timedelta(seconds=self.order_timeout)
                
                expired_orders = []
                for order_id, order in self._active_orders.items():
                    if order.created_at < timeout_threshold:
                        expired_orders.append(order_id)
                
                # 만료된 주문 취소
                for order_id in expired_orders:
                    await self._cancel_order(order_id, "timeout")
                
                # 30초마다 실행
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in order monitoring loop: {e}")
                await asyncio.sleep(30)
    
    async def _cancel_order(self, order_id: str, reason: str = "manual"):
        """주문 취소"""
        try:
            if order_id not in self._active_orders:
                logger.warning(f"Cannot cancel order - not found: {order_id}")
                return False
            
            order = self._active_orders[order_id]
            
            # 브로커에 취소 요청
            result = await self.broker_client.cancel_order(order_id)
            
            if result.success:
                order.update_status(OrderStatus.CANCELLED)
                self._active_orders.pop(order_id, None)
                self._order_history.append(order)
                
                await self.event_bus.publish(EventType.ORDER_CANCELLED.value, {
                    "order_id": order_id,
                    "symbol": order.symbol,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Order cancelled: {order_id} - {reason}")
                return True
            else:
                logger.error(f"Failed to cancel order: {order_id} - {result.message}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def _cancel_all_active_orders(self):
        """모든 활성 주문 취소"""
        active_order_ids = list(self._active_orders.keys())
        for order_id in active_order_ids:
            await self._cancel_order(order_id, "shutdown")
    
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """현재 가격 조회"""
        try:
            # Redis에서 현재 가격 조회
            market_data_key = f"market_data:{symbol}"
            market_data = await self.redis_manager.get_hash(market_data_key)
            
            if market_data and "close" in market_data:
                return float(market_data["close"])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    async def _save_fill_to_redis(self, fill: Fill):
        """Fill 정보를 Redis에 저장"""
        try:
            fill_key = f"fills:{fill.symbol}:{fill.timestamp.strftime('%Y-%m-%d')}"
            fill_data = {
                "fill_id": fill.fill_id,
                "order_id": fill.order_id,
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": fill.quantity,
                "price": fill.price,
                "commission": fill.commission,
                "timestamp": fill.timestamp.isoformat()
            }
            
            await self.redis_manager.list_push(fill_key, fill_data)
            
            # 일일 통계 업데이트
            stats_key = f"daily_stats:{fill.timestamp.strftime('%Y-%m-%d')}"
            await self.redis_manager.hash_increment(stats_key, "total_fills", 1)
            await self.redis_manager.hash_increment(stats_key, "total_volume", fill.quantity)
            
        except Exception as e:
            logger.error(f"Error saving fill to Redis: {e}")
    
    async def _save_position_to_redis(self, position: Position):
        """포지션 정보를 Redis에 저장"""
        try:
            position_key = f"positions:{position.symbol}"
            position_data = {
                "symbol": position.symbol,
                "quantity": position.quantity,
                "average_price": position.average_price,
                "market_price": position.market_price,
                "unrealized_pnl": position.unrealized_pnl,
                "realized_pnl": position.realized_pnl,
                "total_commission": position.total_commission,
                "updated_at": position.updated_at.isoformat()
            }
            
            await self.redis_manager.set_hash(position_key, position_data)
            
        except Exception as e:
            logger.error(f"Error saving position to Redis: {e}")
    
    async def _publish_error(self, error_type: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """에러 이벤트 발행"""
        try:
            await self.event_bus.publish(EventType.ERROR_OCCURRED.value, {
                "component": "OrderEngine",
                "error_type": error_type,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            })
        except Exception as e:
            logger.error(f"Error publishing error event: {e}")
    
    # Public API Methods
    
    async def get_active_orders(self) -> List[Order]:
        """활성 주문 목록 조회"""
        return list(self._active_orders.values())
    
    async def get_order_history(self, limit: int = 100) -> List[Order]:
        """주문 히스토리 조회"""
        return self._order_history[-limit:]
    
    async def get_fill_history(self, limit: int = 100) -> List[Fill]:
        """체결 히스토리 조회"""
        return self._fill_history[-limit:]
    
    async def get_engine_status(self) -> Dict[str, Any]:
        """엔진 상태 조회"""
        return {
            "running": self._running,
            "active_orders_count": len(self._active_orders),
            "total_orders_processed": len(self._order_history),
            "total_fills": len(self._fill_history),
            "config": self.config,
            "uptime": datetime.now().isoformat() if self._running else None
        }
    
    async def cancel_order_by_id(self, order_id: str) -> bool:
        """특정 주문 취소 (외부 API)"""
        return await self._cancel_order(order_id, "manual")
    
    async def cancel_all_orders_for_symbol(self, symbol: str) -> int:
        """특정 심볼의 모든 주문 취소"""
        cancelled_count = 0
        active_orders = [order for order in self._active_orders.values() if order.symbol == symbol]
        
        for order in active_orders:
            if await self._cancel_order(order.order_id, f"symbol_cancel_{symbol}"):
                cancelled_count += 1
        
        return cancelled_count