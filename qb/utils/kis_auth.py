"""
한국투자증권 Open API 인증 시스템
Korean Investment Securities Open API Authentication System

공식 GitHub 참조: https://github.com/koreainvestment/open-trading-api
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

# 환경변수 로딩을 위한 python-dotenv (선택사항)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class KISCredentials:
    """KIS API 인증 정보"""
    app_key: str
    app_secret: str
    account_number: str
    account_product: str
    hts_id: str
    user_agent: str


@dataclass 
class KISToken:
    """KIS API 토큰 정보"""
    access_token: str
    token_type: str
    expires_at: datetime
    
    @property
    def is_expired(self) -> bool:
        """토큰 만료 여부 확인"""
        return datetime.now() >= self.expires_at
        
    def is_near_expiry(self, minutes: int = 30) -> bool:
        """토큰이 곧 만료되는지 확인 (기본: 30분 전)"""
        return datetime.now() >= (self.expires_at - timedelta(minutes=minutes))


class KISAuth:
    """한국투자증권 API 인증 관리자"""
    
    # API 도메인 정보
    DOMAINS = {
        'prod': {
            'rest': 'https://openapi.koreainvestment.com:9443',
            'websocket': 'ws://ops.koreainvestment.com:21000'
        },
        'paper': {
            'rest': 'https://openapivts.koreainvestment.com:29443', 
            'websocket': 'ws://ops.koreainvestment.com:31000'
        }
    }
    
    def __init__(self, mode: str = 'paper', token_cache_dir: Optional[str] = None):
        """
        KIS 인증 관리자 초기화
        
        Args:
            mode: 'prod' (실전투자) 또는 'paper' (모의투자)
            token_cache_dir: 토큰 캐시 디렉토리 (기본: ~/.qb/tokens/)
        """
        self.logger = logging.getLogger(__name__)
        self.mode = mode.lower()
        
        if self.mode not in ['prod', 'paper']:
            raise ValueError("mode must be 'prod' or 'paper'")
        
        # 토큰 캐시 디렉토리 설정
        if token_cache_dir is None:
            token_cache_dir = os.path.expanduser("~/.qb/tokens/")
        
        self.token_cache_dir = Path(token_cache_dir)
        self.token_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 토큰 캐시 파일 경로
        self.token_file = self.token_cache_dir / f"kis_token_{self.mode}_{datetime.now().strftime('%Y%m%d')}.json"
        
        # 인증 정보 로드
        self.credentials = self._load_credentials()
        
        # 현재 토큰
        self._current_token: Optional[KISToken] = None
        
        # 기본 헤더
        self.base_headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain", 
            "charset": "UTF-8",
            "User-Agent": self.credentials.user_agent
        }
        
        self.logger.info(f"KIS Auth initialized in {self.mode} mode")
    
    def _load_credentials(self) -> KISCredentials:
        """환경변수에서 인증 정보 로드"""
        
        # 모드에 따른 환경변수 접두어
        prefix = 'KIS_PAPER_' if self.mode == 'paper' else 'KIS_'
        account_prefix = 'KIS_PAPER_' if self.mode == 'paper' else 'KIS_'
        
        app_key = os.getenv(f'{prefix}APP_KEY')
        app_secret = os.getenv(f'{prefix}APP_SECRET')
        account_number = os.getenv(f'{account_prefix}ACCOUNT_STOCK')
        account_product = os.getenv('KIS_ACCOUNT_PRODUCT', '01')
        hts_id = os.getenv('KIS_HTS_ID')
        user_agent = os.getenv('KIS_USER_AGENT', 
                              'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # 필수 값 검증
        missing = []
        if not app_key:
            missing.append(f'{prefix}APP_KEY')
        if not app_secret:
            missing.append(f'{prefix}APP_SECRET')
        if not account_number:
            missing.append(f'{account_prefix}ACCOUNT_STOCK')
        if not hts_id:
            missing.append('KIS_HTS_ID')
            
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return KISCredentials(
            app_key=app_key,
            app_secret=app_secret,
            account_number=account_number,
            account_product=account_product,
            hts_id=hts_id,
            user_agent=user_agent
        )
    
    def _save_token(self, token: KISToken) -> None:
        """토큰을 파일에 저장"""
        try:
            token_data = {
                'access_token': token.access_token,
                'token_type': token.token_type,
                'expires_at': token.expires_at.isoformat()
            }
            
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump(token_data, f, ensure_ascii=False, indent=2)
                
            self.logger.debug(f"Token saved to {self.token_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save token: {e}")
    
    def _load_token(self) -> Optional[KISToken]:
        """파일에서 토큰 로드"""
        try:
            if not self.token_file.exists():
                return None
                
            with open(self.token_file, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
                
            expires_at = datetime.fromisoformat(token_data['expires_at'])
            
            token = KISToken(
                access_token=token_data['access_token'],
                token_type=token_data['token_type'],
                expires_at=expires_at
            )
            
            # 만료된 토큰이면 None 반환
            if token.is_expired:
                self.logger.debug("Cached token is expired")
                return None
                
            self.logger.debug("Token loaded from cache")
            return token
            
        except Exception as e:
            self.logger.error(f"Failed to load token: {e}")
            return None
    
    def _request_new_token(self) -> KISToken:
        """새 토큰 발급 요청"""
        url = f"{self.DOMAINS[self.mode]['rest']}/oauth2/tokenP"
        
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.credentials.app_key,
            "appsecret": self.credentials.app_secret
        }
        
        try:
            self.logger.info("Requesting new access token...")
            
            response = requests.post(
                url, 
                data=json.dumps(payload),
                headers=self.base_headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Token request failed: {response.status_code} - {response.text}")
            
            result = response.json()
            
            # 응답 검증
            if 'access_token' not in result:
                raise Exception(f"Invalid token response: {result}")
            
            # 만료 시간 파싱 (예: "2024-01-25 23:59:59")
            expires_str = result.get('access_token_token_expired', '')
            try:
                expires_at = datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # 파싱 실패 시 24시간 후로 설정
                expires_at = datetime.now() + timedelta(hours=24)
                
            token = KISToken(
                access_token=result['access_token'],
                token_type=result.get('token_type', 'Bearer'),
                expires_at=expires_at
            )
            
            self.logger.info(f"New token acquired, expires at: {expires_at}")
            
            # 토큰 저장
            self._save_token(token)
            
            return token
            
        except Exception as e:
            self.logger.error(f"Failed to get new token: {e}")
            raise
    
    def get_token(self) -> KISToken:
        """현재 유효한 토큰 반환 (필요시 자동 갱신)"""
        
        # 캐시된 토큰이 있고 유효하면 반환
        if self._current_token and not self._current_token.is_near_expiry():
            return self._current_token
        
        # 파일에서 토큰 로드 시도
        self._current_token = self._load_token()
        
        # 토큰이 없거나 만료 예정이면 새로 발급
        if not self._current_token or self._current_token.is_near_expiry():
            self._current_token = self._request_new_token()
        
        return self._current_token
    
    def get_auth_headers(self) -> Dict[str, str]:
        """인증 헤더 반환"""
        token = self.get_token()
        
        headers = self.base_headers.copy()
        headers.update({
            "authorization": f"{token.token_type} {token.access_token}",
            "appkey": self.credentials.app_key,
            "appsecret": self.credentials.app_secret
        })
        
        return headers
    
    def get_trading_headers(self, tr_id: str, tr_cont: str = "") -> Dict[str, str]:
        """거래용 헤더 반환 (TR ID 포함)"""
        headers = self.get_auth_headers()
        
        # 모의투자인 경우 TR ID 변환 (T/J/C -> V)
        if self.mode == 'paper' and tr_id and tr_id[0] in ('T', 'J', 'C'):
            tr_id = 'V' + tr_id[1:]
        
        headers.update({
            "tr_id": tr_id,
            "custtype": "P",  # 일반 고객
            "tr_cont": tr_cont
        })
        
        return headers
    
    def get_websocket_headers(self) -> Dict[str, str]:
        """웹소켓용 헤더 반환"""
        # 웹소켓은 별도 승인키 필요
        url = f"{self.DOMAINS[self.mode]['rest']}/oauth2/Approval"
        
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.credentials.app_key,
            "secretkey": self.credentials.app_secret  # 웹소켓은 secretkey 사용
        }
        
        try:
            response = requests.post(
                url,
                data=json.dumps(payload),
                headers=self.base_headers,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Websocket approval failed: {response.status_code}")
            
            result = response.json()
            approval_key = result.get('approval_key')
            
            if not approval_key:
                raise Exception("No approval key in response")
            
            return {
                "content-type": "utf-8",
                "approval_key": approval_key
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get websocket headers: {e}")
            raise
    
    @property
    def base_url(self) -> str:
        """기본 REST API URL"""
        return self.DOMAINS[self.mode]['rest']
    
    @property 
    def websocket_url(self) -> str:
        """웹소켓 URL"""
        return self.DOMAINS[self.mode]['websocket']
    
    @property
    def account_info(self) -> Tuple[str, str]:
        """계좌 정보 (계좌번호, 상품코드) 튜플 반환"""
        return self.credentials.account_number, self.credentials.account_product
    
    def is_paper_trading(self) -> bool:
        """모의투자 여부"""
        return self.mode == 'paper'
    
    def get_hash_key(self, order_data: Dict[str, Any]) -> Optional[str]:
        """주문 해시키 발급 (선택사항)"""
        url = f"{self.base_url}/uapi/hashkey"
        
        try:
            headers = self.get_auth_headers()
            response = requests.post(
                url,
                data=json.dumps(order_data),
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('HASH')
            else:
                self.logger.warning(f"Hash key request failed: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get hash key: {e}")
            return None
    
    def __str__(self) -> str:
        return f"KISAuth(mode={self.mode}, account={self.credentials.account_number})"
    
    def __repr__(self) -> str:
        return self.__str__()


# 전역 인스턴스 (편의성을 위한)
_auth_instance: Optional[KISAuth] = None


def get_auth(mode: Optional[str] = None) -> KISAuth:
    """전역 KIS 인증 인스턴스 반환"""
    global _auth_instance
    
    if _auth_instance is None or (mode and _auth_instance.mode != mode):
        if mode is None:
            mode = os.getenv('KIS_MODE', 'paper')
        _auth_instance = KISAuth(mode=mode)
    
    return _auth_instance


def set_auth_mode(mode: str) -> KISAuth:
    """인증 모드 변경"""
    global _auth_instance
    _auth_instance = KISAuth(mode=mode)
    return _auth_instance