"""
KIS 인증 관련 데이터 모델
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class TokenInfo:
    """토큰 정보 데이터 클래스"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400  # 24시간 (초)
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.created_at is None:
            self.created_at = datetime.now()
        
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(seconds=self.expires_in)
    
    def is_expired(self) -> bool:
        """토큰 만료 여부 확인"""
        return datetime.now() >= self.expires_at
    
    def time_until_expiry(self) -> int:
        """만료까지 남은 시간 (초)"""
        if self.is_expired():
            return 0
        return int((self.expires_at - datetime.now()).total_seconds())


@dataclass
class KISCredentials:
    """KIS API 인증 정보"""
    app_key: str
    app_secret: str
    account_no: str
    account_prod_cd: str = "01"
    
    @classmethod
    def from_env(cls) -> "KISCredentials":
        """환경변수에서 인증정보 로드"""
        return cls(
            app_key=os.getenv("KIS_APP_KEY", ""),
            app_secret=os.getenv("KIS_APP_SECRET", ""),
            account_no=os.getenv("KIS_ACCOUNT_NO", ""),
            account_prod_cd=os.getenv("KIS_ACCOUNT_PROD_CD", "01")
        )


@dataclass
class APIEndpoints:
    """KIS API 엔드포인트 정의"""
    base_url: str
    token_path: str = "/oauth2/tokenP"
    websocket_auth_path: str = "/oauth2/Approval"
    websocket_url: str = ""
    
    @classmethod
    def get_prod_endpoints(cls) -> "APIEndpoints":
        """실전투자 엔드포인트"""
        return cls(
            base_url="https://openapi.koreainvestment.com:9443",
            websocket_url="wss://ops.koreainvestment.com:21000"
        )
    
    @classmethod
    def get_vps_endpoints(cls) -> "APIEndpoints":
        """모의투자 엔드포인트"""
        return cls(
            base_url="https://openapivts.koreainvestment.com:29443", 
            websocket_url="wss://ops.koreainvestment.com:31000"
        )