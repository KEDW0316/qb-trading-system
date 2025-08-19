"""
KIS 인증 관련 설정 및 상수
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class KISAPIConfig:
    """KIS API 설정 상수"""
    
    # API 제한
    DEFAULT_RATE_LIMIT = 18  # 초당 최대 호출 (안전 마진)
    TOKEN_RATE_LIMIT = 1     # 토큰 발급 분당 최대 호출
    
    # 타임아웃 설정
    CONNECT_TIMEOUT = 10     # 연결 타임아웃 (초)
    READ_TIMEOUT = 30        # 읽기 타임아웃 (초)
    TOTAL_TIMEOUT = 60       # 전체 타임아웃 (초)
    
    # 토큰 설정
    TOKEN_EXPIRY_BUFFER = 300  # 만료 5분 전 갱신 (초)
    MAX_TOKEN_RETRIES = 3      # 토큰 발급 최대 재시도
    
    # 파일 경로
    TOKEN_FILE_PREFIX = "kis_token"
    CACHE_DIR = "data/cache"


# API 엔드포인트 상수
ENDPOINTS: Dict[str, Dict[str, str]] = {
    "prod": {
        "base_url": "https://openapi.koreainvestment.com:9443",
        "websocket_url": "wss://ops.koreainvestment.com:21000"
    },
    "vps": {
        "base_url": "https://openapivts.koreainvestment.com:29443", 
        "websocket_url": "wss://ops.koreainvestment.com:31000"
    }
}

# HTTP 헤더 템플릿
COMMON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "KIS-Auto-Trading/1.0"
}