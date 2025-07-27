"""
주문 엔진 이벤트 핸들러 (Order Engine Event Handler)

QB Trading System의 주문 관련 이벤트 구독 및 발행을 담당합니다.
체결 통지, 주문 상태 변경 등의 이벤트를 처리합니다.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import json

from .base import Order, Fill, OrderStatus, OrderSide
from ...utils.event_bus import EventBus, EventType
from ...utils.redis_manager import RedisManager

logger = logging.getLogger(__name__)


class OrderEventHandler:
    """
    주문 이벤트 핸들러
    
    주요 기능:
    1. KIS API 체결 통지 수신 및 처리
    2. 주문 상태 변경 이벤트 발행
    3. 포지션 업데이트 이벤트 처리
    4. 실시간 체결 모니터링
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        redis_manager: RedisManager,
        config: Optional[Dict[str, Any]] = None
    ):
        self.event_bus = event_bus
        self.redis_manager = redis_manager
        self.config = config or {}
        
        # 이벤트 핸들러 등록
        self._event_handlers: Dict[str, Callable] = {
            "kis_fill_notification": self._handle_kis_fill_notification,
            "kis_order_status_change": self._handle_kis_order_status_change,
            "market_data_received": self._handle_market_data_for_positions,
        }
        
        # 체결 통지 채널
        self.fill_notification_channel = "kis_fill_notifications"
        self.order_status_channel = "kis_order_status"
        
        # 처리 통계
        self._processed_events = 0
        self._failed_events = 0
        
        logger.info("OrderEventHandler initialized")
    
    async def start(self):
        """이벤트 핸들러 시작"""
        try:
            # 이벤트 구독
            for event_type, handler in self._event_handlers.items():
                await self.event_bus.subscribe(event_type, handler)
            
            # Redis Pub/Sub 구독 시작
            asyncio.create_task(self._subscribe_redis_notifications())
            
            logger.info("OrderEventHandler started")
            
        except Exception as e:
            logger.error(f"Error starting OrderEventHandler: {e}")
            raise
    
    async def stop(self):
        """이벤트 핸들러 중지"""
        try:
            # 이벤트 구독 해제
            for event_type in self._event_handlers.keys():
                await self.event_bus.unsubscribe(event_type)
            
            logger.info("OrderEventHandler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping OrderEventHandler: {e}")
    
    async def _subscribe_redis_notifications(self):
        """Redis Pub/Sub을 통한 체결 통지 구독"""
        try:
            pubsub = await self.redis_manager.get_pubsub()
            await pubsub.subscribe(self.fill_notification_channel, self.order_status_channel)
            
            logger.info("Subscribed to Redis notifications")
            
            while True:
                try:
                    message = await pubsub.get_message(timeout=1.0)
                    if message and message['type'] == 'message':
                        await self._process_redis_message(message)
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error processing Redis message: {e}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"Error in Redis subscription: {e}")
    
    async def _process_redis_message(self, message: Dict[str, Any]):
        """Redis 메시지 처리"""
        try:
            channel = message['channel'].decode('utf-8')
            data = json.loads(message['data'].decode('utf-8'))
            
            if channel == self.fill_notification_channel:
                await self._handle_fill_notification(data)
            elif channel == self.order_status_channel:
                await self._handle_order_status_notification(data)
            
            self._processed_events += 1
            
        except Exception as e:
            logger.error(f"Error processing Redis message: {e}")
            self._failed_events += 1
    
    async def _handle_fill_notification(self, notification_data: Dict[str, Any]):
        """체결 통지 처리"""
        try:
            # KIS API 체결 통지 데이터 파싱
            broker_order_id = notification_data.get("odno", "")  # 주문번호
            symbol = notification_data.get("pdno", "")  # 종목코드
            fill_quantity = int(notification_data.get("cntg_qty", "0"))  # 체결수량
            fill_price = float(notification_data.get("cntg_unpr", "0"))  # 체결단가
            fill_time = notification_data.get("cntg_tmrd", "")  # 체결시각
            
            # 매매구분 (1:매도, 2:매수)
            trade_type = notification_data.get("sll_buy_dvsn_cd", "")
            side = OrderSide.SELL if trade_type == "1" else OrderSide.BUY
            
            # Fill 객체 생성
            fill = Fill(
                order_id="",  # 내부 주문 ID는 별도 매핑 필요
                symbol=symbol,
                side=side,
                quantity=fill_quantity,
                price=fill_price,
                commission=0.0,  # 별도 계산 필요
                timestamp=self._parse_kis_time(fill_time),
                broker_fill_id=notification_data.get("cntg_sno", ""),  # 체결일련번호
                metadata={
                    "broker_order_id": broker_order_id,
                    "raw_notification": notification_data
                }
            )
            
            # 주문 체결 이벤트 발행
            await self.event_bus.publish(EventType.ORDER_EXECUTED.value, {
                "fill": {
                    "fill_id": fill.fill_id,
                    "order_id": fill.order_id,
                    "symbol": fill.symbol,
                    "side": fill.side.value,
                    "quantity": fill.quantity,
                    "price": fill.price,
                    "commission": fill.commission,
                    "timestamp": fill.timestamp.isoformat(),
                    "broker_fill_id": fill.broker_fill_id,
                    "metadata": fill.metadata
                },
                "notification_time": datetime.now().isoformat()
            })
            
            logger.info(f"Fill notification processed: {symbol} {side.value} {fill_quantity}@{fill_price}")
            
        except Exception as e:
            logger.error(f"Error handling fill notification: {e}")
    
    async def _handle_order_status_notification(self, notification_data: Dict[str, Any]):
        """주문 상태 변경 통지 처리"""
        try:
            broker_order_id = notification_data.get("odno", "")
            symbol = notification_data.get("pdno", "")
            order_status = notification_data.get("ord_stts", "")  # 주문상태
            
            # KIS 주문 상태를 내부 상태로 매핑
            mapped_status = self._map_kis_order_status(order_status)
            
            # 주문 상태 변경 이벤트 발행
            await self.event_bus.publish("order_status_changed", {
                "broker_order_id": broker_order_id,
                "symbol": symbol,
                "new_status": mapped_status.value if mapped_status else "UNKNOWN",
                "kis_status": order_status,
                "timestamp": datetime.now().isoformat(),
                "raw_notification": notification_data
            })
            
            logger.info(f"Order status notification processed: {broker_order_id} -> {mapped_status}")
            
        except Exception as e:
            logger.error(f"Error handling order status notification: {e}")
    
    async def _handle_kis_fill_notification(self, event_data: Dict[str, Any]):
        """KIS 체결 통지 이벤트 처리"""
        # 기존 _handle_fill_notification과 동일한 로직
        await self._handle_fill_notification(event_data)
    
    async def _handle_kis_order_status_change(self, event_data: Dict[str, Any]):
        """KIS 주문 상태 변경 이벤트 처리"""
        # 기존 _handle_order_status_notification과 동일한 로직
        await self._handle_order_status_notification(event_data)
    
    async def _handle_market_data_for_positions(self, event_data: Dict[str, Any]):
        """포지션 업데이트를 위한 시장 데이터 처리"""
        try:
            market_data = event_data.get("market_data", {})
            symbol = market_data.get("symbol")
            close_price = market_data.get("close")
            
            if symbol and close_price:
                # 포지션 시장가 업데이트 이벤트 발행
                await self.event_bus.publish("position_market_price_update", {
                    "symbol": symbol,
                    "market_price": close_price,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling market data for positions: {e}")
    
    def _parse_kis_time(self, kis_time: str) -> datetime:
        """KIS 시간 형식을 datetime으로 변환"""
        try:
            if len(kis_time) == 6:  # HHMMSS
                now = datetime.now()
                hour = int(kis_time[:2])
                minute = int(kis_time[2:4])
                second = int(kis_time[4:6])
                return now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            else:
                return datetime.now()
                
        except Exception as e:
            logger.error(f"Error parsing KIS time: {e}")
            return datetime.now()
    
    def _map_kis_order_status(self, kis_status: str) -> Optional[OrderStatus]:
        """KIS 주문 상태를 내부 상태로 매핑"""
        try:
            status_mapping = {
                "01": OrderStatus.SUBMITTED,    # 주문접수
                "02": OrderStatus.FILLED,       # 전량체결
                "03": OrderStatus.PARTIAL_FILLED, # 일부체결
                "04": OrderStatus.CANCELLED,    # 주문취소
                "05": OrderStatus.REJECTED,     # 주문거부
                "06": OrderStatus.PENDING,      # 접수대기
            }
            
            return status_mapping.get(kis_status)
            
        except Exception as e:
            logger.error(f"Error mapping KIS order status: {e}")
            return None
    
    async def publish_order_placed(self, order: Order, broker_order_id: str):
        """주문 제출 이벤트 발행"""
        try:
            await self.event_bus.publish(EventType.ORDER_PLACED.value, {
                "order_id": order.order_id,
                "broker_order_id": broker_order_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "quantity": order.quantity,
                "price": order.price,
                "strategy_name": order.strategy_name,
                "timestamp": datetime.now().isoformat(),
                "metadata": order.metadata
            })
            
        except Exception as e:
            logger.error(f"Error publishing order placed event: {e}")
    
    async def publish_order_failed(self, order: Order, error_message: str, error_code: str = ""):
        """주문 실패 이벤트 발행"""
        try:
            await self.event_bus.publish(EventType.ORDER_FAILED.value, {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "error_message": error_message,
                "error_code": error_code,
                "timestamp": datetime.now().isoformat(),
                "order_data": {
                    "quantity": order.quantity,
                    "price": order.price,
                    "strategy_name": order.strategy_name
                }
            })
            
        except Exception as e:
            logger.error(f"Error publishing order failed event: {e}")
    
    async def publish_order_cancelled(self, order_id: str, symbol: str, reason: str = ""):
        """주문 취소 이벤트 발행"""
        try:
            await self.event_bus.publish(EventType.ORDER_CANCELLED.value, {
                "order_id": order_id,
                "symbol": symbol,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error publishing order cancelled event: {e}")
    
    async def publish_position_updated(self, symbol: str, position_data: Dict[str, Any]):
        """포지션 업데이트 이벤트 발행"""
        try:
            await self.event_bus.publish("position_updated", {
                "symbol": symbol,
                "position": position_data,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error publishing position updated event: {e}")
    
    async def get_event_stats(self) -> Dict[str, Any]:
        """이벤트 처리 통계"""
        return {
            "processed_events": self._processed_events,
            "failed_events": self._failed_events,
            "success_rate": self._processed_events / (self._processed_events + self._failed_events) 
                          if (self._processed_events + self._failed_events) > 0 else 1.0,
            "active_subscriptions": len(self._event_handlers)
        }


class FillMonitor:
    """
    체결 모니터링 시스템
    
    실시간으로 체결 정보를 모니터링하고 이상 상황을 감지합니다.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        redis_manager: RedisManager,
        config: Optional[Dict[str, Any]] = None
    ):
        self.event_bus = event_bus
        self.redis_manager = redis_manager
        self.config = config or {}
        
        # 모니터링 설정
        self.max_fill_delay = self.config.get("max_fill_delay", 30)  # 최대 체결 지연 시간 (초)
        self.unusual_price_threshold = self.config.get("unusual_price_threshold", 0.05)  # 5% 가격 이상
        
        # 체결 추적
        self._pending_fills: Dict[str, datetime] = {}
        self._recent_fills: List[Dict[str, Any]] = []
        
        logger.info("FillMonitor initialized")
    
    async def start(self):
        """체결 모니터 시작"""
        try:
            # 체결 관련 이벤트 구독
            await self.event_bus.subscribe(EventType.ORDER_EXECUTED.value, self._monitor_fill)
            await self.event_bus.subscribe(EventType.ORDER_PLACED.value, self._track_pending_order)
            
            # 주기적 체크 태스크 시작
            asyncio.create_task(self._periodic_checks())
            
            logger.info("FillMonitor started")
            
        except Exception as e:
            logger.error(f"Error starting FillMonitor: {e}")
            raise
    
    async def _monitor_fill(self, event_data: Dict[str, Any]):
        """체결 모니터링"""
        try:
            fill_data = event_data.get("fill", {})
            order_id = fill_data.get("order_id")
            symbol = fill_data.get("symbol")
            price = fill_data.get("price")
            quantity = fill_data.get("quantity")
            
            # 대기 중인 주문에서 제거
            if order_id in self._pending_fills:
                fill_delay = (datetime.now() - self._pending_fills[order_id]).total_seconds()
                del self._pending_fills[order_id]
                
                # 체결 지연 경고
                if fill_delay > self.max_fill_delay:
                    await self._alert_slow_fill(order_id, symbol, fill_delay)
            
            # 가격 이상 감지
            await self._check_unusual_price(symbol, price)
            
            # 최근 체결 기록
            self._recent_fills.append({
                "order_id": order_id,
                "symbol": symbol,
                "price": price,
                "quantity": quantity,
                "timestamp": datetime.now()
            })
            
            # 최근 체결 기록 크기 제한 (최근 1000개)
            if len(self._recent_fills) > 1000:
                self._recent_fills = self._recent_fills[-1000:]
            
        except Exception as e:
            logger.error(f"Error monitoring fill: {e}")
    
    async def _track_pending_order(self, event_data: Dict[str, Any]):
        """대기 중인 주문 추적"""
        try:
            order_id = event_data.get("order_id")
            if order_id:
                self._pending_fills[order_id] = datetime.now()
                
        except Exception as e:
            logger.error(f"Error tracking pending order: {e}")
    
    async def _periodic_checks(self):
        """주기적 체크"""
        while True:
            try:
                await self._check_delayed_fills()
                await asyncio.sleep(30)  # 30초마다 체크
                
            except Exception as e:
                logger.error(f"Error in periodic checks: {e}")
                await asyncio.sleep(30)
    
    async def _check_delayed_fills(self):
        """지연된 체결 체크"""
        try:
            now = datetime.now()
            delayed_orders = []
            
            for order_id, submit_time in self._pending_fills.items():
                delay = (now - submit_time).total_seconds()
                if delay > self.max_fill_delay:
                    delayed_orders.append((order_id, delay))
            
            for order_id, delay in delayed_orders:
                await self._alert_slow_fill(order_id, "UNKNOWN", delay)
                
        except Exception as e:
            logger.error(f"Error checking delayed fills: {e}")
    
    async def _check_unusual_price(self, symbol: str, fill_price: float):
        """비정상적인 가격 체크"""
        try:
            # 현재 시장 가격 조회
            market_data_key = f"market_data:{symbol}"
            market_data = await self.redis_manager.get_hash(market_data_key)
            
            if market_data and "close" in market_data:
                market_price = float(market_data["close"])
                price_diff = abs(fill_price - market_price) / market_price
                
                if price_diff > self.unusual_price_threshold:
                    await self._alert_unusual_price(symbol, fill_price, market_price, price_diff)
                    
        except Exception as e:
            logger.error(f"Error checking unusual price: {e}")
    
    async def _alert_slow_fill(self, order_id: str, symbol: str, delay: float):
        """체결 지연 경고"""
        try:
            await self.event_bus.publish("fill_delay_alert", {
                "alert_type": "SLOW_FILL",
                "order_id": order_id,
                "symbol": symbol,
                "delay_seconds": delay,
                "threshold": self.max_fill_delay,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.warning(f"Slow fill detected: {order_id} ({symbol}) - {delay:.1f}s delay")
            
        except Exception as e:
            logger.error(f"Error alerting slow fill: {e}")
    
    async def _alert_unusual_price(self, symbol: str, fill_price: float, market_price: float, diff_ratio: float):
        """비정상적인 가격 경고"""
        try:
            await self.event_bus.publish("unusual_price_alert", {
                "alert_type": "UNUSUAL_PRICE",
                "symbol": symbol,
                "fill_price": fill_price,
                "market_price": market_price,
                "difference_ratio": diff_ratio,
                "threshold": self.unusual_price_threshold,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.warning(f"Unusual price detected: {symbol} - Fill: {fill_price}, Market: {market_price} ({diff_ratio:.2%} diff)")
            
        except Exception as e:
            logger.error(f"Error alerting unusual price: {e}")
    
    async def get_monitor_stats(self) -> Dict[str, Any]:
        """모니터링 통계"""
        return {
            "pending_orders": len(self._pending_fills),
            "recent_fills_count": len(self._recent_fills),
            "average_fill_delay": await self._calculate_average_fill_delay(),
            "unusual_price_alerts_today": await self._count_todays_alerts("unusual_price_alert"),
            "slow_fill_alerts_today": await self._count_todays_alerts("fill_delay_alert")
        }
    
    async def _calculate_average_fill_delay(self) -> float:
        """평균 체결 지연 시간 계산"""
        try:
            # 최근 체결들의 평균 지연 시간 계산 (실제 구현에서는 더 정확한 추적 필요)
            return 2.5  # 임시값
            
        except Exception as e:
            logger.error(f"Error calculating average fill delay: {e}")
            return 0.0
    
    async def _count_todays_alerts(self, alert_type: str) -> int:
        """오늘의 경고 수 계산"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            alert_key = f"alerts:{alert_type}:{today}"
            count = await self.redis_manager.get_data(alert_key)
            return int(count) if count else 0
            
        except Exception as e:
            logger.error(f"Error counting today's alerts: {e}")
            return 0