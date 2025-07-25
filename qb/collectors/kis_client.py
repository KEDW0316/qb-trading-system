"""
한국투자증권 API 클라이언트
Korean Investment Securities API Client

KIS API 기본 클라이언트 클래스 구현
공식 GitHub 참조: https://github.com/koreainvestment/open-trading-api
"""

import json
import time
import logging
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Optional, Any, List
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from utils.kis_auth import KISAuth


class KISClient:
    """한국투자증권 API 기본 클라이언트 클래스"""
    
    def __init__(self, mode: str = 'paper'):
        """
        KIS 클라이언트 초기화
        
        Args:
            mode: 'prod' (실전투자) 또는 'paper' (모의투자)
        """
        self.logger = logging.getLogger(__name__)
        self.mode = mode.lower()
        
        # KIS 인증 인스턴스 생성
        self.auth = KISAuth(mode=self.mode)
        
        # Rate limiting 관리
        self.request_times: List[float] = []
        self.max_requests_per_sec = 5  # 초당 최대 요청 수
        self.daily_request_count = 0
        self.last_request_day = datetime.now().day
        
        # 기본 타임아웃 설정
        self.default_timeout = 30
        
        self.logger.info(f"KISClient initialized in {self.mode} mode")
    
    async def _manage_rate_limit(self) -> None:
        """API 호출 속도 제한 관리"""
        now = time.time()
        
        # 1초 이내 요청들만 유지
        self.request_times = [t for t in self.request_times if now - t < 1.0]
        
        # 현재 초당 요청 수가 제한에 도달했으면 대기
        if len(self.request_times) >= self.max_requests_per_sec:
            wait_time = 1.0 - (now - self.request_times[0])
            if wait_time > 0:
                self.logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
        
        # 일일 요청 수 관리
        current_day = datetime.now().day
        if current_day != self.last_request_day:
            self.daily_request_count = 0
            self.last_request_day = current_day
        
        self.daily_request_count += 1
        
        # 현재 시간 기록
        self.request_times.append(time.time())
    
    async def request(
        self, 
        method: str, 
        endpoint: str, 
        tr_id: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None, 
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 3
    ) -> Any:
        """
        API 요청 공통 로직 (재시도, 에러 처리 포함)
        
        Args:
            method: HTTP 메소드 (GET, POST, PUT, DELETE)
            endpoint: API 엔드포인트
            tr_id: 거래ID (Transaction ID)
            params: URL 파라미터
            data: 요청 본문 데이터
            headers: 추가 헤더
            retry_count: 재시도 횟수
            
        Returns:
            API 응답 데이터
            
        Raises:
            Exception: API 요청 실패시
        """
        await self._manage_rate_limit()
        
        # 토큰 확인 및 갱신
        token = self.auth.get_token()
        
        # 요청 헤더 구성
        if tr_id:
            request_headers = self.auth.get_trading_headers(tr_id)
        else:
            request_headers = self.auth.get_auth_headers()
        
        if headers:
            request_headers.update(headers)
        
        url = f"{self.auth.base_url}{endpoint}"
        
        # 재시도 로직
        last_exception = None
        
        for attempt in range(retry_count):
            try:
                self.logger.debug(
                    f"Request {attempt + 1}/{retry_count}: {method} {url}"
                    f"{f' (TR_ID: {tr_id})' if tr_id else ''}"
                )
                
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.default_timeout)) as session:
                    request_kwargs = {
                        "headers": request_headers
                    }
                    
                    if params:
                        request_kwargs["params"] = params
                    
                    if data:
                        request_kwargs["json"] = data
                    
                    async with session.request(method, url, **request_kwargs) as response:
                        response_text = await response.text()
                        
                        self.logger.debug(
                            f"Response {response.status}: {response_text[:200]}..."
                        )
                        
                        if response.status == 200:
                            try:
                                return json.loads(response_text)
                            except json.JSONDecodeError:
                                return response_text
                        
                        elif response.status == 401:  # 인증 오류
                            self.logger.warning("Authentication error, refreshing token")
                            # 토큰 재발급 시도
                            try:
                                self.auth._current_token = None  # 현재 토큰 무효화
                                token = self.auth.get_token()  # 새 토큰 발급
                                # 헤더 업데이트
                                if tr_id:
                                    request_headers = self.auth.get_trading_headers(tr_id)
                                else:
                                    request_headers = self.auth.get_auth_headers()
                                if headers:
                                    request_headers.update(headers)
                            except Exception as e:
                                self.logger.error(f"Token refresh failed: {e}")
                            
                            if attempt < retry_count - 1:  # 마지막 시도가 아니면 재시도
                                continue
                        
                        # 기타 HTTP 오류
                        error_msg = f"HTTP {response.status}: {response_text}"
                        self.logger.error(error_msg)
                        last_exception = Exception(error_msg)
                        
                        if attempt < retry_count - 1:
                            continue
                        
            except asyncio.TimeoutError:
                error_msg = f"Request timeout after {self.default_timeout}s"
                self.logger.warning(error_msg)
                last_exception = Exception(error_msg)
                
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt  # 지수 백오프
                    self.logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                    
            except aiohttp.ClientError as e:
                error_msg = f"Client error: {str(e)}"
                self.logger.warning(error_msg)
                last_exception = Exception(error_msg)
                
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt  # 지수 백오프
                    self.logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                    
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                self.logger.error(error_msg)
                last_exception = Exception(error_msg)
                
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    self.logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
        
        # 모든 재시도 실패
        if last_exception:
            raise last_exception
        else:
            raise Exception(f"Request failed after {retry_count} attempts")
    
    @property
    def account_info(self) -> tuple:
        """계좌 정보 반환"""
        return self.auth.account_info
    
    @property
    def is_paper_trading(self) -> bool:
        """모의투자 여부"""
        return self.auth.is_paper_trading()
    
    def get_daily_request_count(self) -> int:
        """일일 요청 수 반환"""
        return self.daily_request_count
    
    def get_current_rate_limit_status(self) -> Dict[str, Any]:
        """현재 rate limit 상태 반환"""
        now = time.time()
        recent_requests = [t for t in self.request_times if now - t < 1.0]
        
        return {
            "requests_last_second": len(recent_requests),
            "max_requests_per_second": self.max_requests_per_sec,
            "daily_request_count": self.daily_request_count,
            "can_make_request": len(recent_requests) < self.max_requests_per_sec
        }
    
    def __str__(self) -> str:
        account_number, account_product = self.account_info
        return f"KISClient(mode={self.mode}, account={account_number}, daily_requests={self.daily_request_count})"
    
    def __repr__(self) -> str:
        return self.__str__()