"""
Event Bus Engine

Enhanced event-driven communication system for QB Trading System.
Based on Redis Pub/Sub with production-ready features.
"""

from .core import (
    Event,
    EventType,
    EventPriority,
    EventFilter,
    EventSubscription,
    EnhancedEventBus,
    EventBusMetrics,
    CircuitBreaker
)

from .adapters import (
    EventBusAdapter,
    AsyncEventBusAdapter
)

from .handlers import (
    BaseEventHandler,
    MarketDataEventHandler,
    TradingSignalEventHandler,
    RiskAlertEventHandler,
    SystemEventHandler
)

__all__ = [
    # Core classes
    'Event',
    'EventType', 
    'EventPriority',
    'EventFilter',
    'EventSubscription',
    'EnhancedEventBus',
    'EventBusMetrics',
    'CircuitBreaker',
    
    # Adapters
    'EventBusAdapter',
    'AsyncEventBusAdapter',
    
    # Handlers
    'BaseEventHandler',
    'MarketDataEventHandler', 
    'TradingSignalEventHandler',
    'RiskAlertEventHandler',
    'SystemEventHandler'
]

# Default event bus instance (singleton)
_default_event_bus = None

def get_default_event_bus():
    """Get the default event bus instance"""
    global _default_event_bus
    return _default_event_bus

def set_default_event_bus(event_bus: EnhancedEventBus):
    """Set the default event bus instance"""
    global _default_event_bus
    _default_event_bus = event_bus