"""ABOUTME: Unified API interface for seamless multi-market access"""

from .client import UnifiedClient
from .websocket import UnifiedWebSocket

__all__ = [
    "UnifiedClient",
    "UnifiedWebSocket"
]