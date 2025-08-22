"""
ABOUTME: US stock market WebSocket client for real-time data streaming
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
from src.api.markets.usa.constants import (
    USA_WS_TR_IDS,
    USA_QUOTE_COLUMNS,
    USA_TICK_COLUMNS
)


class USWebSocketClient(BaseWebSocketClient):
    """미국 주식 WebSocket 클라이언트"""
    
    def _get_tr_ids(self) -> Dict[str, Dict[str, str]]:
        """TR_ID 매핑 반환"""
        return {"usa": USA_WS_TR_IDS}
    
    def _get_us_stock_key(self, symbol: str, exchange: str = "NASD", day_trading: bool = False) -> str:
        """
        미국 주식 종목 키 생성
        
        Args:
            symbol: 티커 심볼 (예: AAPL)
            exchange: 거래소 (NASD, NYSE, AMEX)
            day_trading: 주간거래 여부
            
        Returns:
            KIS WebSocket 종목 키 (예: DNASAAPL)
        """
        if day_trading:
            # 주간거래 (10:00~16:00)
            if exchange == "NASD":
                prefix = "RBAQ"
            elif exchange == "NYSE":
                prefix = "RBAY"
            elif exchange == "AMEX":
                prefix = "RBAA"
            else:
                prefix = "RBAQ"  # 기본값
        else:
            # 정규 거래
            if exchange == "NASD":
                prefix = "DNAS"
            elif exchange == "NYSE":
                prefix = "DNYS"
            elif exchange == "AMEX":
                prefix = "DAMS"
            else:
                prefix = "DNAS"  # 기본값
        
        return f"{prefix}{symbol.upper()}"
    
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
                
                # 콜백 호출 (미국 주식)
                if tr_id == "HDFSASP0" and self.callbacks.get("on_quote"):
                    await self.callbacks["on_quote"](df)
                elif tr_id in ["HDFSCNT0", "HDFSCNT2"] and self.callbacks.get("on_tick"):
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
            
            elif sys_msg.tr_id in ["HDFSASP0", "HDFSCNT0", "HDFSCNT2"]:
                # 구독 응답 처리 (미국 주식)
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
                    if sys_msg.tr_id == "HDFSASP0":
                        self.data_map[sys_msg.tr_id]["columns"] = USA_QUOTE_COLUMNS
                    elif sys_msg.tr_id in ["HDFSCNT0", "HDFSCNT2"]:
                        self.data_map[sys_msg.tr_id]["columns"] = USA_TICK_COLUMNS
                    
                    self.logger.info(f"Subscription successful: {sys_msg.tr_id} - {sys_msg.tr_msg}")
                else:
                    self.logger.error(f"Subscription failed: {sys_msg.tr_id} - {sys_msg.tr_msg}")
        
        except Exception as e:
            self.logger.error(f"Error processing system message: {e}")
    
    async def subscribe_quote(self, 
                            symbols: Union[str, List[str]], 
                            exchange: str = "NASD",
                            day_trading: bool = False) -> bool:
        """
        미국 주식 실시간 호가 구독
        
        Args:
            symbols: 티커 심볼 (단일 또는 리스트, 예: "AAPL" 또는 ["AAPL", "TSLA"])
            exchange: 거래소 (NASD, NYSE, AMEX)
            day_trading: 주간거래 여부 (10:00~16:00)
            
        Returns:
            구독 성공 여부
        """
        if not self.is_connected:
            await self.connect()
        
        # 단일 심볼을 리스트로 변환
        if isinstance(symbols, str):
            symbols = [symbols]
        
        success_count = 0
        for symbol in symbols:
            try:
                # 미국 주식 종목 키 생성
                stock_key = self._get_us_stock_key(symbol, exchange, day_trading)
                
                success = await self._send_subscription_message(
                    tr_id=USA_WS_TR_IDS["quote"],
                    tr_type="1",  # 구독
                    tr_key=stock_key
                )
                
                if success:
                    # 구독 정보 저장
                    sub_id = f"us_quote_{symbol}_{exchange}"
                    self.subscriptions[sub_id] = {
                        "tr_id": USA_WS_TR_IDS["quote"],
                        "tr_key": stock_key,
                        "symbol": symbol,
                        "exchange": exchange,
                        "market": "usa",
                        "day_trading": day_trading,
                        "subscribed_at": datetime.now()
                    }
                    success_count += 1
                    self.logger.info(f"Subscribed to US quote: {symbol} ({exchange}) -> {stock_key}")
                
            except Exception as e:
                self.logger.error(f"Failed to subscribe US quote {symbol}: {e}")
        
        return success_count == len(symbols)
    
    async def subscribe_tick(self, 
                           symbols: Union[str, List[str]], 
                           exchange: str = "NASD",
                           day_trading: bool = False,
                           delayed: bool = False) -> bool:
        """
        미국 주식 실시간 체결 구독
        
        Args:
            symbols: 티커 심볼 (단일 또는 리스트)
            exchange: 거래소 (NASD, NYSE, AMEX)
            day_trading: 주간거래 여부
            delayed: 지연시세 사용 여부 (False: 실시간, True: 지연)
            
        Returns:
            구독 성공 여부
        """
        if not self.is_connected:
            await self.connect()
        
        # 단일 심볼을 리스트로 변환
        if isinstance(symbols, str):
            symbols = [symbols]
        
        # TR_ID 선택
        tr_id = USA_WS_TR_IDS["delayed_tick"] if delayed else USA_WS_TR_IDS["tick"]
        
        success_count = 0
        for symbol in symbols:
            try:
                # 미국 주식 종목 키 생성
                stock_key = self._get_us_stock_key(symbol, exchange, day_trading)
                
                success = await self._send_subscription_message(
                    tr_id=tr_id,
                    tr_type="1",  # 구독
                    tr_key=stock_key
                )
                
                if success:
                    # 구독 정보 저장
                    sub_id = f"us_tick_{symbol}_{exchange}" + ("_delayed" if delayed else "")
                    self.subscriptions[sub_id] = {
                        "tr_id": tr_id,
                        "tr_key": stock_key,
                        "symbol": symbol,
                        "exchange": exchange,
                        "market": "usa",
                        "day_trading": day_trading,
                        "delayed": delayed,
                        "subscribed_at": datetime.now()
                    }
                    success_count += 1
                    tick_type = "delayed" if delayed else "realtime"
                    self.logger.info(f"Subscribed to US {tick_type} tick: {symbol} ({exchange}) -> {stock_key}")
                
            except Exception as e:
                self.logger.error(f"Failed to subscribe US tick {symbol}: {e}")
        
        return success_count == len(symbols)
    
    async def unsubscribe(self, 
                         symbol: str, 
                         data_type: str = "all", 
                         exchange: str = "NASD") -> bool:
        """
        미국 주식 구독 해제
        
        Args:
            symbol: 티커 심볼
            data_type: 데이터 타입 ("quote", "tick", "all")
            exchange: 거래소
            
        Returns:
            해제 성공 여부
        """
        success_count = 0
        total_count = 0
        
        # 미국 주식 종목 키 생성
        stock_key = self._get_us_stock_key(symbol, exchange)
        
        if data_type in ["quote", "all"]:
            try:
                success = await self._send_subscription_message(
                    tr_id=USA_WS_TR_IDS["quote"],
                    tr_type="2",  # 구독 해제
                    tr_key=stock_key
                )
                
                if success:
                    sub_id = f"us_quote_{symbol}_{exchange}"
                    if sub_id in self.subscriptions:
                        del self.subscriptions[sub_id]
                    success_count += 1
                    self.logger.info(f"Unsubscribed US quote: {symbol} ({exchange})")
                
                total_count += 1
                
            except Exception as e:
                self.logger.error(f"Failed to unsubscribe US quote {symbol}: {e}")
                total_count += 1
        
        if data_type in ["tick", "all"]:
            # 실시간과 지연 모두 해제 시도
            for delayed in [False, True]:
                try:
                    tr_id = USA_WS_TR_IDS["delayed_tick"] if delayed else USA_WS_TR_IDS["tick"]
                    success = await self._send_subscription_message(
                        tr_id=tr_id,
                        tr_type="2",  # 구독 해제
                        tr_key=stock_key
                    )
                    
                    if success:
                        sub_suffix = "_delayed" if delayed else ""
                        sub_id = f"us_tick_{symbol}_{exchange}{sub_suffix}"
                        if sub_id in self.subscriptions:
                            del self.subscriptions[sub_id]
                        success_count += 1
                        tick_type = "delayed" if delayed else "realtime"
                        self.logger.info(f"Unsubscribed US {tick_type} tick: {symbol} ({exchange})")
                    
                    total_count += 1
                    
                except Exception as e:
                    tick_type = "delayed" if delayed else "realtime"
                    self.logger.error(f"Failed to unsubscribe US {tick_type} tick {symbol}: {e}")
                    total_count += 1
        
        return success_count > 0