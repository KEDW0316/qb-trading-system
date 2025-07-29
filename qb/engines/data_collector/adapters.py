"""
Data Adapters

다양한 데이터 소스를 위한 어댑터 클래스들
- BaseDataAdapter: 추상 베이스 클래스
- KISDataAdapter: 한국투자증권 WebSocket/REST API
- NaverDataAdapter: 네이버 금융 데이터
- YahooDataAdapter: 야후 파이낸스 데이터
"""

import asyncio
import json
import logging
import websockets
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from enum import Enum

from ...utils.kis_auth import KISAuth
from ...collectors.kis_client import KISClient
from .connection_manager import ConnectionManager


class AdapterStatus(Enum):
    """어댑터 상태"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class BaseDataAdapter(ABC):
    """
    데이터 어댑터 추상 베이스 클래스
    
    모든 데이터 소스 어댑터가 구현해야 하는 인터페이스
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.status = AdapterStatus.DISCONNECTED
        self.subscribed_symbols: Set[str] = set()
        
        # 통계
        self.stats = {
            'messages_received': 0,
            'messages_sent': 0,
            'connections': 0,
            'reconnections': 0,
            'errors': 0,
            'last_message_time': None
        }
    
    @abstractmethod
    async def connect(self) -> bool:
        """데이터 소스에 연결"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """연결 해제"""
        pass
    
    @abstractmethod
    async def subscribe_symbol(self, symbol: str) -> bool:
        """심볼 구독"""
        pass
    
    @abstractmethod
    async def unsubscribe_symbol(self, symbol: str) -> bool:
        """심볼 구독 해제"""
        pass
    
    @abstractmethod
    async def collect_data(self) -> List[Dict[str, Any]]:
        """데이터 수집 (실시간 메시지들 반환)"""
        pass
    
    @abstractmethod
    async def get_historical_data(self, symbol: str, timeframe: str, count: int = 200) -> List[Dict[str, Any]]:
        """과거 데이터 조회"""
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """어댑터 상태 정보"""
        return {
            'name': self.name,
            'status': self.status.value,
            'subscribed_symbols': list(self.subscribed_symbols),
            'stats': self.stats.copy()
        }
    
    def _update_stats(self, stat_name: str, increment: int = 1):
        """통계 업데이트"""
        self.stats[stat_name] += increment
        if stat_name == 'messages_received':
            self.stats['last_message_time'] = datetime.now().isoformat()


class KISDataAdapter(BaseDataAdapter):
    """
    한국투자증권 데이터 어댑터
    
    WebSocket을 통한 실시간 데이터 수집
    REST API를 통한 과거 데이터 조회
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("KIS", config)
        
        # KIS 클라이언트 초기화
        self.kis_client = KISClient(mode=config.get('mode', 'paper'))
        
        # WebSocket 설정
        self.websocket_url = self._get_websocket_url()
        self.websocket = None
        self.message_queue = asyncio.Queue()
        
        # WebSocket 인증 키
        self.approval_key = config.get('approval_key')
        if not self.approval_key:
            self.logger.warning("No approval_key provided for WebSocket connection")
        
        # 연결 관리
        self.connection_manager = ConnectionManager(
            max_retries=config.get('max_retries', 5),
            retry_delay=config.get('retry_delay', 5)
        )
        
        # 구독 관리
        self.subscription_ids = {}  # symbol -> subscription_id 매핑
        self.pending_subscriptions = []  # 대기 중인 구독 요청들
        self._listener_task = None  # 메시지 리스너 태스크
        self._reconnect_task = None  # 재연결 태스크
        
    def _get_websocket_url(self) -> str:
        """현재 모드에 따른 WebSocket URL 반환"""
        # 실제 거래 모드인지 확인 (prod/real = 실전투자)
        current_mode = self.kis_client.mode_manager.get_current_mode()
        if current_mode in ['prod', 'real']:
            return "ws://ops.koreainvestment.com:21000/tryitout"  # 실전투자
        else:
            return "ws://ops.koreainvestment.com:31000/tryitout"  # 모의투자
    
    async def connect(self) -> bool:
        """KIS WebSocket 연결"""
        try:
            self.status = AdapterStatus.CONNECTING
            
            # 기존 KIS 클라이언트 인증 확인
            try:
                token = self.kis_client.auth.get_token()
                if not token or not token.access_token:
                    self.logger.error("KIS client not authenticated - no valid token")
                    return False
                self.logger.info(f"KIS authentication successful - token expires at {token.expires_at}")
            except Exception as e:
                self.logger.error(f"KIS authentication failed: {e}")
                return False
            
            # WebSocket 승인키 가져오기
            try:
                ws_headers = self.kis_client.auth.get_websocket_headers()
                self.approval_key = ws_headers.get('approval_key')
                if not self.approval_key:
                    self.logger.error("Failed to get WebSocket approval_key")
                    return False
                self.logger.info("WebSocket approval_key obtained successfully")
            except Exception as e:
                self.logger.error(f"Failed to get WebSocket approval_key: {e}")
                return False
            
            # WebSocket 연결 (KIS 공식 방식: /tryitout 경로 사용)
            self.websocket = await websockets.connect(self.websocket_url)
            
            self.status = AdapterStatus.CONNECTED
            self.stats['connections'] += 1
            
            # 메시지 수신 태스크 시작
            self._listener_task = asyncio.create_task(self._message_listener())
            
            # 대기 중인 구독 요청들 전송
            await self._send_pending_subscriptions()
            
            self.logger.info("KIS WebSocket connected successfully")
            return True
            
        except Exception as e:
            self.status = AdapterStatus.ERROR
            self.stats['errors'] += 1
            self.logger.error(f"Failed to connect to KIS WebSocket: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """KIS WebSocket 연결 해제"""
        try:
            # 재연결 태스크 취소
            if self._reconnect_task and not self._reconnect_task.done():
                self._reconnect_task.cancel()
                
            # 리스너 태스크 취소
            if self._listener_task and not self._listener_task.done():
                self._listener_task.cancel()
            
            # WebSocket 연결 종료
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            
            self.status = AdapterStatus.DISCONNECTED
            self.logger.info("KIS WebSocket disconnected")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to disconnect from KIS: {e}")
            return False
    
    async def subscribe_symbol(self, symbol: str) -> bool:
        """KIS 심볼 구독 (실시간 체결가)"""
        try:
            # 구독 정보를 pending list에 추가
            self.pending_subscriptions.append({
                "symbol": symbol,
                "tr_id": "H0STCNT0"  # 실시간 체결가
            })
            
            # 이미 연결되어 있으면 즉시 전송
            if self.status == AdapterStatus.CONNECTED and self.websocket:
                await self._send_pending_subscriptions()
            
            # 구독 목록에 추가
            self.subscribed_symbols.add(symbol)
            self.logger.info(f"Subscription request added for KIS symbol: {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to KIS symbol {symbol}: {e}")
            return False
    
    async def unsubscribe_symbol(self, symbol: str) -> bool:
        """KIS 심볼 구독 해제"""
        try:
            if self.status != AdapterStatus.CONNECTED:
                return True
            
            # 구독 해제 메시지
            unsubscribe_message = {
                "header": {
                    "approval_key": self.kis_auth.approval_key,
                    "custtype": "P",
                    "tr_type": "2",  # 해제
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": "H0STCNT0",
                        "tr_key": symbol
                    }
                }
            }
            
            await self.websocket.send(json.dumps(unsubscribe_message))
            self.subscribed_symbols.discard(symbol)
            self.stats['messages_sent'] += 1
            
            self.logger.info(f"Unsubscribed from KIS symbol: {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe from KIS symbol {symbol}: {e}")
            return False
    
    async def collect_data(self) -> List[Dict[str, Any]]:
        """KIS 실시간 데이터 수집"""
        messages = []
        
        try:
            # 큐에서 메시지들 수집 (non-blocking)
            while not self.message_queue.empty():
                try:
                    message = self.message_queue.get_nowait()
                    messages.append(message)
                except asyncio.QueueEmpty:
                    break
                    
        except Exception as e:
            self.logger.error(f"Error collecting KIS data: {e}")
            
        return messages
    
    async def get_historical_data(self, symbol: str, timeframe: str, count: int = 200) -> List[Dict[str, Any]]:
        """KIS 과거 데이터 조회 (기존 KISClient 활용)"""
        try:
            # 기존 KISClient의 메서드 활용
            if timeframe == "1d" or timeframe == "D":
                # 일봉 데이터 조회
                result = await asyncio.to_thread(
                    self.kis_client.get_daily_price,
                    symbol=symbol,
                    start_date=None,  # 기본값 사용
                    end_date=None,
                    adj_price=True
                )
            elif timeframe == "1m":
                # 분봉 데이터 조회 (제한적 지원)
                result = await asyncio.to_thread(
                    self.kis_client.get_minute_price,
                    symbol=symbol,
                    timeframe="1"
                ) if hasattr(self.kis_client, 'get_minute_price') else []
            else:
                self.logger.warning(f"Unsupported timeframe: {timeframe}")
                return []
            
            if result and isinstance(result, list):
                # 최근 count개만 반환
                return result[-count:] if len(result) > count else result
            else:
                self.logger.warning(f"No historical data received for {symbol}")
                return []
                
        except Exception as e:
            self.logger.error(f"Failed to get KIS historical data for {symbol}: {e}")
            return []
    
    async def _send_pending_subscriptions(self):
        """대기 중인 구독 요청들을 전송"""
        if not self.websocket or not self.pending_subscriptions:
            return
            
        sent_symbols = []
        
        for subscription in self.pending_subscriptions[:]:  # 복사본으로 순회
            try:
                subscribe_message = {
                    "header": {
                        "approval_key": self.approval_key,
                        "custtype": "P",  # 개인
                        "tr_type": "1",   # 등록
                        "content-type": "utf-8"
                    },
                    "body": {
                        "input": {
                            "tr_id": subscription["tr_id"],
                            "tr_key": subscription["symbol"]
                        }
                    }
                }
                
                await self.websocket.send(json.dumps(subscribe_message))
                sent_symbols.append(subscription["symbol"])
                self.pending_subscriptions.remove(subscription)
                self.stats['messages_sent'] += 1
                
                # 잠시 대기하여 서버 부하 방지
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Failed to send subscription for {subscription['symbol']}: {e}")
        
        if sent_symbols:
            self.logger.info(f"Sent subscriptions for symbols: {sent_symbols}")
    
    async def _message_listener(self):
        """WebSocket 메시지 수신 리스너"""
        try:
            while self.websocket and self.status == AdapterStatus.CONNECTED:
                try:
                    message = await self.websocket.recv()
                    parsed_data = self._parse_realtime_message(message)
                    
                    if parsed_data:
                        await self.message_queue.put(parsed_data)
                        self._update_stats('messages_received')
                        
                except websockets.exceptions.ConnectionClosed:
                    self.logger.warning("KIS WebSocket connection closed")
                    self.status = AdapterStatus.DISCONNECTED
                    # 재연결 시도
                    if not self._reconnect_task or self._reconnect_task.done():
                        self._reconnect_task = asyncio.create_task(self._auto_reconnect())
                    break
                except Exception as e:
                    self.logger.error(f"Error receiving KIS message: {e}")
                    self._update_stats('errors')
                    
        except Exception as e:
            self.logger.error(f"KIS message listener error: {e}")
            self.status = AdapterStatus.ERROR
            # 재연결 시도
            if not self._reconnect_task or self._reconnect_task.done():
                self._reconnect_task = asyncio.create_task(self._auto_reconnect())
    
    def _parse_realtime_message(self, message: str) -> Optional[Dict[str, Any]]:
        """실시간 메시지 파싱 (KIS 파이프 구분 형식)"""
        try:
            # KIS WebSocket 메시지는 파이프(|) 구분 텍스트 형식
            # 형식: "0|H0STCNT0|005930|데이터..."
            if not message or len(message) < 3:
                return None
            
            # 시스템 메시지 (JSON 형식) 처리
            if message[0] == "{":
                try:
                    import json
                    system_msg = json.loads(message)
                    if system_msg.get("header", {}).get("tr_id") == "PINGPONG":
                        self.logger.debug("Received PINGPONG")
                        return None  # PINGPONG은 무시
                    return None  # 다른 시스템 메시지도 무시
                except json.JSONDecodeError:
                    pass
                
            # 첫 문자로 메시지 타입 확인 (0: 실시간 데이터, 1: 체결통보)
            if message[0] not in ["0", "1"]:
                return None
                
            parts = message.split("|")
            if len(parts) < 4:
                self.logger.debug(f"Invalid KIS message format: {message[:100]}")
                return None
                
            msg_type = parts[0]  # "0" 또는 "1"
            tr_id = parts[1]     # "H0STCNT0" 등
            symbol = parts[2]    # "005930" 등
            data_part = parts[3] # 실제 데이터 부분
            
            # 디버그: 원본 메시지 확인 (처음 몇 개만)
            if not hasattr(self, '_raw_message_logged'):
                self.logger.info(f"Raw KIS message format: msg_type={msg_type}, tr_id={tr_id}, symbol={symbol}")
                self.logger.info(f"Data part preview: {data_part[:100]}...")
                self._raw_message_logged = True
            
            # H0STCNT0 (실시간 체결가) 메시지 파싱
            if tr_id == "H0STCNT0":
                return self._parse_h0stcnt0_data(symbol, data_part)  # symbol을 명시적으로 전달
            elif tr_id == "H0STASP0":  # 실시간 호가
                return self._parse_h0stasp0_data(symbol, data_part)
            else:
                self.logger.debug(f"Unsupported KIS TR_ID: {tr_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to parse KIS realtime message: {e}")
            return None
    
    def _parse_h0stcnt0_data(self, symbol: str, data: str) -> Optional[Dict[str, Any]]:
        """H0STCNT0 (실시간 체결가) 데이터 파싱"""
        try:
            # 데이터는 캐럿(^) 구분
            fields = data.split("^")
            
            if len(fields) < 10:
                self.logger.debug(f"Insufficient H0STCNT0 fields: {len(fields)} for symbol {symbol}")
                return None
            
            # KIS 실시간 체결가 필드 매핑 (공식 문서 기준)
            # 0: MKSC_SHRN_ISCD (종목코드) 
            # 1: STCK_CNTG_HOUR (체결시간-시)
            # 2: STCK_CNTG_MINT (체결시간-분) 
            # 3: STCK_CNTG_SCND (체결시간-초)
            # 4: STCK_PRPR (현재가)
            # 5: PRDY_VRSS (전일대비)
            # 6: PRDY_VRSS_SIGN (전일대비부호)
            # 7: PRDY_CTRT (전일대비율)
            # 8: WGHN_AVRG_STCK_PRC (가중평균주식가격)
            # 9: STCK_OPRC (시가)
            # 10: STCK_HGPR (고가)
            # 11: STCK_LWPR (저가)
            # 12: ASKP1 (매도호가1)
            # 13: BIDP1 (매수호가1)
            # 14: CNTG_VOL (체결거래량)
            # 15: ACML_VOL (누적거래량)
            # 16: ACML_TR_PBMN (누적거래대금)
            
            current_price = fields[4] if len(fields) > 4 else "0"
            
            # 시간 정보 구성 (필드 1, 2, 3: 시, 분, 초)
            try:
                hour = fields[1] if len(fields) > 1 and fields[1] else "00"
                minute = fields[2] if len(fields) > 2 and fields[2] else "00"
                second = fields[3] if len(fields) > 3 and fields[3] else "00"
                timestamp = datetime.now().replace(
                    hour=int(hour), 
                    minute=int(minute), 
                    second=int(second),
                    microsecond=0
                )
            except (ValueError, IndexError):
                timestamp = datetime.now()
                
            result = {
                "symbol": symbol,  # parts[2]에서 전달받은 심볼 사용
                "timestamp": timestamp.isoformat(),
                "close": float(current_price) if current_price else 0.0,
                "volume": int(fields[14]) if len(fields) > 14 and fields[14] else 0,  # 체결거래량
                "acc_volume": int(fields[15]) if len(fields) > 15 and fields[15] else 0,  # 누적거래량
                "change": float(fields[5]) if len(fields) > 5 and fields[5] else 0.0,  # 전일대비
                "change_rate": float(fields[7]) if len(fields) > 7 and fields[7] else 0.0,  # 전일대비율
                "data_type": "realtime_price",
                "source": "kis"
            }
            
            # 디버그용 로그 (첫 번째 수신 메시지만)
            if not hasattr(self, '_first_message_logged'):
                self.logger.info(f"✅ First KIS message parsed successfully!")
                self.logger.info(f"   Symbol: {symbol}")
                self.logger.info(f"   Price: {current_price}")
                self.logger.info(f"   Volume: {fields[14] if len(fields) > 14 else 'N/A'}")
                self.logger.info(f"   Timestamp: {timestamp}")
                self.logger.info(f"   Total fields received: {len(fields)}")
                self._first_message_logged = True
                
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to parse H0STCNT0 data for {symbol}: {e}")
            self.logger.error(f"Data fields: {data[:200]}...")
            return None
    
    async def _auto_reconnect(self):
        """자동 재연결"""
        retry_count = 0
        max_retries = 5
        retry_delay = 5
        
        while retry_count < max_retries:
            try:
                self.logger.info(f"Attempting to reconnect... (attempt {retry_count + 1}/{max_retries})")
                
                # 기존 연결 정리
                if self.websocket:
                    await self.websocket.close()
                    self.websocket = None
                
                # 재연결 시도
                if await self.connect():
                    self.logger.info("Successfully reconnected to KIS WebSocket")
                    
                    # 이전 구독 복원
                    for symbol in self.subscribed_symbols:
                        self.pending_subscriptions.append({
                            "symbol": symbol,
                            "tr_id": "H0STCNT0"
                        })
                    
                    # 구독 재전송
                    await self._send_pending_subscriptions()
                    return
                
            except Exception as e:
                self.logger.error(f"Reconnection attempt failed: {e}")
            
            retry_count += 1
            if retry_count < max_retries:
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)  # 지수 백오프, 최대 60초
        
        self.logger.error(f"Failed to reconnect after {max_retries} attempts")
        self.status = AdapterStatus.ERROR
    
    def _parse_h0stasp0_data(self, symbol: str, data: str) -> Optional[Dict[str, Any]]:
        """H0STASP0 (실시간 호가) 데이터 파싱"""
        try:
            fields = data.split("^")
            if len(fields) < 20:
                return None
                
            # 호가 데이터 파싱 (매도호가1, 매수호가1 등)
            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "ask_price": float(fields[3]) if len(fields) > 3 and fields[3] else 0.0,
                "bid_price": float(fields[13]) if len(fields) > 13 and fields[13] else 0.0,
                "data_type": "realtime_quote",
                "source": "kis"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to parse H0STASP0 data: {e}")
            return None
    
    def _parse_h0stcnt0_message(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """H0STCNT0 (실시간 체결가) 메시지 파싱"""
        try:
            output = data.get("body", {}).get("output", {})
            symbol = output.get("MKSC_SHRN_ISCD")
            
            if not symbol:
                return None
                
            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "close": float(output.get("STCK_PRPR", 0)),
                "volume": int(output.get("CNTG_VOL", 0)),
                "change": float(output.get("PRDY_VRSS", 0)),
                "change_rate": float(output.get("PRDY_CTRT", 0)),
                "message_type": "trade"
            }
        except Exception as e:
            self.logger.error(f"Failed to parse H0STCNT0 message: {e}")
            return None
    
    def _parse_h0stasp0_message(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """H0STASP0 (실시간 호가) 메시지 파싱"""
        try:
            output = data.get("body", {}).get("output", {})
            symbol = output.get("MKSC_SHRN_ISCD")
            
            if not symbol:
                return None
                
            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "bid_price": float(output.get("BIDP1", 0)),
                "ask_price": float(output.get("ASKP1", 0)),
                "bid_volume": int(output.get("BIDP_RSQN1", 0)),
                "ask_volume": int(output.get("ASKP_RSQN1", 0)),
                "message_type": "orderbook"
            }
        except Exception as e:
            self.logger.error(f"Failed to parse H0STASP0 message: {e}")
            return None
    
    def _parse_historical_data(self, data: Dict[str, Any], symbol: str) -> List[Dict[str, Any]]:
        """과거 데이터 파싱"""
        try:
            result = []
            
            if "output2" in data:
                for item in data["output2"]:
                    result.append({
                        "symbol": symbol,
                        "timestamp": item.get("stck_bsop_date"),
                        "open": float(item.get("stck_oprc", 0)),
                        "high": float(item.get("stck_hgpr", 0)),
                        "low": float(item.get("stck_lwpr", 0)),
                        "close": float(item.get("stck_clpr", 0)),
                        "volume": int(item.get("acml_vol", 0))
                    })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to parse KIS historical data: {e}")
            return []


class NaverDataAdapter(BaseDataAdapter):
    """
    네이버 금융 데이터 어댑터
    
    HTTP API를 통한 주가 데이터 수집 (폴링 방식)
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("Naver", config)
        self.base_url = "https://polling.finance.naver.com"
        self.api_url = "https://finance.naver.com/api/sise/etfItemList.nhn"
        self.session = None
        self.polling_interval = config.get('polling_interval', 5)  # 5초 간격
        self.last_prices = {}  # 심볼별 마지막 가격 저장
        
    async def connect(self) -> bool:
        """네이버 API 연결"""
        try:
            self.session = aiohttp.ClientSession()
            self.status = AdapterStatus.CONNECTED
            self.stats['connections'] += 1
            self.logger.info("Naver adapter connected")
            return True
        except Exception as e:
            self.status = AdapterStatus.ERROR
            self.logger.error(f"Failed to connect to Naver: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """네이버 API 연결 해제"""
        try:
            if self.session:
                await self.session.close()
                self.session = None
            self.status = AdapterStatus.DISCONNECTED
            self.logger.info("Naver adapter disconnected")
            return True
        except Exception as e:
            self.logger.error(f"Failed to disconnect from Naver: {e}")
            return False
    
    async def subscribe_symbol(self, symbol: str) -> bool:
        """네이버 심볼 구독 (폴링 방식)"""
        self.subscribed_symbols.add(symbol)
        self.logger.info(f"Subscribed to Naver symbol: {symbol}")
        return True
    
    async def unsubscribe_symbol(self, symbol: str) -> bool:
        """네이버 심볼 구독 해제"""
        self.subscribed_symbols.discard(symbol)
        self.logger.info(f"Unsubscribed from Naver symbol: {symbol}")
        return True
    
    async def collect_data(self) -> List[Dict[str, Any]]:
        """네이버 실시간 데이터 수집 (폴링)"""
        messages = []
        
        if not self.subscribed_symbols or not self.session:
            return messages
        
        try:
            # 구독된 모든 심볼에 대해 데이터 수집
            for symbol in self.subscribed_symbols:
                data = await self._fetch_symbol_data(symbol)
                if data:
                    # 가격 변화가 있을 때만 메시지 추가
                    if self._has_price_changed(symbol, data):
                        messages.append(data)
                        self._update_stats('messages_received')
                        self.last_prices[symbol] = data['close']
                    
        except Exception as e:
            self.logger.error(f"Error collecting Naver data: {e}")
            self._update_stats('errors')
            
        return messages
    
    async def get_historical_data(self, symbol: str, timeframe: str, count: int = 200) -> List[Dict[str, Any]]:
        """네이버 과거 데이터 조회"""
        try:
            # 네이버 차트 API 활용
            url = f"https://fchart.stock.naver.com/sise.nhn"
            params = {
                'symbol': symbol,
                'timeframe': 'day' if timeframe in ['1d', 'D'] else 'minute',
                'count': count,
                'requestType': 0
            }
            
            if self.session:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        text = await response.text()
                        return self._parse_historical_data(text, symbol)
            
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to get Naver historical data for {symbol}: {e}")
            return []
    
    def _has_price_changed(self, symbol: str, data: Dict[str, Any]) -> bool:
        """가격 변화 확인"""
        if symbol not in self.last_prices:
            return True
        return self.last_prices[symbol] != data.get('close', 0)
    
    async def _fetch_symbol_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """심볼별 데이터 조회 (네이버 현재가 API)"""
        try:
            # 네이버 현재가 조회 API
            url = f"https://finance.naver.com/item/sise.naver"
            params = {'code': symbol}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._parse_current_price_html(html, symbol)
                    
        except Exception as e:
            self.logger.error(f"Failed to fetch Naver data for {symbol}: {e}")
            
        return None
    
    def _parse_current_price_html(self, html: str, symbol: str) -> Optional[Dict[str, Any]]:
        """네이버 현재가 HTML 파싱"""
        try:
            # BeautifulSoup 대신 정규식으로 간단히 파싱
            import re
            
            # 현재가 추출
            price_pattern = r'class="no_today"[^>]*>[\s]*<em[^>]*>([^<]+)</em>'
            price_match = re.search(price_pattern, html)
            
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                current_price = float(price_str)
                
                # 거래량 추출 (간단한 예시)
                volume_pattern = r'거래량</em>[\s]*<span[^>]*>([^<]+)</span>'
                volume_match = re.search(volume_pattern, html)
                volume = 0
                if volume_match:
                    volume_str = volume_match.group(1).replace(',', '')
                    volume = int(volume_str) if volume_str.isdigit() else 0
                
                return {
                    "symbol": symbol,
                    "timestamp": datetime.now().isoformat(),
                    "open": current_price,  # 실시간에서는 현재가로 대체
                    "high": current_price,
                    "low": current_price,
                    "close": current_price,
                    "volume": volume,
                    "source": "naver"
                }
                
        except Exception as e:
            self.logger.error(f"Failed to parse Naver HTML for {symbol}: {e}")
            
        return None
    
    def _parse_historical_data(self, data: str, symbol: str) -> List[Dict[str, Any]]:
        """네이버 과거 데이터 파싱"""
        try:
            # 네이버 차트 데이터는 특정 형식으로 제공됨
            # 실제 구현시 네이버 API 응답 형식에 맞춰 파싱 필요
            return []
        except Exception as e:
            self.logger.error(f"Failed to parse Naver historical data: {e}")
            return []


class YahooDataAdapter(BaseDataAdapter):
    """
    야후 파이낸스 데이터 어댑터
    
    yfinance 라이브러리를 통한 데이터 수집
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("Yahoo", config)
        self.session = None
        self.polling_interval = config.get('polling_interval', 10)  # 10초 간격
        self.last_prices = {}  # 심볼별 마지막 가격 저장
        
        # yfinance 사용 여부 확인
        try:
            import yfinance as yf
            self.yf = yf
            self.yf_available = True
        except ImportError:
            self.yf = None
            self.yf_available = False
            self.logger.warning("yfinance not available, using direct API")
        
    async def connect(self) -> bool:
        """야후 파이낸스 연결"""
        try:
            self.session = aiohttp.ClientSession()
            self.status = AdapterStatus.CONNECTED
            self.stats['connections'] += 1
            self.logger.info("Yahoo adapter connected")
            return True
        except Exception as e:
            self.status = AdapterStatus.ERROR
            self.logger.error(f"Failed to connect to Yahoo: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """야후 파이낸스 연결 해제"""
        try:
            if self.session:
                await self.session.close()
                self.session = None
            self.status = AdapterStatus.DISCONNECTED
            self.logger.info("Yahoo adapter disconnected")
            return True
        except Exception as e:
            self.logger.error(f"Failed to disconnect from Yahoo: {e}")
            return False
    
    async def subscribe_symbol(self, symbol: str) -> bool:
        """야후 심볼 구독"""
        # 한국 주식의 경우 .KS 또는 .KQ 추가
        if symbol.isdigit() and len(symbol) == 6:
            symbol = f"{symbol}.KS"  # 기본적으로 KOSPI
        
        self.subscribed_symbols.add(symbol)
        self.logger.info(f"Subscribed to Yahoo symbol: {symbol}")
        return True
    
    async def unsubscribe_symbol(self, symbol: str) -> bool:
        """야후 심볼 구독 해제"""
        self.subscribed_symbols.discard(symbol)
        self.logger.info(f"Unsubscribed from Yahoo symbol: {symbol}")
        return True
    
    async def collect_data(self) -> List[Dict[str, Any]]:
        """야후 파이낸스 실시간 데이터 수집 (폴링)"""
        messages = []
        
        if not self.subscribed_symbols or not self.session:
            return messages
        
        try:
            for symbol in self.subscribed_symbols:
                data = await self._fetch_current_price(symbol)
                if data:
                    # 가격 변화가 있을 때만 메시지 추가
                    if self._has_price_changed(symbol, data):
                        messages.append(data)
                        self._update_stats('messages_received')
                        self.last_prices[symbol] = data['close']
                        
        except Exception as e:
            self.logger.error(f"Error collecting Yahoo data: {e}")
            self._update_stats('errors')
            
        return messages
    
    async def get_historical_data(self, symbol: str, timeframe: str, count: int = 200) -> List[Dict[str, Any]]:
        """야후 파이낸스 과거 데이터 조회"""
        try:
            if self.yf_available:
                # yfinance 사용
                return await self._get_historical_with_yfinance(symbol, timeframe, count)
            else:
                # 직접 API 호출
                return await self._get_historical_with_api(symbol, timeframe, count)
                
        except Exception as e:
            self.logger.error(f"Failed to get Yahoo historical data for {symbol}: {e}")
            return []
    
    def _has_price_changed(self, symbol: str, data: Dict[str, Any]) -> bool:
        """가격 변화 확인"""
        if symbol not in self.last_prices:
            return True
        return abs(self.last_prices[symbol] - data.get('close', 0)) > 0.01
    
    async def _fetch_current_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """현재 가격 조회"""
        try:
            # Yahoo Finance API를 통한 현재가 조회
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {
                'interval': '1m',
                'range': '1d'
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_current_price_data(data, symbol)
                    
        except Exception as e:
            self.logger.error(f"Failed to fetch Yahoo current price for {symbol}: {e}")
            
        return None
    
    def _parse_current_price_data(self, data: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        """Yahoo Finance API 응답 파싱"""
        try:
            chart = data.get('chart', {})
            result = chart.get('result', [])
            
            if not result:
                return None
                
            quote = result[0]
            meta = quote.get('meta', {})
            current_price = meta.get('regularMarketPrice', 0)
            
            if current_price == 0:
                return None
            
            # 추가 정보 추출
            previous_close = meta.get('previousClose', current_price)
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close > 0 else 0
            
            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "open": meta.get('regularMarketOpen', current_price),
                "high": meta.get('regularMarketDayHigh', current_price),
                "low": meta.get('regularMarketDayLow', current_price),
                "close": current_price,
                "volume": meta.get('regularMarketVolume', 0),
                "change": change,
                "change_percent": change_percent,
                "source": "yahoo"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to parse Yahoo current price data: {e}")
            return None
    
    async def _get_historical_with_yfinance(self, symbol: str, timeframe: str, count: int) -> List[Dict[str, Any]]:
        """yfinance를 사용한 과거 데이터 조회"""
        try:
            def fetch_data():
                ticker = self.yf.Ticker(symbol)
                
                # 시간대별 매핑
                interval_map = {
                    '1m': '1m',
                    '5m': '5m',
                    '15m': '15m',
                    '1h': '1h',
                    '1d': '1d',
                    'D': '1d'
                }
                
                interval = interval_map.get(timeframe, '1d')
                period = '1y' if interval == '1d' else '5d'
                
                hist = ticker.history(period=period, interval=interval)
                
                result = []
                for index, row in hist.iterrows():
                    result.append({
                        "symbol": symbol,
                        "timestamp": index.isoformat(),
                        "open": float(row['Open']),
                        "high": float(row['High']),
                        "low": float(row['Low']),
                        "close": float(row['Close']),
                        "volume": int(row['Volume']),
                        "source": "yahoo"
                    })
                
                return result[-count:] if len(result) > count else result
            
            # 동기 함수를 비동기로 실행
            return await asyncio.to_thread(fetch_data)
            
        except Exception as e:
            self.logger.error(f"Failed to get Yahoo historical data with yfinance: {e}")
            return []
    
    async def _get_historical_with_api(self, symbol: str, timeframe: str, count: int) -> List[Dict[str, Any]]:
        """직접 API를 사용한 과거 데이터 조회"""
        try:
            # Yahoo Finance API 직접 호출
            interval_map = {
                '1m': '1m',
                '5m': '5m',
                '15m': '15m',
                '1h': '1h',
                '1d': '1d',
                'D': '1d'
            }
            
            interval = interval_map.get(timeframe, '1d')
            range_period = '1y' if interval == '1d' else '5d'
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            params = {
                'interval': interval,
                'range': range_period
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_historical_data(data, symbol, count)
                    
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to get Yahoo historical data with API: {e}")
            return []
    
    def _parse_historical_data(self, data: Dict[str, Any], symbol: str, count: int) -> List[Dict[str, Any]]:
        """Yahoo Finance 과거 데이터 파싱"""
        try:
            chart = data.get('chart', {})
            result = chart.get('result', [])
            
            if not result:
                return []
            
            quote = result[0]
            timestamps = quote.get('timestamp', [])
            indicators = quote.get('indicators', {})
            quote_data = indicators.get('quote', [{}])[0]
            
            opens = quote_data.get('open', [])
            highs = quote_data.get('high', [])
            lows = quote_data.get('low', [])
            closes = quote_data.get('close', [])
            volumes = quote_data.get('volume', [])
            
            historical_data = []
            
            for i, timestamp in enumerate(timestamps):
                if i >= len(closes) or closes[i] is None:
                    continue
                    
                historical_data.append({
                    "symbol": symbol,
                    "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
                    "open": float(opens[i]) if i < len(opens) and opens[i] is not None else 0,
                    "high": float(highs[i]) if i < len(highs) and highs[i] is not None else 0,
                    "low": float(lows[i]) if i < len(lows) and lows[i] is not None else 0,
                    "close": float(closes[i]),
                    "volume": int(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0,
                    "source": "yahoo"
                })
            
            # 최근 count개만 반환
            return historical_data[-count:] if len(historical_data) > count else historical_data
            
        except Exception as e:
            self.logger.error(f"Failed to parse Yahoo historical data: {e}")
            return []