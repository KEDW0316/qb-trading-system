"""
KIS API 인증 및 토큰 관리 클래스
TDD로 구현 - 리팩토링으로 개선
"""

import json
import logging
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .models import TokenInfo, KISCredentials, APIEndpoints
from .exceptions import TokenIssueError, InvalidCredentialsError
from .config import KISAPIConfig, ENDPOINTS, COMMON_HEADERS


class KISAuthManager:
    """KIS API 인증 및 토큰 관리 클래스"""
    
    def __init__(self, env: str = "vps"):
        """
        초기화
        Args:
            env: "prod" (실전투자) or "vps" (모의투자)
        """
        if env not in ENDPOINTS:
            raise ValueError(f"Invalid environment: {env}. Must be one of: {list(ENDPOINTS.keys())}")
            
        self.env = env
        self.logger = logging.getLogger(f"{__name__}.{env}")
        self.credentials = KISCredentials.from_env()
        self.config = KISAPIConfig()
        
        # 인증 정보 검증
        self._validate_credentials()
        
        # API 엔드포인트 설정
        if env == "prod":
            self.endpoints = APIEndpoints.get_prod_endpoints()
        else:
            self.endpoints = APIEndpoints.get_vps_endpoints()
        
        self.logger.info(f"KIS Auth Manager initialized for {env} environment")
    
    def _validate_credentials(self) -> None:
        """인증 정보 유효성 검증"""
        if not self.credentials.app_key or not self.credentials.app_secret:
            raise InvalidCredentialsError("KIS_APP_KEY and KIS_APP_SECRET must be set")
        
        if not self.credentials.account_no:
            raise InvalidCredentialsError("KIS_ACCOUNT_NO must be set")
        
        self.logger.debug("Credentials validation passed")
    
    async def get_access_token(self) -> str:
        """액세스 토큰 조회 (자동 갱신 포함)"""
        try:
            # 캐시된 토큰 확인
            cached_token = self._load_token_from_file()
            
            if self._is_token_valid(cached_token):
                self.logger.debug("Using cached token")
                return cached_token.access_token
            
            # 토큰이 없거나 만료된 경우 새로 발급
            if cached_token:
                self.logger.info("Token expired, issuing new token")
            else:
                self.logger.info("No cached token found, issuing new token")
                
            new_token = await self._issue_new_token()
            self._save_token_to_file(new_token)
            
            self.logger.info("New token issued successfully")
            return new_token.access_token
            
        except Exception as e:
            self.logger.error(f"Failed to get access token: {e}")
            raise
    
    async def get_websocket_approval_key(self) -> str:
        """WebSocket 인증키 조회"""
        return await self._issue_websocket_key()
    
    def get_headers(self) -> dict:
        """API 호출용 헤더 생성"""
        # 주의: 이 메서드는 동기 메서드이므로 실제로는 캐시된 토큰만 사용
        # 실제 구현에서는 비동기 버전을 만들거나 호출 전에 토큰을 미리 준비해야 함
        cached_token = self._load_token_from_file()
        if not self._is_token_valid(cached_token):
            raise TokenIssueError("No valid token available. Call get_access_token() first.")
        
        return {
            "Authorization": f"Bearer {cached_token.access_token}",
            "Content-Type": "application/json",
            "appkey": self.credentials.app_key,
            "appsecret": self.credentials.app_secret
        }
    
    async def _issue_new_token(self) -> TokenInfo:
        """새 토큰 발급 (OAuth2 /tokenP 호출)"""
        url = f"{self.endpoints.base_url}{self.endpoints.token_path}"
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self.credentials.app_key,
            "appsecret": self.credentials.app_secret
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                result = await response.json()
                
                if response.status != 200:
                    error_msg = result.get("error_description", f"HTTP {response.status}")
                    raise TokenIssueError(f"Token issue failed: {error_msg}")
                
                if "access_token" not in result:
                    raise TokenIssueError("Invalid response format: missing access_token")
                
                return TokenInfo(
                    access_token=result["access_token"],
                    token_type=result.get("token_type", "Bearer"),
                    expires_in=result.get("expires_in", 86400)
                )
    
    async def _issue_websocket_key(self) -> str:
        """WebSocket 인증키 발급"""
        url = f"{self.endpoints.base_url}{self.endpoints.websocket_auth_path}"
        
        data = {
            "grant_type": "client_credentials", 
            "appkey": self.credentials.app_key,
            "secretkey": self.credentials.app_secret
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                result = await response.json()
                
                if response.status != 200:
                    error_msg = result.get("error_description", f"HTTP {response.status}")
                    raise TokenIssueError(f"WebSocket key issue failed: {error_msg}")
                
                return result["approval_key"]
    
    def _save_token_to_file(self, token_info: TokenInfo) -> None:
        """토큰을 JSON 파일로 저장"""
        file_path = Path(self._get_token_file_path())
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "access_token": token_info.access_token,
            "token_type": token_info.token_type,
            "expires_in": token_info.expires_in,
            "expires_at": token_info.expires_at.isoformat(),
            "created_at": token_info.created_at.isoformat()
        }
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_token_from_file(self) -> Optional[TokenInfo]:
        """JSON 파일에서 토큰 로드"""
        file_path = Path(self._get_token_file_path())
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return TokenInfo(
                access_token=data["access_token"],
                token_type=data["token_type"],
                expires_in=data["expires_in"],
                expires_at=datetime.fromisoformat(data["expires_at"]),
                created_at=datetime.fromisoformat(data["created_at"])
            )
        
        except (json.JSONDecodeError, KeyError, ValueError):
            # 파일이 손상된 경우 None 반환
            return None
    
    def _is_token_valid(self, token_info: Optional[TokenInfo]) -> bool:
        """토큰 유효성 검증 (만료시간 체크 + 버퍼)"""
        if token_info is None:
            return False
        
        # 만료 5분 전까지 유효하다고 판단 (안전 마진)
        buffer_time = timedelta(seconds=self.config.TOKEN_EXPIRY_BUFFER)
        expiry_with_buffer = token_info.expires_at - buffer_time
        
        is_valid = datetime.now() < expiry_with_buffer
        
        if not is_valid:
            remaining = token_info.time_until_expiry()
            self.logger.debug(f"Token expires in {remaining} seconds")
            
        return is_valid
    
    def _get_token_expiry_time(self, expires_in: int) -> datetime:
        """토큰 만료시간 계산"""
        return datetime.now() + timedelta(seconds=expires_in)
    
    def _get_api_base_url(self) -> str:
        """환경별 API Base URL 반환"""
        return self.endpoints.base_url
    
    def _get_websocket_url(self) -> str:
        """환경별 WebSocket URL 반환"""
        return self.endpoints.websocket_url
    
    def _get_token_file_path(self) -> str:
        """토큰 파일 경로 생성"""
        return f"data/cache/kis_token_{self.env}.json"