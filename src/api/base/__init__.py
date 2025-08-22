"""ABOUTME: Base classes and common functionality for all API clients"""

from .client import BaseAPIClient
from .websocket import BaseWebSocketClient
from .exceptions import (
    KISAPIException,
    AuthenticationError,
    TokenExpiredError,
    RateLimitError,
    InvalidRequestError,
    MarketClosedError,
    InsufficientBalanceError,
    OrderFailedError,
    WebSocketError,
    WebSocketConnectionError,
    WebSocketSubscriptionError,
    DataParsingError
)

__all__ = [
    "BaseAPIClient",
    "BaseWebSocketClient",
    "KISAPIException",
    "AuthenticationError",
    "TokenExpiredError", 
    "RateLimitError",
    "InvalidRequestError",
    "MarketClosedError",
    "InsufficientBalanceError",
    "OrderFailedError",
    "WebSocketError",
    "WebSocketConnectionError",
    "WebSocketSubscriptionError",
    "DataParsingError"
]