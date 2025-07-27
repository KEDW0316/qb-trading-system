"""
Auto Stop Loss & Take Profit Manager

자동 손절/익절 관리 시스템
실시간 포지션 모니터링을 통해 손절/익절 조건 확인 및 자동 주문 실행
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StopType(Enum):
    """스탑 타입"""
    FIXED_STOP_LOSS = "fixed_stop_loss"       # 고정 손절
    TRAILING_STOP = "trailing_stop"           # 트레일링 스탑
    FIXED_TAKE_PROFIT = "fixed_take_profit"   # 고정 익절
    BREAKEVEN_STOP = "breakeven_stop"         # 본전 보장 스탑


@dataclass
class StopOrder:
    """스탑 주문 정보"""
    symbol: str
    stop_type: StopType
    trigger_price: Decimal
    quantity: int
    side: str  # 'BUY' or 'SELL'
    original_entry_price: Decimal
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Position:
    """포지션 정보 (간소화된 버전)"""
    symbol: str
    quantity: int
    average_price: Decimal
    current_price: Decimal
    side: str  # 'LONG' or 'SHORT'
    unrealized_pnl: Decimal
    entry_time: datetime
    updated_at: datetime


class AutoStopLossManager:
    """
    자동 손절/익절 관리자
    
    주요 기능:
    1. 실시간 포지션 모니터링
    2. 고정 손절/익절 조건 체크
    3. 트레일링 스탑 관리
    4. 자동 주문 실행
    """
    
    def __init__(self, risk_engine):
        self.risk_engine = risk_engine
        self.db_manager = risk_engine.db_manager
        self.redis_manager = risk_engine.redis_manager
        self.event_bus = risk_engine.event_bus
        self.config = risk_engine.config
        
        # 트레일링 스탑 추적
        self._trailing_stops: Dict[str, StopOrder] = {}
        self._highest_prices: Dict[str, Decimal] = {}  # 매수 포지션의 최고가
        self._lowest_prices: Dict[str, Decimal] = {}   # 매도 포지션의 최저가
        
        logger.info("AutoStopLossManager initialized")
    
    async def check_positions(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """
        포지션 손절/익절 조건 확인 및 자동 주문 실행
        
        Args:
            symbol: 종목 코드
            current_price: 현재 가격
            
        Returns:
            Dict: 실행된 액션 정보
        """
        try:
            current_price_decimal = Decimal(str(current_price))
            
            # 포지션 정보 조회
            position = await self._get_position(symbol)
            if not position or position.quantity == 0:
                return None
            
            logger.debug(f"Checking stop conditions for {symbol}: pos={position.quantity}, price={current_price}")
            
            # 1. 고정 손절 체크
            stop_loss_action = await self._check_fixed_stop_loss(position, current_price_decimal)
            if stop_loss_action:
                return stop_loss_action
            
            # 2. 고정 익절 체크
            take_profit_action = await self._check_fixed_take_profit(position, current_price_decimal)
            if take_profit_action:
                return take_profit_action
            
            # 3. 트레일링 스탑 업데이트 및 체크
            trailing_action = await self._update_and_check_trailing_stop(position, current_price_decimal)
            if trailing_action:
                return trailing_action
            
            # 4. 본전 보장 스탑 체크
            breakeven_action = await self._check_breakeven_stop(position, current_price_decimal)
            if breakeven_action:
                return breakeven_action
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking positions for {symbol}: {e}")
            return None
    
    async def set_stop_loss(
        self,
        symbol: str,
        stop_price: float,
        stop_type: StopType = StopType.FIXED_STOP_LOSS
    ) -> bool:
        """
        손절 주문 설정
        
        Args:
            symbol: 종목 코드
            stop_price: 손절 가격
            stop_type: 손절 타입
            
        Returns:
            bool: 설정 성공 여부
        """
        try:
            position = await self._get_position(symbol)
            if not position:
                logger.warning(f"No position found for {symbol}")
                return False
            
            stop_order = StopOrder(
                symbol=symbol,
                stop_type=stop_type,
                trigger_price=Decimal(str(stop_price)),
                quantity=abs(position.quantity),
                side='SELL' if position.quantity > 0 else 'BUY',
                original_entry_price=position.average_price,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Redis에 저장
            await self._save_stop_order(stop_order)
            
            # 트레일링 스탑인 경우 추적 시작
            if stop_type == StopType.TRAILING_STOP:
                self._trailing_stops[symbol] = stop_order
                self._highest_prices[symbol] = position.current_price
            
            logger.info(f"Stop loss set for {symbol}: {stop_type.value} @ {stop_price}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting stop loss for {symbol}: {e}")
            return False
    
    async def set_take_profit(self, symbol: str, target_price: float) -> bool:
        """
        익절 주문 설정
        
        Args:
            symbol: 종목 코드
            target_price: 익절 가격
            
        Returns:
            bool: 설정 성공 여부
        """
        try:
            position = await self._get_position(symbol)
            if not position:
                logger.warning(f"No position found for {symbol}")
                return False
            
            stop_order = StopOrder(
                symbol=symbol,
                stop_type=StopType.FIXED_TAKE_PROFIT,
                trigger_price=Decimal(str(target_price)),
                quantity=abs(position.quantity),
                side='SELL' if position.quantity > 0 else 'BUY',
                original_entry_price=position.average_price,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Redis에 저장
            await self._save_stop_order(stop_order)
            
            logger.info(f"Take profit set for {symbol}: @ {target_price}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting take profit for {symbol}: {e}")
            return False
    
    async def cancel_stop_orders(self, symbol: str) -> bool:
        """
        스탑 주문 취소
        
        Args:
            symbol: 종목 코드
            
        Returns:
            bool: 취소 성공 여부
        """
        try:
            # Redis에서 스탑 주문 삭제
            stop_orders_key = f"stop_orders:{symbol}"
            await self.redis_manager.delete(stop_orders_key)
            
            # 트레일링 스탑 추적 제거
            self._trailing_stops.pop(symbol, None)
            self._highest_prices.pop(symbol, None)
            self._lowest_prices.pop(symbol, None)
            
            logger.info(f"Stop orders cancelled for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling stop orders for {symbol}: {e}")
            return False
    
    async def get_active_stop_orders(self) -> List[StopOrder]:
        """활성 스탑 주문 목록 조회"""
        try:
            stop_orders = []
            
            # Redis에서 모든 스탑 주문 조회
            keys = await self.redis_manager.get_keys_by_pattern("stop_orders:*")
            
            for key in keys:
                orders_data = await self.redis_manager.get_list(key)
                for order_data in orders_data:
                    stop_order = self._deserialize_stop_order(order_data)
                    if stop_order:
                        stop_orders.append(stop_order)
            
            return stop_orders
            
        except Exception as e:
            logger.error(f"Error getting active stop orders: {e}")
            return []
    
    # Private Methods
    
    async def _check_fixed_stop_loss(self, position: Position, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """고정 손절 조건 체크"""
        try:
            if not self.config.get('enable_auto_stop_loss', True):
                return None
            
            # 기본 손절 비율 적용
            stop_loss_pct = self.config.get('default_stop_loss_pct', 3.0)
            
            if position.quantity > 0:  # 매수 포지션 (LONG)
                stop_price = position.average_price * (1 - Decimal(stop_loss_pct / 100))
                if current_price <= stop_price:
                    logger.info(f"Fixed stop loss triggered for {position.symbol}: {current_price} <= {stop_price}")
                    return await self._execute_stop_loss(position, current_price, StopType.FIXED_STOP_LOSS)
            
            else:  # 매도 포지션 (SHORT)
                stop_price = position.average_price * (1 + Decimal(stop_loss_pct / 100))
                if current_price >= stop_price:
                    logger.info(f"Fixed stop loss triggered for {position.symbol}: {current_price} >= {stop_price}")
                    return await self._execute_stop_loss(position, current_price, StopType.FIXED_STOP_LOSS)
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking fixed stop loss: {e}")
            return None
    
    async def _check_fixed_take_profit(self, position: Position, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """고정 익절 조건 체크"""
        try:
            if not self.config.get('enable_auto_take_profit', False):
                return None
            
            # 기본 익절 비율 적용
            take_profit_pct = self.config.get('default_take_profit_pct', 5.0)
            
            if position.quantity > 0:  # 매수 포지션 (LONG)
                target_price = position.average_price * (1 + Decimal(take_profit_pct / 100))
                if current_price >= target_price:
                    logger.info(f"Fixed take profit triggered for {position.symbol}: {current_price} >= {target_price}")
                    return await self._execute_take_profit(position, current_price, StopType.FIXED_TAKE_PROFIT)
            
            else:  # 매도 포지션 (SHORT)
                target_price = position.average_price * (1 - Decimal(take_profit_pct / 100))
                if current_price <= target_price:
                    logger.info(f"Fixed take profit triggered for {position.symbol}: {current_price} <= {target_price}")
                    return await self._execute_take_profit(position, current_price, StopType.FIXED_TAKE_PROFIT)
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking fixed take profit: {e}")
            return None
    
    async def _update_and_check_trailing_stop(self, position: Position, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """트레일링 스탑 업데이트 및 체크"""
        try:
            symbol = position.symbol
            
            # 트레일링 스탑이 설정되지 않은 경우
            if symbol not in self._trailing_stops:
                return None
            
            trailing_stop_pct = self.config.get('trailing_stop_pct', 2.0)
            trailing_stop = self._trailing_stops[symbol]
            
            if position.quantity > 0:  # 매수 포지션 (LONG)
                # 최고가 업데이트
                if symbol not in self._highest_prices or current_price > self._highest_prices[symbol]:
                    self._highest_prices[symbol] = current_price
                    
                    # 트레일링 스탑 가격 업데이트
                    new_stop_price = current_price * (1 - Decimal(trailing_stop_pct / 100))
                    if new_stop_price > trailing_stop.trigger_price:
                        trailing_stop.trigger_price = new_stop_price
                        trailing_stop.updated_at = datetime.now()
                        await self._save_stop_order(trailing_stop)
                        
                        logger.debug(f"Trailing stop updated for {symbol}: {new_stop_price}")
                
                # 트리거 조건 체크
                if current_price <= trailing_stop.trigger_price:
                    logger.info(f"Trailing stop triggered for {symbol}: {current_price} <= {trailing_stop.trigger_price}")
                    return await self._execute_stop_loss(position, current_price, StopType.TRAILING_STOP)
            
            else:  # 매도 포지션 (SHORT)
                # 최저가 업데이트
                if symbol not in self._lowest_prices or current_price < self._lowest_prices[symbol]:
                    self._lowest_prices[symbol] = current_price
                    
                    # 트레일링 스탑 가격 업데이트
                    new_stop_price = current_price * (1 + Decimal(trailing_stop_pct / 100))
                    if new_stop_price < trailing_stop.trigger_price:
                        trailing_stop.trigger_price = new_stop_price
                        trailing_stop.updated_at = datetime.now()
                        await self._save_stop_order(trailing_stop)
                        
                        logger.debug(f"Trailing stop updated for {symbol}: {new_stop_price}")
                
                # 트리거 조건 체크
                if current_price >= trailing_stop.trigger_price:
                    logger.info(f"Trailing stop triggered for {symbol}: {current_price} >= {trailing_stop.trigger_price}")
                    return await self._execute_stop_loss(position, current_price, StopType.TRAILING_STOP)
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating trailing stop: {e}")
            return None
    
    async def _check_breakeven_stop(self, position: Position, current_price: Decimal) -> Optional[Dict[str, Any]]:
        """본전 보장 스탑 체크"""
        try:
            # 진입 후 일정 수익이 날 때 본전에서 손절선 설정
            breakeven_trigger_pct = 2.0  # 2% 수익 시 본전 보장
            
            if position.quantity > 0:  # 매수 포지션 (LONG)
                breakeven_trigger_price = position.average_price * (1 + Decimal(breakeven_trigger_pct / 100))
                
                # 수익이 일정 수준 이상일 때 본전 보장
                if current_price >= breakeven_trigger_price:
                    breakeven_stop_price = position.average_price * Decimal('1.001')  # 0.1% 수익 보장
                    
                    if current_price <= breakeven_stop_price:
                        logger.info(f"Breakeven stop triggered for {position.symbol}: {current_price} <= {breakeven_stop_price}")
                        return await self._execute_stop_loss(position, current_price, StopType.BREAKEVEN_STOP)
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking breakeven stop: {e}")
            return None
    
    async def _execute_stop_loss(self, position: Position, current_price: Decimal, stop_type: StopType) -> Dict[str, Any]:
        """손절 주문 실행"""
        try:
            # 손절 주문 생성
            order_data = {
                'symbol': position.symbol,
                'side': 'SELL' if position.quantity > 0 else 'BUY',
                'quantity': abs(position.quantity),
                'order_type': 'MARKET',
                'reason': f'{stop_type.value}_triggered',
                'trigger_price': float(current_price),
                'original_entry_price': float(position.average_price),
                'expected_pnl': float((current_price - position.average_price) * position.quantity)
            }
            
            # 주문 실행 이벤트 발행
            await self._publish_stop_order_event('STOP_LOSS_TRIGGERED', order_data)
            
            # 스탑 주문 정리
            await self.cancel_stop_orders(position.symbol)
            
            logger.info(f"Stop loss executed for {position.symbol}: {stop_type.value} @ {current_price}")
            
            return {
                'action': 'stop_loss_executed',
                'stop_type': stop_type.value,
                'symbol': position.symbol,
                'quantity': abs(position.quantity),
                'price': float(current_price),
                'pnl': float((current_price - position.average_price) * position.quantity),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error executing stop loss: {e}")
            return {
                'action': 'stop_loss_failed',
                'error': str(e),
                'symbol': position.symbol,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _execute_take_profit(self, position: Position, current_price: Decimal, stop_type: StopType) -> Dict[str, Any]:
        """익절 주문 실행"""
        try:
            # 익절 주문 생성
            order_data = {
                'symbol': position.symbol,
                'side': 'SELL' if position.quantity > 0 else 'BUY',
                'quantity': abs(position.quantity),
                'order_type': 'MARKET',
                'reason': f'{stop_type.value}_triggered',
                'trigger_price': float(current_price),
                'original_entry_price': float(position.average_price),
                'expected_pnl': float((current_price - position.average_price) * position.quantity)
            }
            
            # 주문 실행 이벤트 발행
            await self._publish_stop_order_event('TAKE_PROFIT_TRIGGERED', order_data)
            
            # 스탑 주문 정리
            await self.cancel_stop_orders(position.symbol)
            
            logger.info(f"Take profit executed for {position.symbol}: {stop_type.value} @ {current_price}")
            
            return {
                'action': 'take_profit_executed',
                'stop_type': stop_type.value,
                'symbol': position.symbol,
                'quantity': abs(position.quantity),
                'price': float(current_price),
                'pnl': float((current_price - position.average_price) * position.quantity),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error executing take profit: {e}")
            return {
                'action': 'take_profit_failed',
                'error': str(e),
                'symbol': position.symbol,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _get_position(self, symbol: str) -> Optional[Position]:
        """포지션 정보 조회"""
        try:
            # Redis에서 포지션 정보 조회
            position_key = f"positions:{symbol}"
            position_data = await self.redis_manager.get_hash(position_key)
            
            if not position_data:
                return None
            
            return Position(
                symbol=symbol,
                quantity=int(position_data.get('quantity', 0)),
                average_price=Decimal(position_data.get('average_price', '0')),
                current_price=Decimal(position_data.get('market_price', '0')),
                side='LONG' if int(position_data.get('quantity', 0)) > 0 else 'SHORT',
                unrealized_pnl=Decimal(position_data.get('unrealized_pnl', '0')),
                entry_time=datetime.fromisoformat(position_data.get('created_at', datetime.now().isoformat())),
                updated_at=datetime.fromisoformat(position_data.get('updated_at', datetime.now().isoformat()))
            )
            
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    async def _save_stop_order(self, stop_order: StopOrder):
        """스탑 주문 저장"""
        try:
            stop_orders_key = f"stop_orders:{stop_order.symbol}"
            order_data = {
                'symbol': stop_order.symbol,
                'stop_type': stop_order.stop_type.value,
                'trigger_price': str(stop_order.trigger_price),
                'quantity': stop_order.quantity,
                'side': stop_order.side,
                'original_entry_price': str(stop_order.original_entry_price),
                'created_at': stop_order.created_at.isoformat(),
                'updated_at': stop_order.updated_at.isoformat(),
                'metadata': stop_order.metadata or {}
            }
            
            await self.redis_manager.list_push(stop_orders_key, order_data, max_items=10)
            
        except Exception as e:
            logger.error(f"Error saving stop order: {e}")
    
    def _deserialize_stop_order(self, order_data: Dict[str, Any]) -> Optional[StopOrder]:
        """스탑 주문 역직렬화"""
        try:
            return StopOrder(
                symbol=order_data['symbol'],
                stop_type=StopType(order_data['stop_type']),
                trigger_price=Decimal(order_data['trigger_price']),
                quantity=order_data['quantity'],
                side=order_data['side'],
                original_entry_price=Decimal(order_data['original_entry_price']),
                created_at=datetime.fromisoformat(order_data['created_at']),
                updated_at=datetime.fromisoformat(order_data['updated_at']),
                metadata=order_data.get('metadata')
            )
            
        except Exception as e:
            logger.error(f"Error deserializing stop order: {e}")
            return None
    
    async def _publish_stop_order_event(self, event_type: str, order_data: Dict[str, Any]):
        """스탑 주문 이벤트 발행"""
        try:
            event = self.event_bus.create_event(
                event_type,
                source="AutoStopLossManager",
                data=order_data
            )
            self.event_bus.publish(event)
            
        except Exception as e:
            logger.error(f"Error publishing stop order event: {e}")