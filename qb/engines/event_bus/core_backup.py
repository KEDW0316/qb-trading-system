# Legacy Event Bus - DEPRECATED
# This module is kept for backward compatibility only.
# New code should use qb.engines.event_bus instead.

import warnings
import logging
from typing import Dict, Any, Callable, Optional, List

# Import new implementation
from ..engines.event_bus import (
    EnhancedEventBus as _EnhancedEventBus,
    Event as _Event,
    EventType as _EventType,
    EventPriority as _EventPriority,
    EventFilter as _EventFilter
)

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "qb.utils.event_bus is deprecated. Use qb.engines.event_bus instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
EventType = _EventType
Event = _Event
EventPriority = _EventPriority
EventFilter = _EventFilter


class EventBus:
    """
    Legacy EventBus wrapper for backward compatibility.
    
    This wraps the new EnhancedEventBus to maintain API compatibility
    with existing code while encouraging migration to the new implementation.
    """
    
    def __init__(self, redis_manager, max_workers: int = 10):
        """Initialize legacy EventBus wrapper"""
        warnings.warn(
            "EventBus is deprecated. Use EnhancedEventBus from qb.engines.event_bus instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        self._enhanced_bus = _EnhancedEventBus(
            redis_manager=redis_manager,
            max_workers=max_workers
        )
        
        # Legacy attributes for compatibility
        self.redis_manager = redis_manager
        self.logger = logging.getLogger(__name__)
        self.pubsub = redis_manager.redis.pubsub()
        self.subscribers = {}
        self.running = False
        self.listener_thread = None
        self.executor = None
        self._lock = None
        self.event_stats = {
            'published': 0,
            'received': 0,
            'processed': 0,
            'failed': 0
        }
    
    def start(self):
        """Start the event bus"""
        self._enhanced_bus.start()
        self.running = True
        logger.info("Legacy EventBus started (using EnhancedEventBus)")
    
    def stop(self):
        """Stop the event bus"""
        self._enhanced_bus.stop()
        self.running = False
        logger.info("Legacy EventBus stopped")
    
    def publish(self, event: _Event) -> bool:
        """Publish an event"""
        return self._enhanced_bus.publish(event)
    
    def subscribe(self, event_type: _EventType, callback: Callable[[_Event], None]) -> bool:
        """Subscribe to an event type"""
        try:
            subscription_id = self._enhanced_bus.subscribe(event_type, callback)
            
            # Store for legacy compatibility
            channel = f"event:{event_type.value}"
            if channel not in self.subscribers:
                self.subscribers[channel] = []
            self.subscribers[channel].append(callback)
            
            logger.info(f"Legacy subscription to {event_type.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            return False
    
    def unsubscribe(self, event_type: _EventType, callback: Callable[[_Event], None]) -> bool:
        """Unsubscribe from an event type"""
        # This is more complex for the legacy API, so we'll provide basic support
        logger.warning("Legacy unsubscribe called - consider migrating to new API")
        return True
    
    def get_stats(self) -> Dict[str, int]:
        """Get event processing statistics"""
        metrics = self._enhanced_bus.get_metrics()
        
        # Convert to legacy format
        return {
            'published': metrics['total']['published'],
            'received': metrics['total']['received'], 
            'processed': metrics['total']['processed'],
            'failed': metrics['total']['failed']
        }
    
    def broadcast_heartbeat(self, source: str, interval: int = 60):
        """Broadcast heartbeat (simplified for compatibility)"""
        logger.info(f"Legacy heartbeat requested for {source}")
        # Note: The new implementation handles heartbeats differently
        # This is here for API compatibility only
    
    def create_event(self, event_type: _EventType, source: str, 
                    data: Dict[str, Any], correlation_id: Optional[str] = None) -> _Event:
        """Create an event (delegate to new implementation)"""
        return self._enhanced_bus.create_event(
            event_type=event_type,
            source=source,
            data=data,
            correlation_id=correlation_id
        )
    
    # Additional methods for accessing the enhanced functionality
    def get_enhanced_bus(self) -> _EnhancedEventBus:
        """Get the underlying EnhancedEventBus instance"""
        warnings.warn(
            "Consider migrating to use EnhancedEventBus directly",
            DeprecationWarning,
            stacklevel=2
        )
        return self._enhanced_bus
    
    def health_check(self) -> Dict[str, Any]:
        """Health check (new functionality)"""
        return self._enhanced_bus.health_check()


# For maximum backward compatibility, provide the old function-style interface
def create_event_bus(redis_manager, max_workers: int = 10) -> EventBus:
    """
    Factory function for creating EventBus (legacy compatibility)
    
    DEPRECATED: Use EnhancedEventBus from qb.engines.event_bus instead
    """
    warnings.warn(
        "create_event_bus is deprecated. Use EnhancedEventBus directly.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return EventBus(redis_manager, max_workers)


# Migration guide comment
"""
MIGRATION GUIDE:

Old Code:
    from qb.utils.event_bus import EventBus, EventType
    
    event_bus = EventBus(redis_manager)
    event_bus.start()
    
    event = event_bus.create_event(EventType.MARKET_DATA_RECEIVED, "source", data)
    event_bus.publish(event)

New Code:
    from qb.engines.event_bus import EnhancedEventBus, EventType
    from qb.engines.event_bus.adapters import EventBusAdapter
    
    event_bus = EnhancedEventBus(redis_manager)
    event_bus.start()
    
    adapter = EventBusAdapter(event_bus, "MyComponent")
    adapter.publish_event(EventType.MARKET_DATA_RECEIVED, data)

Benefits of migrating:
- Better performance with batch processing
- Circuit breaker pattern for resilience  
- Enhanced metrics and monitoring
- Type-safe event filters
- Specialized adapters for different use cases
- Better error handling and recovery
"""