"""
KIS API WebSocket Handler
실시간 데이터 수신을 위한 WebSocket 클라이언트
"""

import asyncio
import json
import logging
import websockets
from base64 import b64decode
from io import StringIO
from typing import Dict, List, Optional, Callable, Any, Tuple, Union
from datetime import datetime
from collections import namedtuple
import pandas as pd

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from src.auth.kis_auth import KISAuthManager


class Market:
    """시장 구분"""
    KOREA = "KR"
    USA = "US"


class USExchange:
    """미국 거래소 코드"""
    NASDAQ = "NAS"
    NYSE = "NYS" 
    AMEX = "AMS"
    # 주간거래
    NASDAQ_DAY = "BAQ"
    NYSE_DAY = "BAY"
    AMEX_DAY = "BAA"


class KISWebSocketHandler:
    """KIS API WebSocket 클라이언트"""
    
    def __init__(self, auth_manager: KISAuthManager, max_retries: int = 3):
        """
        초기화
        Args:
            auth_manager: 인증 관리자
            max_retries: 최대 재시도 횟수
        """
        self.auth_manager = auth_manager
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        
        # WebSocket URL
        self.ws_base_url = self._get_ws_base_url()
        
        # 구독 관리
        self.subscriptions = {}  # 구독 정보 저장
        self.data_map = {}       # 데이터 컬럼 매핑
        
        # TR_ID 매핑
        self.tr_ids = {
            "korea": {
                "quote": "H0STASP0",      # 실시간 호가
                "tick": "H0STCNT0",       # 실시간 체결
                "night_quote": "H0NXASP0" # 야간 호가
            },
            "usa": {
                "quote": "HDFSASP0",      # 실시간 호가 (1호가 무료)
                "tick": "HDFSCNT0",       # 실시간 체결 (무료)
                "delayed_tick": "HDFSCNT2", # 지연 체결
                "notice": "H0GSCNI0"      # 체결 통보
            }
        }
        
        # 연결 상태
        self.websocket = None
        self.is_connected = False
        self.retry_count = 0
        self.approval_key = None
        
        # 콜백 함수
        self.on_quote_callback: Optional[Callable] = None
        self.on_tick_callback: Optional[Callable] = None
        self.on_error_callback: Optional[Callable] = None
    
    def _get_ws_base_url(self) -> str:
        """WebSocket Base URL 반환"""
        import os
        if self.auth_manager.env == "prod":
            return os.getenv("KIS_WS_URL_PROD", "ws://ops.koreainvestment.com:21000")
        else:  # vps
            return os.getenv("KIS_WS_URL_VPS", "ws://ops.koreainvestment.com:31000")
    
    def _is_korean_stock_code(self, symbol: str) -> bool:
        """한국 주식 코드인지 확인 (6자리 숫자)"""
        return len(symbol) == 6 and symbol.isdigit()
    
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
    
    def _detect_market(self, symbol: str) -> str:
        """시장 자동 감지"""
        if self._is_korean_stock_code(symbol):
            return "korea"
        else:
            return "usa"
    
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
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"승인키 발급 실패: {response.status}")
                
                result = await response.json()
                if result.get("approval_key"):
                    return result["approval_key"]
                else:
                    raise Exception(f"승인키 발급 실패: {result}")
    
    async def connect(self):
        """WebSocket 연결"""
        if self.is_connected:
            return True
        
        try:
            # 승인키 발급
            approval_key = await self._get_approval_key()
            self.logger.info(f"승인키 발급 완료: {approval_key[:20]}...")
            
            # KIS WebSocket 연결 (레퍼런스 코드 기준)
            ws_url = f"{self.ws_base_url}/tryitout"
            
            self.logger.info(f"WebSocket 연결 시도: {ws_url}")
            
            # WebSocket 연결 (레퍼런스와 동일하게 헤더 없이 연결 후 승인키 저장)
            self.websocket = await websockets.connect(ws_url)
            self.is_connected = True
            self.retry_count = 0
            
            # 승인키 저장 (메시지 전송 시 사용)
            self.approval_key = approval_key
            
            self.logger.info(f"WebSocket 연결 성공: {ws_url}")
            
            # 메시지 수신 시작
            asyncio.create_task(self._message_handler())
            return True
            
        except Exception as e:
            self.logger.error(f"WebSocket 연결 실패: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """WebSocket 연결 해제"""
        if self.websocket and not getattr(self.websocket, 'closed', True):
            await self.websocket.close()
        
        self.is_connected = False
        self.websocket = None
        self.logger.info("WebSocket 연결 해제됨")
    
    async def _reconnect(self):
        """재연결 시도"""
        if self.retry_count >= self.max_retries:
            self.logger.error(f"최대 재시도 횟수 초과: {self.max_retries}")
            return False
        
        self.retry_count += 1
        self.logger.warning(f"재연결 시도 중... ({self.retry_count}/{self.max_retries})")
        
        try:
            await self.disconnect()
            await asyncio.sleep(2 ** self.retry_count)  # 지수 백오프
            await self.connect()
            
            # 기존 구독 복원
            await self._restore_subscriptions()
            
            return True
        except Exception as e:
            self.logger.error(f"재연결 실패: {e}")
            return False
    
    async def _restore_subscriptions(self):
        """기존 구독 복원"""
        for sub_id, sub_info in self.subscriptions.items():
            try:
                await self._send_subscription_message(
                    tr_id=sub_info["tr_id"],
                    tr_type="1",  # 구독
                    stock_code=sub_info["stock_code"],
                    exchange=sub_info["exchange"]
                )
                self.logger.info(f"구독 복원됨: {sub_id}")
            except Exception as e:
                self.logger.error(f"구독 복원 실패 {sub_id}: {e}")
    
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
    
    async def _message_handler(self):
        """메시지 수신 처리"""
        self.logger.info("메시지 핸들러 시작됨")
        try:
            async for message in self.websocket:
                self.logger.debug(f"수신된 메시지: {message[:100]}...")  # 처음 100자만 로깅
                try:
                    await self._process_message(message)
                except Exception as e:
                    self.logger.error(f"메시지 처리 오류: {e}")
                    if self.on_error_callback:
                        await self.on_error_callback(e, message)
        
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket 연결 끊김")
            self.is_connected = False
            
            # 재연결 시도
            if await self._reconnect():
                self.logger.info("재연결 성공")
            else:
                self.logger.error("재연결 실패")
        
        except Exception as e:
            self.logger.error(f"메시지 핸들러 오류: {e}")
            self.is_connected = False
            if self.on_error_callback:
                await self.on_error_callback(e, None)
    
    async def _process_message(self, message: str):
        """개별 메시지 처리"""
        self.logger.info(f"메시지 타입 확인: 첫 문자='{message[0]}', 길이={len(message)}")
        
        # 실시간 데이터인지 시스템 메시지인지 구분
        if message[0] in ["0", "1"]:
            # 실시간 데이터 처리
            self.logger.info(f"실시간 데이터 수신: {message[:100]}...")
            await self._process_realtime_data(message)
        else:
            # 시스템 메시지 처리
            await self._process_system_message(message)
    
    async def _process_realtime_data(self, message: str):
        """실시간 데이터 처리"""
        try:
            parts = message.split("|")
            if len(parts) < 4:
                self.logger.warning(f"잘못된 데이터 형식: {message}")
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
                
                # 콜백 호출 (한국 + 미국 주식)
                if tr_id in ["H0STASP0", "H0NXASP0", "HDFSASP0"] and self.on_quote_callback:
                    await self.on_quote_callback(df)
                elif tr_id in ["H0STCNT0", "HDFSCNT0", "HDFSCNT2"] and self.on_tick_callback:
                    await self.on_tick_callback(df)
        
        except Exception as e:
            self.logger.error(f"실시간 데이터 처리 오류: {e}")
            if self.on_error_callback:
                await self.on_error_callback(e, message)
    
    async def _process_system_message(self, message: str):
        """시스템 메시지 처리"""
        try:
            sys_msg = self._parse_system_message(message)
            
            if sys_msg.isPingPong:
                # PING-PONG 응답
                self.logger.debug(f"PING 수신: {message}")
                await self.websocket.pong(message.encode())
                self.logger.debug(f"PONG 발송: {message}")
            
            elif sys_msg.tr_id in ["H0STASP0", "H0STCNT0", "H0NXASP0", "HDFSASP0", "HDFSCNT0", "HDFSCNT2"]:
                # 구독 응답 처리 (한국 + 미국 주식)
                if sys_msg.isOk:
                    # 복호화 키 저장
                    if sys_msg.tr_id not in self.data_map:
                        self.data_map[sys_msg.tr_id] = {}
                    
                    self.data_map[sys_msg.tr_id].update({
                        "encrypt": sys_msg.encrypt,
                        "key": sys_msg.ekey,
                        "iv": sys_msg.iv
                    })
                    
                    self.logger.info(f"구독 성공: {sys_msg.tr_id} - {sys_msg.tr_msg}")
                else:
                    self.logger.error(f"구독 실패: {sys_msg.tr_id} - {sys_msg.tr_msg}")
        
        except Exception as e:
            self.logger.error(f"시스템 메시지 처리 오류: {e}")
    
    async def _send_subscription_message(self, 
                                       tr_id: str, 
                                       tr_type: str, 
                                       stock_code: str,
                                       exchange: str = "UN") -> bool:
        """구독 메시지 전송"""
        if not self.is_connected or not self.websocket:
            raise Exception("WebSocket이 연결되지 않음")
        
        # 저장된 승인키 사용 (connect 시 발급받은 것)
        approval_key = self.approval_key
        if not approval_key:
            approval_key = await self._get_approval_key()
        
        # KIS WebSocket 메시지 구성 (레퍼런스 형식)
        message = {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": tr_type,
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": stock_code
                }
            }
        }
        
        self.logger.info(f"구독 메시지 전송: {tr_id} - {stock_code} ({tr_type})")
        
        # 컬럼 정보 저장
        if tr_id not in self.data_map:
            self.data_map[tr_id] = {}
        
        # 한국 주식 컬럼 매핑
        if tr_id == "H0STASP0":
            # 실시간 호가 컬럼
            self.data_map[tr_id]["columns"] = [
                "MKSC_SHRN_ISCD", "BSOP_HOUR", "HOUR_CLS_CODE",
                "ASKP1", "ASKP2", "ASKP3", "ASKP4", "ASKP5",
                "ASKP6", "ASKP7", "ASKP8", "ASKP9", "ASKP10",
                "BIDP1", "BIDP2", "BIDP3", "BIDP4", "BIDP5",
                "BIDP6", "BIDP7", "BIDP8", "BIDP9", "BIDP10",
                "ASKP_RSQN1", "ASKP_RSQN2", "ASKP_RSQN3", "ASKP_RSQN4", "ASKP_RSQN5",
                "ASKP_RSQN6", "ASKP_RSQN7", "ASKP_RSQN8", "ASKP_RSQN9", "ASKP_RSQN10",
                "BIDP_RSQN1", "BIDP_RSQN2", "BIDP_RSQN3", "BIDP_RSQN4", "BIDP_RSQN5",
                "BIDP_RSQN6", "BIDP_RSQN7", "BIDP_RSQN8", "BIDP_RSQN9", "BIDP_RSQN10",
                "TOTAL_ASKP_RSQN", "TOTAL_BIDP_RSQN", "OVTM_TOTAL_ASKP_RSQN", "OVTM_TOTAL_BIDP_RSQN",
                "ANTC_CNPR", "ANTC_CNQN", "ANTC_VOL", "ANTC_CNTG_VRSS", "ANTC_CNTG_VRSS_SIGN",
                "ANTC_CNTG_PRDY_CTRT", "ACML_VOL", "TOTAL_ASKP_RSQN_ICDC", "TOTAL_BIDP_RSQN_ICDC",
                "OVTM_TOTAL_ASKP_ICDC", "OVTM_TOTAL_BIDP_ICDC", "STCK_DEAL_CLS_CODE"
            ]
        elif tr_id == "H0STCNT0":
            # 실시간 체결 컬럼
            self.data_map[tr_id]["columns"] = [
                "MKSC_SHRN_ISCD", "STCK_CNTG_HOUR", "STCK_PRPR", "PRDY_VRSS_SIGN",
                "PRDY_VRSS", "PRDY_CTRT", "WGHN_AVRG_STCK_PRC", "STCK_OPRC",
                "STCK_HGPR", "STCK_LWPR", "ASKP1", "BIDP1", "CNTG_VOL", "ACML_VOL",
                "ACML_TR_PBMN", "SELN_CNTG_CSNU", "SHNU_CNTG_CSNU", "NTBY_CNTG_CSNU",
                "CTTR", "SELN_CNTG_SMTN", "SHNU_CNTG_SMTN", "CCLD_DVSN", "SHNU_RATE",
                "PRDY_VOL_VRSS_ACML_VOL_RATE", "OPRC_HOUR", "OPRC_VRSS_PRPR_SIGN",
                "OPRC_VRSS_PRPR", "HGPR_HOUR", "HGPR_VRSS_PRPR_SIGN", "HGPR_VRSS_PRPR",
                "LWPR_HOUR", "LWPR_VRSS_PRPR_SIGN", "LWPR_VRSS_PRPR", "BSOP_DATE",
                "NEW_MKOP_CLS_CODE", "TRHT_YN", "ASKP_RSQN1", "BIDP_RSQN1",
                "TOTAL_ASKP_RSQN", "TOTAL_BIDP_RSQN", "VOL_TNRT",
                "PRDY_SMNS_HOUR_ACML_VOL", "PRDY_SMNS_HOUR_ACML_VOL_RATE",
                "HOUR_CLS_CODE", "MRKT_TRTM_CLS_CODE", "VI_STND_PRC"
            ]
        elif tr_id == "H0NXASP0":
            # 실시간 야간 호가 컬럼 (NXT)
            self.data_map[tr_id]["columns"] = [
                "MKSC_SHRN_ISCD", "BSOP_HOUR", "HOUR_CLS_CODE",
                "ASKP1", "ASKP2", "ASKP3", "ASKP4", "ASKP5",
                "ASKP6", "ASKP7", "ASKP8", "ASKP9", "ASKP10",
                "BIDP1", "BIDP2", "BIDP3", "BIDP4", "BIDP5",
                "BIDP6", "BIDP7", "BIDP8", "BIDP9", "BIDP10",
                "ASKP_RSQN1", "ASKP_RSQN2", "ASKP_RSQN3", "ASKP_RSQN4", "ASKP_RSQN5",
                "ASKP_RSQN6", "ASKP_RSQN7", "ASKP_RSQN8", "ASKP_RSQN9", "ASKP_RSQN10",
                "BIDP_RSQN1", "BIDP_RSQN2", "BIDP_RSQN3", "BIDP_RSQN4", "BIDP_RSQN5",
                "BIDP_RSQN6", "BIDP_RSQN7", "BIDP_RSQN8", "BIDP_RSQN9", "BIDP_RSQN10",
                "TOTAL_ASKP_RSQN", "TOTAL_BIDP_RSQN", "OVTM_TOTAL_ASKP_RSQN", "OVTM_TOTAL_BIDP_RSQN",
                "ANTC_CNPR", "ANTC_CNQN", "ANTC_VOL", "ANTC_CNTG_VRSS", "ANTC_CNTG_VRSS_SIGN",
                "ANTC_CNTG_PRDY_CTRT", "ACML_VOL", "TOTAL_ASKP_RSQN_ICDC", "TOTAL_BIDP_RSQN_ICDC",
                "OVTM_TOTAL_ASKP_ICDC", "OVTM_TOTAL_BIDP_ICDC", "STCK_DEAL_CLS_CODE"
            ]
        
        # 미국 주식 컬럼 매핑
        elif tr_id == "HDFSASP0":
            # 미국 주식 실시간 호가 컬럼 (1호가만 무료)
            self.data_map[tr_id]["columns"] = [
                "symb",      # 종목코드
                "zdiv",      # 소수점자리수
                "xymd",      # 현지거래일자
                "xhms",      # 현지거래시간
                "kymd",      # 한국거래일자
                "khms",      # 한국거래시간
                "bvol",      # 매수호가수량총계
                "avol",      # 매도호가수량총계
                "bdvl",      # 매수호가금액총계
                "advl",      # 매도호가금액총계
                "pbid1",     # 매수호가1
                "pask1",     # 매도호가1
                "vbid1",     # 매수호가수량1
                "vask1",     # 매도호가수량1
                "dbid1",     # 매수호가건수1
                "dask1"      # 매도호가건수1
            ]
        elif tr_id == "HDFSCNT0":
            # 미국 주식 실시간 체결 컬럼 (무료)
            self.data_map[tr_id]["columns"] = [
                "symb",      # 종목코드
                "zdiv",      # 소수점자리수
                "xymd",      # 현지거래일자
                "xhms",      # 현지거래시간
                "kymd",      # 한국거래일자
                "khms",      # 한국거래시간
                "last",      # 현재가
                "base",      # 전일종가
                "diff",      # 대비
                "rate",      # 등락률
                "sign",      # 대비기호
                "tvol",      # 거래량
                "tamt",      # 거래대금
                "ordy"       # 매수가능여부
            ]
        elif tr_id == "HDFSCNT2":
            # 미국 주식 지연 체결 컬럼 (지연시세)
            self.data_map[tr_id]["columns"] = [
                "symb",      # 종목코드
                "zdiv",      # 소수점자리수
                "xymd",      # 현지거래일자
                "xhms",      # 현지거래시간
                "kymd",      # 한국거래일자
                "khms",      # 한국거래시간
                "last",      # 현재가
                "base",      # 전일종가
                "diff",      # 대비
                "rate",      # 등락률
                "sign",      # 대비기호
                "tvol",      # 거래량
                "tamt",      # 거래대금
                "ordy"       # 매수가능여부
            ]
        
        # 메시지 전송
        try:
            message_str = json.dumps(message)
            self.logger.info(f"전송할 메시지: {message_str}")
            await self.websocket.send(message_str)
            self.logger.info(f"구독 메시지 전송 완료: {tr_id} - {stock_code}")
            return True
        
        except Exception as e:
            self.logger.error(f"구독 메시지 전송 실패: {e}")
            return False
    
    async def subscribe_quote(self, 
                            stock_codes: Union[str, List[str]], 
                            exchange: str = "UN") -> bool:
        """
        실시간 호가 구독 (H0STASP0)
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
        
        success_count = 0
        for stock_code in stock_codes:
            try:
                success = await self._send_subscription_message(
                    tr_id="H0STASP0",
                    tr_type="1",  # 구독
                    stock_code=stock_code,
                    exchange=exchange
                )
                
                if success:
                    # 구독 정보 저장
                    sub_id = f"quote_{stock_code}_{exchange}"
                    self.subscriptions[sub_id] = {
                        "tr_id": "H0STASP0",
                        "stock_code": stock_code,
                        "exchange": exchange,
                        "subscribed_at": datetime.now()
                    }
                    success_count += 1
                    self.logger.info(f"실시간 호가 구독: {stock_code} ({exchange})")
                
                # 연속 요청 간격
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"실시간 호가 구독 실패 {stock_code}: {e}")
        
        return success_count == len(stock_codes)
    
    async def subscribe_tick(self, 
                           stock_codes: Union[str, List[str]], 
                           exchange: str = "UN") -> bool:
        """
        실시간 체결 구독 (H0STCNT0)
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
        
        success_count = 0
        for stock_code in stock_codes:
            try:
                success = await self._send_subscription_message(
                    tr_id="H0NXASP0",
                    tr_type="1",  # 구독
                    stock_code=stock_code,
                    exchange=exchange
                )
                
                if success:
                    # 구독 정보 저장
                    sub_id = f"tick_{stock_code}_{exchange}"
                    self.subscriptions[sub_id] = {
                        "tr_id": "H0NXASP0",
                        "stock_code": stock_code,
                        "exchange": exchange,
                        "subscribed_at": datetime.now()
                    }
                    success_count += 1
                    self.logger.info(f"실시간 체결 구독: {stock_code} ({exchange})")
                
                # 연속 요청 간격
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"실시간 체결 구독 실패 {stock_code}: {e}")
        
        return success_count == len(stock_codes)
    
    async def unsubscribe(self, stock_code: str, data_type: str = "all", exchange: str = "UN") -> bool:
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
                success = await self._send_subscription_message(
                    tr_id="H0STASP0",
                    tr_type="2",  # 구독 해제
                    stock_code=stock_code,
                    exchange=exchange
                )
                
                if success:
                    sub_id = f"quote_{stock_code}_{exchange}"
                    if sub_id in self.subscriptions:
                        del self.subscriptions[sub_id]
                    success_count += 1
                    self.logger.info(f"실시간 호가 구독 해제: {stock_code} ({exchange})")
                
                total_count += 1
                
            except Exception as e:
                self.logger.error(f"실시간 호가 구독 해제 실패 {stock_code}: {e}")
                total_count += 1
        
        if data_type in ["tick", "all"]:
            try:
                success = await self._send_subscription_message(
                    tr_id="H0NXASP0",
                    tr_type="2",  # 구독 해제
                    stock_code=stock_code,
                    exchange=exchange
                )
                
                if success:
                    sub_id = f"tick_{stock_code}_{exchange}"
                    if sub_id in self.subscriptions:
                        del self.subscriptions[sub_id]
                    success_count += 1
                    self.logger.info(f"실시간 체결 구독 해제: {stock_code} ({exchange})")
                
                total_count += 1
                
            except Exception as e:
                self.logger.error(f"실시간 체결 구독 해제 실패 {stock_code}: {e}")
                total_count += 1
        
        return success_count == total_count
    
    async def unsubscribe_quote(self, stock_codes: List[str], exchange: str = "UN") -> bool:
        """
        실시간 호가 구독 해제
        Args:
            stock_codes: 종목코드 리스트
            exchange: 거래소 구분
        Returns:
            성공 여부
        """
        success_count = 0
        
        for stock_code in stock_codes:
            try:
                success = await self._send_subscription_message(
                    tr_id="H0NXASP0",
                    tr_type="2",  # 구독 해제
                    stock_code=stock_code,
                    exchange=exchange
                )
                
                if success:
                    sub_id = f"quote_{stock_code}_{exchange}"
                    if sub_id in self.subscriptions:
                        del self.subscriptions[sub_id]
                    success_count += 1
                    self.logger.info(f"실시간 호가 구독 해제: {stock_code} ({exchange})")
                
                # 연속 요청 간격
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"실시간 호가 구독 해제 실패 {stock_code}: {e}")
        
        return success_count == len(stock_codes)
    
    async def unsubscribe_tick(self, stock_codes: List[str], exchange: str = "SOR") -> bool:
        """
        실시간 체결 구독 해제
        Args:
            stock_codes: 종목코드 리스트
            exchange: 거래소 구분
        Returns:
            성공 여부
        """
        success_count = 0
        
        for stock_code in stock_codes:
            try:
                success = await self._send_subscription_message(
                    tr_id="H0NXASP0",
                    tr_type="2",  # 구독 해제
                    stock_code=stock_code,
                    exchange=exchange
                )
                
                if success:
                    sub_id = f"tick_{stock_code}_{exchange}"
                    if sub_id in self.subscriptions:
                        del self.subscriptions[sub_id]
                    success_count += 1
                    self.logger.info(f"실시간 체결 구독 해제: {stock_code} ({exchange})")
                
                # 연속 요청 간격
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"실시간 체결 구독 해제 실패 {stock_code}: {e}")
        
        return success_count == len(stock_codes)
    
    # ============= 미국 주식 WebSocket 메서드 =============
    
    async def subscribe_us_quote(self, 
                                symbols: Union[str, List[str]], 
                                exchange: str = "NASD",
                                day_trading: bool = False) -> bool:
        """
        미국 주식 실시간 호가 구독 (HDFSASP0)
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
                    tr_id=self.tr_ids["usa"]["quote"],  # HDFSASP0
                    tr_type="1",  # 구독
                    stock_code=stock_key,
                    exchange=exchange
                )
                
                if success:
                    # 구독 정보 저장
                    sub_id = f"us_quote_{symbol}_{exchange}"
                    self.subscriptions[sub_id] = {
                        "tr_id": self.tr_ids["usa"]["quote"],
                        "stock_code": stock_key,
                        "symbol": symbol,
                        "exchange": exchange,
                        "market": "usa",
                        "day_trading": day_trading,
                        "subscribed_at": datetime.now()
                    }
                    success_count += 1
                    self.logger.info(f"미국 주식 실시간 호가 구독: {symbol} ({exchange}) -> {stock_key}")
                
                # 연속 요청 간격
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"미국 주식 실시간 호가 구독 실패 {symbol}: {e}")
        
        return success_count == len(symbols)
    
    async def subscribe_us_tick(self, 
                               symbols: Union[str, List[str]], 
                               exchange: str = "NASD",
                               day_trading: bool = False,
                               delayed: bool = False) -> bool:
        """
        미국 주식 실시간 체결 구독 (HDFSCNT0 or HDFSCNT2)
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
        tr_id = self.tr_ids["usa"]["delayed_tick"] if delayed else self.tr_ids["usa"]["tick"]
        
        success_count = 0
        for symbol in symbols:
            try:
                # 미국 주식 종목 키 생성
                stock_key = self._get_us_stock_key(symbol, exchange, day_trading)
                
                success = await self._send_subscription_message(
                    tr_id=tr_id,
                    tr_type="1",  # 구독
                    stock_code=stock_key,
                    exchange=exchange
                )
                
                if success:
                    # 구독 정보 저장
                    sub_id = f"us_tick_{symbol}_{exchange}" + ("_delayed" if delayed else "")
                    self.subscriptions[sub_id] = {
                        "tr_id": tr_id,
                        "stock_code": stock_key,
                        "symbol": symbol,
                        "exchange": exchange,
                        "market": "usa",
                        "day_trading": day_trading,
                        "delayed": delayed,
                        "subscribed_at": datetime.now()
                    }
                    success_count += 1
                    tick_type = "지연 체결" if delayed else "실시간 체결"
                    self.logger.info(f"미국 주식 {tick_type} 구독: {symbol} ({exchange}) -> {stock_key}")
                
                # 연속 요청 간격
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"미국 주식 실시간 체결 구독 실패 {symbol}: {e}")
        
        return success_count == len(symbols)
    
    async def unsubscribe_us_stock(self, 
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
                    tr_id=self.tr_ids["usa"]["quote"],
                    tr_type="2",  # 구독 해제
                    stock_code=stock_key,
                    exchange=exchange
                )
                
                if success:
                    sub_id = f"us_quote_{symbol}_{exchange}"
                    if sub_id in self.subscriptions:
                        del self.subscriptions[sub_id]
                    success_count += 1
                    self.logger.info(f"미국 주식 실시간 호가 구독 해제: {symbol} ({exchange})")
                
                total_count += 1
                
            except Exception as e:
                self.logger.error(f"미국 주식 실시간 호가 구독 해제 실패 {symbol}: {e}")
                total_count += 1
        
        if data_type in ["tick", "all"]:
            # 실시간과 지연 모두 해제 시도
            for delayed in [False, True]:
                try:
                    tr_id = self.tr_ids["usa"]["delayed_tick"] if delayed else self.tr_ids["usa"]["tick"]
                    success = await self._send_subscription_message(
                        tr_id=tr_id,
                        tr_type="2",  # 구독 해제
                        stock_code=stock_key,
                        exchange=exchange
                    )
                    
                    if success:
                        sub_suffix = "_delayed" if delayed else ""
                        sub_id = f"us_tick_{symbol}_{exchange}{sub_suffix}"
                        if sub_id in self.subscriptions:
                            del self.subscriptions[sub_id]
                        success_count += 1
                        tick_type = "지연 체결" if delayed else "실시간 체결"
                        self.logger.info(f"미국 주식 {tick_type} 구독 해제: {symbol} ({exchange})")
                    
                    total_count += 1
                    
                except Exception as e:
                    tick_type = "지연 체결" if delayed else "실시간 체결"
                    self.logger.error(f"미국 주식 {tick_type} 구독 해제 실패 {symbol}: {e}")
                    total_count += 1
        
        return success_count > 0  # 하나라도 성공하면 성공으로 간주
    
    # ============= 통합 메서드 (한국/미국 자동 구분) =============
    
    async def subscribe_realtime(self,
                                symbol: str,
                                data_type: str = "both",
                                market: str = "auto",
                                exchange: str = None) -> bool:
        """
        통합 실시간 데이터 구독 (한국/미국 자동 구분)
        Args:
            symbol: 종목코드 또는 티커 심볼
            data_type: "quote", "tick", "both"
            market: "KR", "US", "auto"
            exchange: 거래소 코드
        Returns:
            구독 성공 여부
        """
        # 시장 자동 감지
        if market == "auto":
            market = self._detect_market(symbol)
        
        success = True
        
        if market == "korea":
            # 한국 주식
            if data_type in ["quote", "both"]:
                result = await self.subscribe_quote([symbol], exchange or "UN")
                success &= result
            
            if data_type in ["tick", "both"]:
                result = await self.subscribe_tick([symbol], exchange or "UN")
                success &= result
        
        else:  # USA
            # 미국 주식
            if data_type in ["quote", "both"]:
                result = await self.subscribe_us_quote([symbol], exchange or "NASD")
                success &= result
            
            if data_type in ["tick", "both"]:
                result = await self.subscribe_us_tick([symbol], exchange or "NASD")
                success &= result
        
        return success
    
    def set_callbacks(self,
                     on_quote: Optional[Callable] = None,
                     on_tick: Optional[Callable] = None,
                     on_error: Optional[Callable] = None):
        """
        콜백 함수 설정
        Args:
            on_quote: 실시간 호가 데이터 콜백
            on_tick: 실시간 체결 데이터 콜백
            on_error: 에러 콜백
        """
        self.on_quote_callback = on_quote
        self.on_tick_callback = on_tick
        self.on_error_callback = on_error
    
    def get_subscriptions(self) -> Dict:
        """현재 구독 목록 반환"""
        return self.subscriptions.copy()
    
    def get_connection_status(self) -> Dict:
        """연결 상태 반환"""
        return {
            "is_connected": self.is_connected,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "subscription_count": len(self.subscriptions),
            "ws_url": self.ws_base_url
        }