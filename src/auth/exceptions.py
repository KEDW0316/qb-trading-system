"""
KIS 인증 관련 예외 클래스
"""


class KISAuthError(Exception):
    """KIS 인증 관련 기본 예외"""
    pass


class TokenExpiredError(KISAuthError):
    """토큰 만료 예외"""
    pass


class TokenIssueError(KISAuthError):
    """토큰 발급 실패 예외"""
    pass


class InvalidCredentialsError(KISAuthError):
    """잘못된 인증 정보 예외"""
    pass


class RateLimitExceededError(KISAuthError):
    """Rate Limit 초과 예외"""
    pass