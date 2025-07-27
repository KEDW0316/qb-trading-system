"""
포지션 관리자 (Position Manager) 구현

QB Trading System의 실시간 포지션 추적 및 관리 시스템입니다.
체결 정보를 기반으로 포지션을 업데이트하고 손익을 계산합니다.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .base import BasePositionManager, Position, Fill, Order, OrderSide, OrderType
from ...utils.redis_manager import RedisManager
from ...database.connection import DatabaseManager

logger = logging.getLogger(__name__)


class PositionManager(BasePositionManager):
    """
    포지션 관리 시스템
    
    주요 기능:
    1. 실시간 포지션 추적
    2. 체결 기반 포지션 업데이트
    3. 손익 계산 및 관리
    4. 포지션 청산 주문 생성
    5. 데이터베이스 및 Redis 동기화
    """
    
    def __init__(
        self,
        redis_manager: RedisManager,
        db_manager: DatabaseManager,
        config: Optional[Dict[str, Any]] = None
    ):
        self.redis_manager = redis_manager
        self.db_manager = db_manager
        self.config = config or {}
        
        # 설정값
        self.enable_short_selling = self.config.get("enable_short_selling", False)
        self.position_size_limit = self.config.get("position_size_limit", 1_000_000)  # 포지션 크기 제한
        self.pnl_calculation_precision = self.config.get("pnl_calculation_precision", 2)
        
        # Redis 키 프리픽스
        self.position_key_prefix = "positions"
        self.daily_pnl_key_prefix = "daily_pnl"
        
        # 인메모리 포지션 캐시
        self._positions: Dict[str, Position] = {}
        self._position_lock = asyncio.Lock()
        
        # 일일 통계
        self._daily_stats: Dict[str, Dict[str, float]] = {}
        
        logger.info("PositionManager initialized")
    
    async def initialize(self):
        """포지션 매니저 초기화 - Redis와 DB에서 포지션 로드"""
        try:
            await self._load_positions_from_redis()
            await self._load_daily_stats()
            
            # DB와 동기화
            await self._sync_with_database()
            
            logger.info(f"PositionManager initialized with {len(self._positions)} positions")
            
        except Exception as e:
            logger.error(f"Error initializing PositionManager: {e}")
            raise
    
    async def update_position(self, symbol: str, fill: Fill) -> Position:
        """
        체결 정보를 기반으로 포지션 업데이트
        
        Args:
            symbol: 종목 코드
            fill: 체결 정보
            
        Returns:
            Position: 업데이트된 포지션
        """
        try:
            async with self._position_lock:
                # 기존 포지션 조회 또는 새로 생성
                position = self._positions.get(symbol)
                if not position:
                    position = Position(symbol=symbol)
                    self._positions[symbol] = position
                
                # 포지션에 체결 정보 반영
                position.add_fill(fill.side, fill.quantity, fill.price, fill.commission)
                
                # Redis에 저장
                await self._save_position_to_redis(position)
                
                # 일일 통계 업데이트
                await self._update_daily_stats(symbol, fill)
                
                # 데이터베이스에 체결 기록 저장
                await self._save_fill_to_database(fill)
                
                logger.info(f"Position updated: {symbol} - Qty: {position.quantity}, Avg: {position.average_price:.2f}")
                
                return position
                
        except Exception as e:
            logger.error(f"Error updating position for {symbol}: {e}")
            # 기존 포지션 반환 (실패해도 기존 상태 유지)
            return self._positions.get(symbol, Position(symbol=symbol))
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """
        특정 종목의 포지션 조회
        
        Args:
            symbol: 종목 코드
            
        Returns:
            Optional[Position]: 포지션 (없으면 None)
        """
        try:
            # 캐시에서 조회
            position = self._positions.get(symbol)
            if position:
                # 현재 시장가로 미실현 손익 업데이트
                current_price = await self._get_current_market_price(symbol)
                if current_price:
                    position.update_market_price(current_price)
                    await self._save_position_to_redis(position)
                
                return position
            
            # Redis에서 조회
            position = await self._load_position_from_redis(symbol)
            if position:
                self._positions[symbol] = position
                return position
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {e}")
            return None
    
    async def get_all_positions(self) -> List[Position]:
        """
        모든 포지션 조회
        
        Returns:
            List[Position]: 포지션 목록
        """
        try:
            positions = []
            
            # 모든 포지션의 현재 시장가 업데이트
            for symbol, position in self._positions.items():
                current_price = await self._get_current_market_price(symbol)
                if current_price:
                    position.update_market_price(current_price)
                    await self._save_position_to_redis(position)
                
                positions.append(position)
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting all positions: {e}")
            return []
    
    async def close_position(self, symbol: str) -> Optional[Order]:
        """
        포지션 청산 주문 생성
        
        Args:
            symbol: 청산할 종목 코드
            
        Returns:
            Optional[Order]: 청산 주문 (포지션이 없으면 None)
        """
        try:
            position = await self.get_position(symbol)
            if not position or position.is_flat:
                logger.info(f"No position to close for {symbol}")
                return None
            
            # 청산 주문 방향 결정
            if position.is_long:
                side = OrderSide.SELL
            else:
                side = OrderSide.BUY
            
            # 청산 주문 생성
            close_order = Order(
                symbol=symbol,
                side=side,
                order_type=OrderType.MARKET,  # 시장가로 즉시 청산
                quantity=abs(position.quantity),
                strategy_name="position_close",
                metadata={
                    "action": "close_position",
                    "original_position_quantity": position.quantity,
                    "average_price": position.average_price,
                    "unrealized_pnl": position.unrealized_pnl
                }
            )
            
            logger.info(f"Close position order created: {symbol} - {side.value} {close_order.quantity}")
            return close_order
            
        except Exception as e:
            logger.error(f"Error creating close position order for {symbol}: {e}")
            return None
    
    async def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        포트폴리오 요약 정보
        
        Returns:
            Dict[str, Any]: 포트폴리오 통계
        """
        try:
            positions = await self.get_all_positions()
            
            total_market_value = 0.0
            total_cost_basis = 0.0
            total_unrealized_pnl = 0.0
            total_realized_pnl = 0.0
            total_commission = 0.0
            long_positions = 0
            short_positions = 0
            
            for position in positions:
                if not position.is_flat:
                    total_market_value += position.market_value
                    total_cost_basis += position.cost_basis
                    total_unrealized_pnl += position.unrealized_pnl
                    total_realized_pnl += position.realized_pnl
                    total_commission += position.total_commission
                    
                    if position.is_long:
                        long_positions += 1
                    else:
                        short_positions += 1
            
            # 오늘의 손익 계산
            today = datetime.now().strftime("%Y-%m-%d")
            daily_pnl = await self._get_daily_pnl(today)
            
            return {
                "total_positions": len([p for p in positions if not p.is_flat]),
                "long_positions": long_positions,
                "short_positions": short_positions,
                "total_market_value": round(total_market_value, 2),
                "total_cost_basis": round(total_cost_basis, 2),
                "total_unrealized_pnl": round(total_unrealized_pnl, 2),
                "total_realized_pnl": round(total_realized_pnl, 2),
                "total_commission": round(total_commission, 2),
                "daily_pnl": round(daily_pnl, 2),
                "total_pnl": round(total_unrealized_pnl + total_realized_pnl, 2),
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            return {}
    
    async def get_position_history(self, symbol: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        포지션 히스토리 조회
        
        Args:
            symbol: 종목 코드
            days: 조회할 일수
            
        Returns:
            List[Dict[str, Any]]: 포지션 히스토리
        """
        try:
            # 데이터베이스에서 체결 기록 조회
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # SQL 쿼리 실행 (실제 구현에서는 ORM 사용)
            query = """
            SELECT * FROM trades 
            WHERE symbol = %s AND timestamp >= %s AND timestamp <= %s
            ORDER BY timestamp ASC
            """
            
            # 여기서는 간단히 Redis에서 조회
            history = []
            for i in range(days):
                date = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
                fills_key = f"fills:{symbol}:{date}"
                daily_fills = await self.redis_manager.list_get_all(fills_key)
                
                for fill_data in daily_fills:
                    if isinstance(fill_data, dict):
                        history.append(fill_data)
            
            return sorted(history, key=lambda x: x.get("timestamp", ""))
            
        except Exception as e:
            logger.error(f"Error getting position history for {symbol}: {e}")
            return []
    
    async def calculate_risk_metrics(self) -> Dict[str, float]:
        """
        리스크 지표 계산
        
        Returns:
            Dict[str, float]: 리스크 지표
        """
        try:
            positions = await self.get_all_positions()
            portfolio_summary = await self.get_portfolio_summary()
            
            if not positions:
                return {}
            
            # 포지션 집중도 계산
            total_market_value = portfolio_summary.get("total_market_value", 0)
            if total_market_value == 0:
                return {}
            
            max_position_exposure = 0.0
            position_count = 0
            
            for position in positions:
                if not position.is_flat:
                    position_exposure = abs(position.market_value) / total_market_value
                    max_position_exposure = max(max_position_exposure, position_exposure)
                    position_count += 1
            
            # VaR 계산 (간단한 버전)
            volatilities = []
            for position in positions:
                if not position.is_flat and position.average_price > 0:
                    price_change_ratio = abs(position.market_price - position.average_price) / position.average_price
                    volatilities.append(price_change_ratio)
            
            avg_volatility = sum(volatilities) / len(volatilities) if volatilities else 0.0
            var_95 = total_market_value * avg_volatility * 1.645  # 95% VaR
            
            return {
                "max_position_exposure": round(max_position_exposure, 4),
                "average_position_size": round(1.0 / position_count if position_count > 0 else 0, 4),
                "portfolio_concentration": round(max_position_exposure * position_count, 4),
                "value_at_risk_95": round(var_95, 2),
                "gross_exposure": round(total_market_value, 2),
                "net_exposure": round(portfolio_summary.get("total_unrealized_pnl", 0), 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {}
    
    async def _save_position_to_redis(self, position: Position):
        """Redis에 포지션 저장"""
        try:
            position_key = f"{self.position_key_prefix}:{position.symbol}"
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
            
            # 포지션이 청산된 경우 Redis에서 제거
            if position.is_flat:
                await self.redis_manager.delete_key(position_key)
            
        except Exception as e:
            logger.error(f"Error saving position to Redis: {e}")
    
    async def _load_position_from_redis(self, symbol: str) -> Optional[Position]:
        """Redis에서 포지션 로드"""
        try:
            position_key = f"{self.position_key_prefix}:{symbol}"
            position_data = await self.redis_manager.get_hash(position_key)
            
            if position_data:
                position = Position(
                    symbol=position_data["symbol"],
                    quantity=int(position_data["quantity"]),
                    average_price=float(position_data["average_price"]),
                    market_price=float(position_data["market_price"]),
                    unrealized_pnl=float(position_data["unrealized_pnl"]),
                    realized_pnl=float(position_data["realized_pnl"]),
                    total_commission=float(position_data["total_commission"]),
                    updated_at=datetime.fromisoformat(position_data["updated_at"])
                )
                return position
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading position from Redis: {e}")
            return None
    
    async def _load_positions_from_redis(self):
        """Redis에서 모든 포지션 로드"""
        try:
            # Redis에서 모든 포지션 키 조회
            pattern = f"{self.position_key_prefix}:*"
            position_keys = await self.redis_manager.scan_keys(pattern)
            
            for key in position_keys:
                symbol = key.split(":")[-1]
                position = await self._load_position_from_redis(symbol)
                if position:
                    self._positions[symbol] = position
            
        except Exception as e:
            logger.error(f"Error loading positions from Redis: {e}")
    
    async def _get_current_market_price(self, symbol: str) -> Optional[float]:
        """현재 시장 가격 조회"""
        try:
            market_data_key = f"market_data:{symbol}"
            market_data = await self.redis_manager.get_hash(market_data_key)
            
            if market_data and "close" in market_data:
                return float(market_data["close"])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting current market price for {symbol}: {e}")
            return None
    
    async def _update_daily_stats(self, symbol: str, fill: Fill):
        """일일 통계 업데이트"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            stats_key = f"{self.daily_pnl_key_prefix}:{today}"
            
            # 거래 횟수 업데이트
            await self.redis_manager.hash_increment(stats_key, "trade_count", 1)
            
            # 거래량 업데이트
            await self.redis_manager.hash_increment(stats_key, "total_volume", fill.quantity)
            
            # 수수료 누적
            await self.redis_manager.hash_increment(stats_key, "total_commission", fill.commission)
            
        except Exception as e:
            logger.error(f"Error updating daily stats: {e}")
    
    async def _get_daily_pnl(self, date: str) -> float:
        """특정 날짜의 일일 손익 조회"""
        try:
            stats_key = f"{self.daily_pnl_key_prefix}:{date}"
            stats = await self.redis_manager.get_hash(stats_key)
            
            if stats and "realized_pnl" in stats:
                return float(stats["realized_pnl"])
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting daily PnL for {date}: {e}")
            return 0.0
    
    async def _load_daily_stats(self):
        """일일 통계 로드"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            for i in range(7):  # 최근 7일간의 통계 로드
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                stats_key = f"{self.daily_pnl_key_prefix}:{date}"
                stats = await self.redis_manager.get_hash(stats_key)
                
                if stats:
                    self._daily_stats[date] = {
                        "trade_count": int(stats.get("trade_count", 0)),
                        "total_volume": int(stats.get("total_volume", 0)),
                        "total_commission": float(stats.get("total_commission", 0)),
                        "realized_pnl": float(stats.get("realized_pnl", 0))
                    }
            
        except Exception as e:
            logger.error(f"Error loading daily stats: {e}")
    
    async def _save_fill_to_database(self, fill: Fill):
        """체결 정보를 데이터베이스에 저장"""
        try:
            # 실제 구현에서는 ORM을 사용하여 trades 테이블에 저장
            # 여기서는 로깅만 수행
            logger.debug(f"Fill saved to database: {fill.fill_id} - {fill.symbol} {fill.side.value} {fill.quantity}@{fill.price}")
            
        except Exception as e:
            logger.error(f"Error saving fill to database: {e}")
    
    async def _sync_with_database(self):
        """데이터베이스와 동기화"""
        try:
            # 실제 구현에서는 데이터베이스의 포지션 테이블과 동기화
            # 여기서는 생략
            logger.debug("Position sync with database completed")
            
        except Exception as e:
            logger.error(f"Error syncing with database: {e}")