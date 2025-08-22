"""
ABOUTME: Korean stock market WebSocket client for real-time data streaming
"""

import json
import pandas as pd
from io import StringIO
from typing import Dict, List, Union, Optional
from datetime import datetime
from collections import namedtuple
from base64 import b64decode

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from src.api.base.websocket import BaseWebSocketClient
from src.api.markets.korea.constants import (
    KOREA_WS_TR_IDS,
    KOREA_QUOTE_COLUMNS,
    KOREA_TICK_COLUMNS
)


class KoreaWebSocketClient(BaseWebSocketClient):
    """한국 주식 WebSocket 클라이언트"""
    
    def _get_tr_ids(self) -> Dict[str, Dict[str, str]]:
        """TR_ID 매핑 반환"""
        return {"korea": KOREA_WS_TR_IDS}
    
    def _aes_cbc_base64_dec(self, key: str, iv: str, cipher_text: str) -> str:
        """AES CBC 복호화"""
        if not key or not iv:
            raise AttributeError("key and iv cannot be None")
        
        cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
        return bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))
    
    def _parse_system_message(self, data: str) -> namedtuple:
        """시스템 메시지 파싱"""
        rdic = json.loads(data)
        
        tr_id = rdic["header"]["tr_id"]
        tr_key = rdic["header"].get("tr_key")
        encrypt = rdic["header"].get("encrypt")
        
        is_pingpong = tr_id == "PINGPONG"
        is_ok = False
        is_unsub = False
        tr_msg = None
        iv = None
        ekey = None
        
        if rdic.get("body"):
            is_ok = rdic["body"]["rt_cd"] == "0"
            tr_msg = rdic["body"]["msg1"]
            
            if "output" in rdic["body"]:
                iv = rdic["body"]["output"].get("iv")
                ekey = rdic["body"]["output"].get("key")
            
            is_unsub = tr_msg and tr_msg.startswith("UNSUB")
        
        SysMsg = namedtuple("SysMsg", [
            "isOk", "tr_id", "tr_key", "isUnSub", "isPingPong", 
            "tr_msg", "iv", "ekey", "encrypt"
        ])
        
        return SysMsg(is_ok, tr_id, tr_key, is_unsub, is_pingpong, tr_msg, iv, ekey, encrypt)
    
    async def _process_message(self, message: str):
        """메시지 처리"""
        self.logger.debug(f"Processing message: {message[:100]}...")
        
        # 실시간 데이터인지 시스템 메시지인지 구분
        if message[0] in ["0", "1"]:
            # 실시간 데이터 처리
            await self._process_realtime_data(message)
        else:
            # 시스템 메시지 처리
            await self._process_system_message(message)
    
    async def _process_realtime_data(self, message: str):
        """실시간 데이터 처리"""
        try:
            parts = message.split("|")
            if len(parts) < 4:
                self.logger.warning(f"Invalid data format: {message}")
                return
            
            tr_id = parts[1]
            data = parts[3]
            
            # 데이터 복호화 (필요한 경우)
            if tr_id in self.data_map:
                data_info = self.data_map[tr_id]
                if data_info.get("encrypt") == "Y":
                    data = self._aes_cbc_base64_dec(
                        data_info["key"], 
                        data_info["iv"], 
                        data
                    )
                
                # CSV 파싱
                df = pd.read_csv(
                    StringIO(data), 
                    header=None, 
                    sep="^", 
                    names=data_info["columns"], 
                    dtype=object
                )
                
                # 콜백 호출
                if tr_id in ["H0STASP0", "H0NXASP0"] and self.callbacks.get("on_quote"):
                    await self.callbacks["on_quote"](df)
                elif tr_id == "H0STCNT0" and self.callbacks.get("on_tick"):
                    await self.callbacks["on_tick"](df)
        
        except Exception as e:
            self.logger.error(f"Error processing realtime data: {e}")
            if self.callbacks.get("on_error"):
                await self.callbacks["on_error"](e, message)
    
    async def _process_system_message(self, message: str):
        """시스템 메시지 처리"""
        try:
            sys_msg = self._parse_system_message(message)
            
            if sys_msg.isPingPong:
                # PING-PONG 응답
                self.logger.debug(f"PING received: {message}")
                await self.websocket.pong(message.encode())
                self.logger.debug(f"PONG sent: {message}")
            
            elif sys_msg.tr_id in ["H0STASP0", "H0STCNT0", "H0NXASP0"]:
                # 구독 응답 처리
                if sys_msg.isOk:
                    # 복호화 키 저장
                    if sys_msg.tr_id not in self.data_map:
                        self.data_map[sys_msg.tr_id] = {}
                    
                    self.data_map[sys_msg.tr_id].update({
                        "encrypt": sys_msg.encrypt,
                        "key": sys_msg.ekey,
                        "iv": sys_msg.iv
                    })
                    
                    # 컬럼 정보 저장
                    if sys_msg.tr_id == "H0STASP0":
                        self.data_map[sys_msg.tr_id]["columns"] = KOREA_QUOTE_COLUMNS
                    elif sys_msg.tr_id == "H0STCNT0":
                        self.data_map[sys_msg.tr_id]["columns"] = KOREA_TICK_COLUMNS
                    elif sys_msg.tr_id == "H0NXASP0":
                        self.data_map[sys_msg.tr_id]["columns"] = KOREA_QUOTE_COLUMNS
                    
                    self.logger.info(f"Subscription successful: {sys_msg.tr_id} - {sys_msg.tr_msg}")
                else:
                    self.logger.error(f"Subscription failed: {sys_msg.tr_id} - {sys_msg.tr_msg}")
        
        except Exception as e:
            self.logger.error(f"Error processing system message: {e}")
    
    async def subscribe_quote(self, 
                            stock_codes: Union[str, List[str]], 
                            exchange: str = "UN") -> bool:
        """
        실시간 호가 구독
        
        Args:
            stock_codes: 종목코드 (단일 또는 리스트)
            exchange: 거래소 구분 (UN: 통합, KRX: 정규장, NXT: 야간거래, SOR: 스마트라우팅)
            
        Returns:
            구독 성공 여부
        """
        if not self.is_connected:
            await self.connect()
        
        # 단일 종목을 리스트로 변환
        if isinstance(stock_codes, str):
            stock_codes = [stock_codes]
        
        # TR_ID 선택 (야간거래 여부에 따라)
        tr_id = KOREA_WS_TR_IDS["night_quote"] if exchange == "NXT" else KOREA_WS_TR_IDS["quote"]
        
        success_count = 0
        for stock_code in stock_codes:
            try:
                success = await self._send_subscription_message(
                    tr_id=tr_id,
                    tr_type="1",  # 구독
                    tr_key=stock_code
                )
                
                if success:
                    # 구독 정보 저장
                    sub_id = f"kr_quote_{stock_code}_{exchange}"
                    self.subscriptions[sub_id] = {
                        "tr_id": tr_id,
                        "tr_key": stock_code,
                        "exchange": exchange,
                        "market": "korea",
                        "subscribed_at": datetime.now()
                    }
                    success_count += 1
                    self.logger.info(f"Subscribed to quote: {stock_code} ({exchange})")
                
            except Exception as e:
                self.logger.error(f"Failed to subscribe quote {stock_code}: {e}")
        
        return success_count == len(stock_codes)
    
    async def subscribe_tick(self, 
                           stock_codes: Union[str, List[str]], 
                           exchange: str = "UN") -> bool:
        """
        실시간 체결 구독
        
        Args:
            stock_codes: 종목코드 (단일 또는 리스트)
            exchange: 거래소 구분
            
        Returns:
            구독 성공 여부
        """
        if not self.is_connected:
            await self.connect()
        
        # 단일 종목을 리스트로 변환
        if isinstance(stock_codes, str):
            stock_codes = [stock_codes]
        
        tr_id = KOREA_WS_TR_IDS["tick"]
        
        success_count = 0
        for stock_code in stock_codes:
            try:
                success = await self._send_subscription_message(
                    tr_id=tr_id,
                    tr_type="1",  # 구독
                    tr_key=stock_code
                )
                
                if success:
                    # 구독 정보 저장
                    sub_id = f"kr_tick_{stock_code}_{exchange}"
                    self.subscriptions[sub_id] = {
                        "tr_id": tr_id,
                        "tr_key": stock_code,
                        "exchange": exchange,
                        "market": "korea",
                        "subscribed_at": datetime.now()
                    }
                    success_count += 1
                    self.logger.info(f"Subscribed to tick: {stock_code} ({exchange})")
                
            except Exception as e:
                self.logger.error(f"Failed to subscribe tick {stock_code}: {e}")
        
        return success_count == len(stock_codes)
    
    async def unsubscribe(self, 
                         stock_code: str, 
                         data_type: str = "all", 
                         exchange: str = "UN") -> bool:
        """
        구독 해제
        
        Args:
            stock_code: 종목코드
            data_type: 데이터 타입 ("quote", "tick", "all")
            exchange: 거래소 구분
            
        Returns:
            해제 성공 여부
        """
        success_count = 0
        total_count = 0
        
        if data_type in ["quote", "all"]:
            try:
                # 일반/야간 호가 모두 시도
                for tr_id in [KOREA_WS_TR_IDS["quote"], KOREA_WS_TR_IDS["night_quote"]]:
                    success = await self._send_subscription_message(
                        tr_id=tr_id,
                        tr_type="2",  # 구독 해제
                        tr_key=stock_code
                    )
                    
                    if success:
                        sub_id = f"kr_quote_{stock_code}_{exchange}"
                        if sub_id in self.subscriptions:
                            del self.subscriptions[sub_id]
                        success_count += 1
                
                total_count += 1
                
            except Exception as e:
                self.logger.error(f"Failed to unsubscribe quote {stock_code}: {e}")
                total_count += 1
        
        if data_type in ["tick", "all"]:
            try:
                success = await self._send_subscription_message(
                    tr_id=KOREA_WS_TR_IDS["tick"],
                    tr_type="2",  # 구독 해제
                    tr_key=stock_code
                )
                
                if success:
                    sub_id = f"kr_tick_{stock_code}_{exchange}"
                    if sub_id in self.subscriptions:
                        del self.subscriptions[sub_id]
                    success_count += 1
                
                total_count += 1
                
            except Exception as e:
                self.logger.error(f"Failed to unsubscribe tick {stock_code}: {e}")
                total_count += 1
        
        return success_count > 0