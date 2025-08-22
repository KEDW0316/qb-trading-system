"""ABOUTME: Modern refactored KIS API wrapper with market-specific modules and unified interface"""

# 통합 인터페이스 (권장 사용)
from .unified.client import UnifiedClient
from .unified.websocket import UnifiedWebSocket

# 시장별 클라이언트 (직접 사용 가능)
from .markets.korea.client import KoreaStockClient
from .markets.usa.client import USStockClient
from .markets.korea.websocket import KoreaWebSocketClient
from .markets.usa.websocket import USWebSocketClient

# 베이스 클래스
from .base.client import BaseAPIClient
from .base.websocket import BaseWebSocketClient

# 모델과 예외
from .models.enums import Market, KoreaExchange, USExchange, OrderType
from .base.exceptions import (
    KISAPIException,
    AuthenticationError,
    RateLimitError,
    WebSocketError
)

__version__ = "2.0.0"

__all__ = [
    # 통합 인터페이스
    "UnifiedClient",
    "UnifiedWebSocket",
    
    # 시장별 클라이언트
    "KoreaStockClient",
    "USStockClient", 
    "KoreaWebSocketClient",
    "USWebSocketClient",
    
    # 베이스 클래스
    "BaseAPIClient",
    "BaseWebSocketClient",
    
    # 모델과 예외
    "Market",
    "KoreaExchange",
    "USExchange",
    "OrderType",
    "KISAPIException",
    "AuthenticationError",
    "RateLimitError",
    "WebSocketError"
]