"""
Order Engine Module

QB Trading System's order processing core module.
Handles trading signal to order conversion and execution via event-driven architecture.

Main Components:
- OrderEngine: Main order processing engine
- KISBrokerClient: Korean Investment Securities API integration client
- OrderQueue: Order queue management system
- PositionManager: Position manager
- CommissionCalculator: Commission calculator
"""

from .base import (
    Order, OrderResult, Fill, Position,
    OrderType, OrderSide, OrderStatus, TimeInForce,
    BaseBrokerClient, BaseOrderQueue, BasePositionManager, BaseCommissionCalculator
)

from .engine import OrderEngine
from .kis_broker_client import KISBrokerClient
from .order_queue import OrderQueue, PriorityOrder
from .position_manager import PositionManager
from .commission_calculator import (
    KoreanStockCommissionCalculator,
    ETFCommissionCalculator,
    ForeignStockCommissionCalculator
)

__all__ = [
    # Base classes and data types
    'Order',
    'OrderResult', 
    'Fill',
    'Position',
    'OrderType',
    'OrderSide', 
    'OrderStatus',
    'TimeInForce',
    'BaseBrokerClient',
    'BaseOrderQueue',
    'BasePositionManager', 
    'BaseCommissionCalculator',
    
    # Main components
    'OrderEngine',
    'KISBrokerClient',
    'OrderQueue',
    'PriorityOrder',
    'PositionManager',
    
    # Commission calculators
    'KoreanStockCommissionCalculator',
    'ETFCommissionCalculator',
    'ForeignStockCommissionCalculator',
]