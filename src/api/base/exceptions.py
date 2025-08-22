"""
ABOUTME: Custom exception classes for KIS API wrapper
"""


class KISAPIException(Exception):
    """KIS API 기본 예외 클래스"""
    pass


class AuthenticationError(KISAPIException):
    """인증 관련 오류"""
    pass


class TokenExpiredError(AuthenticationError):
    """토큰 만료 오류"""
    pass


class RateLimitError(KISAPIException):
    """Rate Limit 초과 오류"""
    pass


class InvalidRequestError(KISAPIException):
    """잘못된 요청 오류"""
    pass


class MarketClosedError(KISAPIException):
    """시장 마감 오류"""
    pass


class InsufficientBalanceError(KISAPIException):
    """잔고 부족 오류"""
    pass


class OrderFailedError(KISAPIException):
    """주문 실패 오류"""
    pass


class WebSocketError(KISAPIException):
    """WebSocket 연결 오류"""
    pass


class WebSocketConnectionError(WebSocketError):
    """WebSocket 연결 실패"""
    pass


class WebSocketSubscriptionError(WebSocketError):
    """WebSocket 구독 실패"""
    pass


class DataParsingError(KISAPIException):
    """데이터 파싱 오류"""
    pass