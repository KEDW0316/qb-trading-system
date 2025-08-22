"""
ABOUTME: Base API client class providing common functionality for all market-specific clients
"""

import aiohttp
import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, Union
from datetime import datetime

from src.auth.kis_auth import KISAuthManager
from src.utils.rate_limiter import RateLimiter
from src.api.base.exceptions import (
    KISAPIException,
    AuthenticationError,
    RateLimitError,
    InvalidRequestError
)


class BaseAPIClient(ABC):
    """KIS API 기본 클라이언트 클래스"""
    
    def __init__(self, auth_manager: KISAuthManager, rate_limiter: RateLimiter):
        """
        초기화
        
        Args:
            auth_manager: 인증 관리자
            rate_limiter: Rate Limit 관리자
        """
        self.auth_manager = auth_manager
        self.rate_limiter = rate_limiter
        self.logger = self._setup_logger()
        
        # API Base URL
        self.base_url = auth_manager._get_api_base_url()
        
        # 환경별 TR_ID 설정
        self.tr_ids = self._get_tr_ids(auth_manager.env)
        
        # 세션 관리
        self._session: Optional[aiohttp.ClientSession] = None
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    @abstractmethod
    def _get_tr_ids(self, env: str) -> Dict[str, str]:
        """
        환경별 TR_ID 매핑 반환
        
        Args:
            env: 환경 (prod/vps)
            
        Returns:
            TR_ID 매핑 딕셔너리
        """
        pass
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP 세션 가져오기 (재사용)"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """세션 종료"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.close()
    
    async def _make_request(self,
                           method: str,
                           endpoint: str,
                           tr_id: str,
                           params: Optional[Dict] = None,
                           data: Optional[Dict] = None,
                           **kwargs) -> Dict:
        """
        API 요청 실행
        
        Args:
            method: HTTP 메서드 (GET, POST)
            endpoint: API 엔드포인트
            tr_id: 거래 ID
            params: Query parameters
            data: Request body
            **kwargs: 추가 옵션
            
        Returns:
            API 응답 데이터
            
        Raises:
            KISAPIException: API 오류
            RateLimitError: Rate limit 초과
            AuthenticationError: 인증 오류
        """
        # Rate Limit 체크
        try:
            await self.rate_limiter.acquire()
        except Exception as e:
            self.logger.error(f"Rate limit error: {e}")
            raise RateLimitError(f"Rate limit exceeded: {e}")
        
        # 토큰 가져오기
        try:
            token = await self.auth_manager.get_access_token()
        except Exception as e:
            self.logger.error(f"Authentication error: {e}")
            raise AuthenticationError(f"Failed to get access token: {e}")
        
        # 헤더 구성
        headers = {
            "Authorization": f"Bearer {token}",
            "appkey": self.auth_manager.credentials.app_key,
            "appsecret": self.auth_manager.credentials.app_secret,
            "tr_id": tr_id,
            "Content-Type": "application/json"
        }
        
        # 추가 헤더 병합
        if "headers" in kwargs:
            headers.update(kwargs["headers"])
        
        # URL 구성
        url = f"{self.base_url}{endpoint}"
        
        # 디버그 로깅
        self.logger.debug(f"Request: {method} {url}")
        self.logger.debug(f"TR_ID: {tr_id}")
        if params:
            self.logger.debug(f"Params: {params}")
        if data:
            self.logger.debug(f"Data: {data}")
        
        # API 호출
        try:
            session = await self._get_session()
            
            if method.upper() == "GET":
                async with session.get(url, headers=headers, params=params) as response:
                    result = await response.json()
            else:  # POST
                async with session.post(url, headers=headers, json=data) as response:
                    result = await response.json()
            
            # 응답 처리
            return self._handle_response(result)
            
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP client error: {e}")
            raise KISAPIException(f"HTTP request failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise KISAPIException(f"Unexpected error during API request: {e}")
    
    def _handle_response(self, response: Dict) -> Dict:
        """
        API 응답 처리 및 에러 체크
        
        Args:
            response: API 응답
            
        Returns:
            처리된 응답 데이터
            
        Raises:
            KISAPIException: API 에러
        """
        # 에러 체크
        rt_cd = response.get("rt_cd", "")
        
        if rt_cd != "0":
            error_msg = response.get("msg1", "Unknown error")
            error_code = response.get("msg_cd", "")
            
            self.logger.error(f"API Error [{rt_cd}]: {error_msg} (Code: {error_code})")
            
            # 에러 타입별 처리
            if "AUTH" in error_code or "TOKEN" in error_code:
                raise AuthenticationError(f"Authentication failed: {error_msg}")
            elif "RATE" in error_code or "LIMIT" in error_code:
                raise RateLimitError(f"Rate limit exceeded: {error_msg}")
            elif "INVALID" in error_code or "PARAM" in error_code:
                raise InvalidRequestError(f"Invalid request: {error_msg}")
            else:
                raise KISAPIException(f"API Error [{rt_cd}]: {error_msg}")
        
        return response
    
    def _format_date(self, date: Optional[Union[str, datetime]] = None) -> str:
        """
        날짜 형식 변환 (YYYYMMDD)
        
        Args:
            date: 날짜 (str, datetime, None)
            
        Returns:
            YYYYMMDD 형식 문자열
        """
        if date is None:
            return datetime.now().strftime("%Y%m%d")
        elif isinstance(date, datetime):
            return date.strftime("%Y%m%d")
        elif isinstance(date, str):
            # 이미 YYYYMMDD 형식인지 체크
            if len(date) == 8 and date.isdigit():
                return date
            # YYYY-MM-DD 형식 처리
            return date.replace("-", "").replace("/", "")
        else:
            raise ValueError(f"Invalid date format: {date}")
    
    def _validate_stock_code(self, code: str) -> bool:
        """
        종목 코드 유효성 검사
        
        Args:
            code: 종목 코드
            
        Returns:
            유효 여부
        """
        if not code or not isinstance(code, str):
            return False
        return True
    
    @abstractmethod
    async def get_current_price(self, code: str, **kwargs) -> Dict:
        """현재가 조회 (시장별 구현 필요)"""
        pass
    
    @abstractmethod
    async def place_order(self, code: str, order_type: str, quantity: int, price: float = 0, **kwargs) -> Dict:
        """주문 실행 (시장별 구현 필요)"""
        pass
    
    @abstractmethod
    async def get_account_balance(self, **kwargs) -> tuple:
        """계좌 잔고 조회 (시장별 구현 필요)"""
        pass