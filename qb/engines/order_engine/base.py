"""
주문 엔진의 기본 데이터 클래스 및 인터페이스 모듈

QB Trading System의 주문 처리를 위한 핵심 데이터 구조와 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """주문 타입 정의"""
    MARKET = "MARKET"      # 시장가 주문
    LIMIT = "LIMIT"        # 지정가 주문
    STOP = "STOP"          # 스탑 주문
    STOP_LIMIT = "STOP_LIMIT"  # 스탑 지정가 주문


class OrderSide(Enum):
    """주문 방향 정의"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """주문 상태 정의"""
    PENDING = "PENDING"        # 대기
    SUBMITTED = "SUBMITTED"    # 제출됨
    PARTIAL_FILLED = "PARTIAL_FILLED"  # 부분 체결
    FILLED = "FILLED"          # 완전 체결
    CANCELLED = "CANCELLED"    # 취소됨
    REJECTED = "REJECTED"      # 거부됨
    FAILED = "FAILED"          # 실패


class TimeInForce(Enum):
    """주문 유효 기간 정의"""
    DAY = "DAY"              # 당일 유효
    GTC = "GTC"              # Good Till Cancelled
    IOC = "IOC"              # Immediate or Cancel
    FOK = "FOK"              # Fill or Kill


@dataclass
class Order:
    """주문을 나타내는 데이터 클래스"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    strategy_name: Optional[str] = None
    
    # 시스템 관리 필드
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # 체결 정보
    filled_quantity: int = 0
    average_fill_price: Optional[float] = None
    commission: Optional[float] = None
    
    # 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """생성 후 검증"""
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {self.quantity}")
        
        if self.order_type == OrderType.LIMIT and self.price is None:
            raise ValueError("LIMIT order requires price")
        
        if self.order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and self.stop_price is None:
            raise ValueError(f"{self.order_type.value} order requires stop_price")
    
    @property
    def is_filled(self) -> bool:
        """완전 체결 여부"""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_partial_filled(self) -> bool:
        """부분 체결 여부"""
        return self.status == OrderStatus.PARTIAL_FILLED
    
    @property
    def is_active(self) -> bool:
        """활성 주문 여부 (체결 대기 중)"""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]
    
    @property
    def remaining_quantity(self) -> int:
        """미체결 수량"""
        return self.quantity - self.filled_quantity
    
    def update_status(self, new_status: OrderStatus):
        """주문 상태 업데이트"""
        self.status = new_status
        self.updated_at = datetime.now()
    
    def add_fill(self, quantity: int, price: float, commission: float = 0.0):
        """체결 정보 추가"""
        if quantity <= 0:
            raise ValueError("Fill quantity must be positive")
        
        if self.filled_quantity + quantity > self.quantity:
            raise ValueError("Fill quantity exceeds order quantity")
        
        # 평균 체결가 계산
        if self.average_fill_price is None:
            self.average_fill_price = price
        else:
            total_value = (self.average_fill_price * self.filled_quantity) + (price * quantity)
            self.average_fill_price = total_value / (self.filled_quantity + quantity)
        
        self.filled_quantity += quantity
        self.commission = (self.commission or 0.0) + commission
        
        # 상태 업데이트
        if self.filled_quantity == self.quantity:
            self.update_status(OrderStatus.FILLED)
        else:
            self.update_status(OrderStatus.PARTIAL_FILLED)


@dataclass
class OrderResult:
    """주문 실행 결과를 나타내는 데이터 클래스"""
    order_id: str
    success: bool
    broker_order_id: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Fill:
    """체결 정보를 나타내는 데이터 클래스"""
    fill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: int = 0
    price: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    broker_fill_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """포지션 정보를 나타내는 데이터 클래스"""
    symbol: str
    quantity: int = 0
    average_price: float = 0.0
    market_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_commission: float = 0.0
    updated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def market_value(self) -> float:
        """현재 시장 가치"""
        return self.quantity * self.market_price
    
    @property
    def cost_basis(self) -> float:
        """매입 원가"""
        return abs(self.quantity) * self.average_price
    
    @property
    def is_long(self) -> bool:
        """롱 포지션 여부"""
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        """숏 포지션 여부"""
        return self.quantity < 0
    
    @property
    def is_flat(self) -> bool:
        """포지션 없음"""
        return self.quantity == 0
    
    def update_market_price(self, new_price: float):
        """시장 가격 업데이트 및 미실현 손익 계산"""
        self.market_price = new_price
        if not self.is_flat:
            self.unrealized_pnl = (new_price - self.average_price) * self.quantity
        else:
            self.unrealized_pnl = 0.0
        self.updated_at = datetime.now()
    
    def add_fill(self, side: OrderSide, quantity: int, price: float, commission: float = 0.0):
        """체결 정보를 포지션에 반영"""
        fill_quantity = quantity if side == OrderSide.BUY else -quantity
        
        if self.is_flat:
            # 새로운 포지션
            self.quantity = fill_quantity
            self.average_price = price
        else:
            # 기존 포지션 수정
            if (self.quantity > 0 and fill_quantity > 0) or (self.quantity < 0 and fill_quantity < 0):
                # 같은 방향 - 평균가 계산
                total_cost = (abs(self.quantity) * self.average_price) + (quantity * price)
                total_quantity = abs(self.quantity) + quantity
                self.average_price = total_cost / total_quantity
                self.quantity += fill_quantity
            else:
                # 반대 방향 - 실현 손익 계산
                close_quantity = min(abs(self.quantity), quantity)
                realized_gain = (price - self.average_price) * close_quantity
                if self.quantity < 0:
                    realized_gain = -realized_gain
                
                self.realized_pnl += realized_gain
                self.quantity += fill_quantity
                
                # 포지션이 뒤바뀐 경우 새로운 평균가 설정
                if abs(fill_quantity) > abs(self.quantity - fill_quantity):
                    self.average_price = price
        
        self.total_commission += commission
        self.updated_at = datetime.now()


class BaseBrokerClient(ABC):
    """브로커 클라이언트 인터페이스"""
    
    @abstractmethod
    async def place_order(self, order: Order) -> OrderResult:
        """주문 제출"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> OrderResult:
        """주문 취소"""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """주문 상태 조회"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """포지션 조회"""
        pass
    
    @abstractmethod
    async def get_account_balance(self) -> Dict[str, float]:
        """계좌 잔고 조회"""
        pass


class BaseOrderQueue(ABC):
    """주문 큐 인터페이스"""
    
    @abstractmethod
    async def add_order(self, order: Order) -> bool:
        """주문 큐에 추가"""
        pass
    
    @abstractmethod
    async def get_next_order(self) -> Optional[Order]:
        """다음 처리할 주문 반환"""
        pass
    
    @abstractmethod
    async def remove_order(self, order_id: str) -> bool:
        """주문 큐에서 제거"""
        pass
    
    @abstractmethod
    async def get_pending_orders(self) -> List[Order]:
        """대기 중인 주문 목록"""
        pass


class BasePositionManager(ABC):
    """포지션 관리자 인터페이스"""
    
    @abstractmethod
    async def update_position(self, symbol: str, fill: Fill) -> Position:
        """포지션 업데이트"""
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """포지션 조회"""
        pass
    
    @abstractmethod
    async def get_all_positions(self) -> List[Position]:
        """모든 포지션 조회"""
        pass
    
    @abstractmethod
    async def close_position(self, symbol: str) -> Optional[Order]:
        """포지션 청산 주문 생성"""
        pass


class BaseCommissionCalculator(ABC):
    """수수료 계산기 인터페이스"""
    
    @abstractmethod
    def calculate_commission(self, order: Order, fill_price: float, fill_quantity: int) -> float:
        """수수료 계산"""
        pass
    
    @abstractmethod
    def get_commission_rate(self, symbol: str, order_type: OrderType) -> float:
        """수수료율 조회"""
        pass