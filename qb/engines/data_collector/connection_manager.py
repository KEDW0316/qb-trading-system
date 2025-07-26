"""
Connection Manager

연결 관리 및 자동 재연결 로직을 담당하는 컴포넌트
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum


class ConnectionState(Enum):
    """연결 상태"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class ConnectionManager:
    """
    연결 관리자
    
    자동 재연결, 하트비트, 연결 상태 모니터링 담당
    """
    
    def __init__(self, max_retries: int = 5, retry_delay: int = 5, 
                 heartbeat_interval: int = 30, connection_timeout: int = 10):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.heartbeat_interval = heartbeat_interval
        self.connection_timeout = connection_timeout
        
        self.logger = logging.getLogger(__name__)
        
        # 연결 상태
        self.state = ConnectionState.DISCONNECTED
        self.last_connected: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None
        self.retry_count = 0
        
        # 콜백 함수들
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_heartbeat: Optional[Callable] = None
        
        # 비동기 작업
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None
        
        # 통계
        self.stats = {
            'total_connections': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'reconnections': 0,
            'total_uptime_seconds': 0,
            'current_session_start': None
        }
    
    async def connect(self, connect_func: Callable, *args, **kwargs) -> bool:
        """
        연결 수행
        
        Args:
            connect_func: 실제 연결을 수행하는 함수
            *args, **kwargs: connect_func에 전달할 인수들
            
        Returns:
            연결 성공 여부
        """
        if self.state == ConnectionState.CONNECTED:
            self.logger.warning("Already connected")
            return True
        
        self.state = ConnectionState.CONNECTING
        self.stats['total_connections'] += 1
        
        try:
            # 연결 타임아웃 적용
            success = await asyncio.wait_for(
                connect_func(*args, **kwargs),
                timeout=self.connection_timeout
            )
            
            if success:
                self.state = ConnectionState.CONNECTED
                self.last_connected = datetime.now()
                self.retry_count = 0
                self.stats['successful_connections'] += 1
                self.stats['current_session_start'] = datetime.now()
                
                # 하트비트 시작
                self._start_heartbeat()
                
                # 연결 콜백 호출
                if self.on_connected:
                    try:
                        await self.on_connected()
                    except Exception as e:
                        self.logger.error(f"Connection callback error: {e}")
                
                self.logger.info("Connection established successfully")
                return True
            else:
                self.state = ConnectionState.FAILED
                self.stats['failed_connections'] += 1
                self.logger.error("Connection failed")
                return False
                
        except asyncio.TimeoutError:
            self.state = ConnectionState.FAILED
            self.stats['failed_connections'] += 1
            self.logger.error(f"Connection timeout after {self.connection_timeout} seconds")
            return False
        except Exception as e:
            self.state = ConnectionState.FAILED
            self.stats['failed_connections'] += 1
            self.logger.error(f"Connection error: {e}")
            
            # 에러 콜백 호출
            if self.on_error:
                try:
                    await self.on_error(e)
                except Exception as callback_error:
                    self.logger.error(f"Error callback failed: {callback_error}")
            
            return False
    
    async def disconnect(self, disconnect_func: Optional[Callable] = None, *args, **kwargs):
        """
        연결 해제
        
        Args:
            disconnect_func: 실제 연결 해제를 수행하는 함수
            *args, **kwargs: disconnect_func에 전달할 인수들
        """
        if self.state == ConnectionState.DISCONNECTED:
            return
        
        try:
            # 하트비트 중지
            self._stop_heartbeat()
            
            # 재연결 작업 중지
            if self.reconnect_task:
                self.reconnect_task.cancel()
                try:
                    await self.reconnect_task
                except asyncio.CancelledError:
                    pass
                self.reconnect_task = None
            
            # 실제 연결 해제
            if disconnect_func:
                try:
                    await disconnect_func(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Disconnect function error: {e}")
            
            # 상태 업데이트
            prev_state = self.state
            self.state = ConnectionState.DISCONNECTED
            
            # 업타임 통계 업데이트
            if self.stats['current_session_start']:
                session_duration = (datetime.now() - self.stats['current_session_start']).total_seconds()
                self.stats['total_uptime_seconds'] += session_duration
                self.stats['current_session_start'] = None
            
            # 연결 해제 콜백 호출
            if self.on_disconnected and prev_state == ConnectionState.CONNECTED:
                try:
                    await self.on_disconnected()
                except Exception as e:
                    self.logger.error(f"Disconnection callback error: {e}")
            
            self.logger.info("Disconnected successfully")
            
        except Exception as e:
            self.logger.error(f"Disconnect error: {e}")
    
    async def reconnect(self, connect_func: Callable, disconnect_func: Optional[Callable] = None, 
                       *args, **kwargs) -> bool:
        """
        재연결 수행
        
        Args:
            connect_func: 연결 함수
            disconnect_func: 연결 해제 함수
            *args, **kwargs: 함수들에 전달할 인수들
            
        Returns:
            재연결 성공 여부
        """
        if self.state == ConnectionState.RECONNECTING:
            self.logger.warning("Already reconnecting")
            return False
        
        self.state = ConnectionState.RECONNECTING
        self.stats['reconnections'] += 1
        
        # 기존 연결 정리
        await self.disconnect(disconnect_func, *args, **kwargs)
        
        # 재연결 시도
        for attempt in range(self.max_retries):
            self.retry_count = attempt + 1
            
            self.logger.info(f"Reconnection attempt {self.retry_count}/{self.max_retries}")
            
            try:
                success = await self.connect(connect_func, *args, **kwargs)
                if success:
                    self.logger.info("Reconnection successful")
                    return True
                    
            except Exception as e:
                self.logger.error(f"Reconnection attempt {self.retry_count} failed: {e}")
            
            # 마지막 시도가 아니면 대기
            if attempt < self.max_retries - 1:
                wait_time = self.retry_delay * (2 ** attempt)  # 지수 백오프
                self.logger.info(f"Waiting {wait_time} seconds before next attempt")
                await asyncio.sleep(wait_time)
        
        self.state = ConnectionState.FAILED
        self.logger.error(f"Reconnection failed after {self.max_retries} attempts")
        return False
    
    async def auto_reconnect(self, connect_func: Callable, disconnect_func: Optional[Callable] = None,
                            *args, **kwargs):
        """
        자동 재연결 (백그라운드 작업)
        
        Args:
            connect_func: 연결 함수
            disconnect_func: 연결 해제 함수
            *args, **kwargs: 함수들에 전달할 인수들
        """
        if self.reconnect_task and not self.reconnect_task.done():
            self.logger.warning("Auto reconnect already running")
            return
        
        self.reconnect_task = asyncio.create_task(
            self.reconnect(connect_func, disconnect_func, *args, **kwargs)
        )
    
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self.state == ConnectionState.CONNECTED
    
    def is_healthy(self, max_heartbeat_age: int = 60) -> bool:
        """
        연결 건강성 확인
        
        Args:
            max_heartbeat_age: 최대 하트비트 나이 (초)
            
        Returns:
            연결이 건강한지 여부
        """
        if not self.is_connected():
            return False
        
        if self.last_heartbeat:
            age = (datetime.now() - self.last_heartbeat).total_seconds()
            return age <= max_heartbeat_age
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """연결 상태 정보 반환"""
        return {
            'state': self.state.value,
            'is_connected': self.is_connected(),
            'is_healthy': self.is_healthy(),
            'last_connected': self.last_connected.isoformat() if self.last_connected else None,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'retry_count': self.retry_count,
            'stats': self.stats.copy()
        }
    
    def _start_heartbeat(self):
        """하트비트 시작"""
        if self.heartbeat_interval > 0:
            self.heartbeat_task = asyncio.create_task(self._heartbeat_worker())
    
    def _stop_heartbeat(self):
        """하트비트 중지"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
    
    async def _heartbeat_worker(self):
        """하트비트 워커"""
        self.logger.debug("Heartbeat worker started")
        
        try:
            while self.state == ConnectionState.CONNECTED:
                self.last_heartbeat = datetime.now()
                
                # 하트비트 콜백 호출
                if self.on_heartbeat:
                    try:
                        await self.on_heartbeat()
                    except Exception as e:
                        self.logger.error(f"Heartbeat callback error: {e}")
                
                await asyncio.sleep(self.heartbeat_interval)
                
        except asyncio.CancelledError:
            self.logger.debug("Heartbeat worker cancelled")
        except Exception as e:
            self.logger.error(f"Heartbeat worker error: {e}")
    
    def set_callbacks(self, on_connected: Optional[Callable] = None,
                     on_disconnected: Optional[Callable] = None,
                     on_error: Optional[Callable] = None,
                     on_heartbeat: Optional[Callable] = None):
        """콜백 함수들 설정"""
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        self.on_error = on_error
        self.on_heartbeat = on_heartbeat
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            'total_connections': 0,
            'successful_connections': 0,
            'failed_connections': 0,
            'reconnections': 0,
            'total_uptime_seconds': 0,
            'current_session_start': None
        }