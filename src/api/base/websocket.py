"""
ABOUTME: Base WebSocket client class providing common functionality for real-time data streaming
"""

import asyncio
import json
import logging
import websockets
from abc import ABC, abstractmethod
from typing import Dict, Optional, Callable, Any, Set
from datetime import datetime
from collections import defaultdict

from src.auth.kis_auth import KISAuthManager
from src.api.base.exceptions import (
    WebSocketError,
    WebSocketConnectionError,
    WebSocketSubscriptionError
)


class BaseWebSocketClient(ABC):
    """WebSocket 기본 클라이언트 클래스"""
    
    def __init__(self, auth_manager: KISAuthManager, max_retries: int = 3):
        """
        초기화
        
        Args:
            auth_manager: 인증 관리자
            max_retries: 최대 재시도 횟수
        """
        self.auth_manager = auth_manager
        self.max_retries = max_retries
        self.logger = self._setup_logger()
        
        # WebSocket URL
        self.ws_base_url = self._get_ws_base_url()
        
        # 연결 상태
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.retry_count = 0
        self.approval_key: Optional[str] = None
        
        # 구독 관리
        self.subscriptions: Dict[str, Dict] = {}
        self.data_map: Dict[str, Dict] = {}
        
        # 콜백 함수
        self.callbacks: Dict[str, Optional[Callable]] = {
            "on_quote": None,
            "on_tick": None,
            "on_order": None,
            "on_error": None,
            "on_connect": None,
            "on_disconnect": None
        }
        
        # 메시지 핸들러 태스크
        self._message_handler_task: Optional[asyncio.Task] = None
    
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
    
    def _get_ws_base_url(self) -> str:
        """WebSocket Base URL 반환"""
        import os
        if self.auth_manager.env == "prod":
            return os.getenv("KIS_WS_URL_PROD", "ws://ops.koreainvestment.com:21000")
        else:  # vps
            return os.getenv("KIS_WS_URL_VPS", "ws://ops.koreainvestment.com:31000")
    
    @abstractmethod
    def _get_tr_ids(self) -> Dict[str, Dict[str, str]]:
        """TR_ID 매핑 반환 (시장별 구현 필요)"""
        pass
    
    async def _get_approval_key(self) -> str:
        """WebSocket 접속 승인키 발급"""
        import aiohttp
        
        url = f"{self.auth_manager._get_api_base_url()}/oauth2/Approval"
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self.auth_manager.credentials.app_key,
            "secretkey": self.auth_manager.credentials.app_secret
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status != 200:
                        raise WebSocketConnectionError(f"Failed to get approval key: {response.status}")
                    
                    result = await response.json()
                    if result.get("approval_key"):
                        return result["approval_key"]
                    else:
                        raise WebSocketConnectionError(f"Invalid approval key response: {result}")
        except Exception as e:
            self.logger.error(f"Failed to get approval key: {e}")
            raise WebSocketConnectionError(f"Failed to get approval key: {e}")
    
    async def connect(self) -> bool:
        """
        WebSocket 연결
        
        Returns:
            연결 성공 여부
        """
        if self.is_connected:
            self.logger.info("Already connected")
            return True
        
        try:
            # 승인키 발급
            self.approval_key = await self._get_approval_key()
            self.logger.info(f"Got approval key: {self.approval_key[:20]}...")
            
            # WebSocket 연결
            ws_url = f"{self.ws_base_url}/tryitout"
            self.logger.info(f"Connecting to WebSocket: {ws_url}")
            
            self.websocket = await websockets.connect(ws_url)
            self.is_connected = True
            self.retry_count = 0
            
            self.logger.info(f"WebSocket connected: {ws_url}")
            
            # 메시지 수신 시작
            self._message_handler_task = asyncio.create_task(self._message_handler())
            
            # 연결 콜백 호출
            if self.callbacks.get("on_connect"):
                await self.callbacks["on_connect"]()
            
            return True
            
        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}")
            self.is_connected = False
            raise WebSocketConnectionError(f"WebSocket connection failed: {e}")
    
    async def disconnect(self):
        """WebSocket 연결 해제"""
        self.logger.info("Disconnecting WebSocket...")
        
        # 메시지 핸들러 태스크 취소
        if self._message_handler_task and not self._message_handler_task.done():
            self._message_handler_task.cancel()
            try:
                await self._message_handler_task
            except asyncio.CancelledError:
                pass
        
        # WebSocket 연결 종료
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
        
        self.is_connected = False
        self.websocket = None
        self.approval_key = None
        
        # 연결 해제 콜백 호출
        if self.callbacks.get("on_disconnect"):
            await self.callbacks["on_disconnect"]()
        
        self.logger.info("WebSocket disconnected")
    
    async def _reconnect(self) -> bool:
        """
        재연결 시도
        
        Returns:
            재연결 성공 여부
        """
        if self.retry_count >= self.max_retries:
            self.logger.error(f"Max retries exceeded: {self.max_retries}")
            return False
        
        self.retry_count += 1
        self.logger.warning(f"Reconnecting... ({self.retry_count}/{self.max_retries})")
        
        try:
            await self.disconnect()
            await asyncio.sleep(2 ** self.retry_count)  # 지수 백오프
            await self.connect()
            
            # 기존 구독 복원
            await self._restore_subscriptions()
            
            return True
        except Exception as e:
            self.logger.error(f"Reconnection failed: {e}")
            return False
    
    async def _restore_subscriptions(self):
        """기존 구독 복원"""
        self.logger.info(f"Restoring {len(self.subscriptions)} subscriptions...")
        
        for sub_id, sub_info in self.subscriptions.items():
            try:
                await self._send_subscription_message(
                    tr_id=sub_info["tr_id"],
                    tr_type="1",  # 구독
                    tr_key=sub_info["tr_key"]
                )
                self.logger.info(f"Restored subscription: {sub_id}")
            except Exception as e:
                self.logger.error(f"Failed to restore subscription {sub_id}: {e}")
    
    async def _message_handler(self):
        """메시지 수신 처리 루프"""
        self.logger.info("Message handler started")
        
        try:
            async for message in self.websocket:
                try:
                    await self._process_message(message)
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    if self.callbacks.get("on_error"):
                        await self.callbacks["on_error"](e, message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket connection closed")
            self.is_connected = False
            
            # 재연결 시도
            if await self._reconnect():
                self.logger.info("Reconnection successful")
            else:
                self.logger.error("Reconnection failed")
                if self.callbacks.get("on_error"):
                    await self.callbacks["on_error"](
                        WebSocketConnectionError("Connection lost and reconnection failed"),
                        None
                    )
        
        except Exception as e:
            self.logger.error(f"Message handler error: {e}")
            self.is_connected = False
            if self.callbacks.get("on_error"):
                await self.callbacks["on_error"](e, None)
    
    @abstractmethod
    async def _process_message(self, message: str):
        """메시지 처리 (시장별 구현 필요)"""
        pass
    
    async def _send_subscription_message(self,
                                        tr_id: str,
                                        tr_type: str,
                                        tr_key: str) -> bool:
        """
        구독 메시지 전송
        
        Args:
            tr_id: 거래 ID
            tr_type: 거래 타입 (1: 구독, 2: 구독해제)
            tr_key: 종목 키
            
        Returns:
            전송 성공 여부
        """
        if not self.is_connected or not self.websocket:
            raise WebSocketConnectionError("WebSocket is not connected")
        
        # 메시지 구성
        message = {
            "header": {
                "approval_key": self.approval_key,
                "custtype": "P",
                "tr_type": tr_type,
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": tr_key
                }
            }
        }
        
        try:
            message_str = json.dumps(message)
            self.logger.debug(f"Sending subscription: {tr_id} - {tr_key} ({tr_type})")
            await self.websocket.send(message_str)
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to send subscription message: {e}")
            raise WebSocketSubscriptionError(f"Failed to send subscription: {e}")
    
    def set_callbacks(self, **callbacks):
        """
        콜백 함수 설정
        
        Args:
            **callbacks: 콜백 함수들
                - on_quote: 호가 데이터 콜백
                - on_tick: 체결 데이터 콜백
                - on_order: 주문 체결 콜백
                - on_error: 에러 콜백
                - on_connect: 연결 콜백
                - on_disconnect: 연결 해제 콜백
        """
        for name, callback in callbacks.items():
            if name in self.callbacks:
                self.callbacks[name] = callback
            else:
                self.logger.warning(f"Unknown callback: {name}")
    
    def get_subscriptions(self) -> Dict[str, Dict]:
        """현재 구독 목록 반환"""
        return self.subscriptions.copy()
    
    def get_connection_status(self) -> Dict[str, Any]:
        """연결 상태 반환"""
        return {
            "is_connected": self.is_connected,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "subscription_count": len(self.subscriptions),
            "ws_url": self.ws_base_url
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.disconnect()