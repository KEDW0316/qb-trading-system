import requests
import jwt
import uuid
import hashlib
import time
import os
import json
import asyncio
import websockets
from typing import Dict, Optional, Any, Callable
from urllib.parse import urlencode
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class BithumbWebSocket:
    """빗썸 WebSocket API 클래스"""
    
    PUBLIC_WS_URL = "wss://ws-api.bithumb.com/websocket/v1"
    PRIVATE_WS_URL = "wss://ws-api.bithumb.com/websocket/v1/private"
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('BIT_APP_KEY')
        self.secret_key = secret_key or os.getenv('BIT_APP_SECRET')
        self.public_ws = None
        self.private_ws = None
        self.callbacks = {}
        
    async def connect_public(self):
        """Public WebSocket 연결"""
        try:
            self.public_ws = await websockets.connect(self.PUBLIC_WS_URL)
            print("Public WebSocket 연결 성공!")
            return True
        except Exception as e:
            print(f"Public WebSocket 연결 실패: {e}")
            return False
    
    async def connect_private(self):
        """Private WebSocket 연결 (JWT 인증)"""
        if not self.api_key or not self.secret_key:
            print("API 키가 필요합니다")
            return False
            
        try:
            # JWT 토큰 생성
            payload = {
                'access_key': self.api_key,
                'nonce': str(uuid.uuid4()),
                'timestamp': round(time.time() * 1000)
            }
            
            jwt_token = jwt.encode(payload, self.secret_key, algorithm='HS256')
            authorization_token = f'Bearer {jwt_token}'
            
            # WebSocket 연결 시 헤더에 인증 정보 포함
            extra_headers = {
                'authorization': authorization_token
            }
            
            self.private_ws = await websockets.connect(
                self.PRIVATE_WS_URL,
                extra_headers=extra_headers
            )
            print("Private WebSocket 연결 성공!")
            return True
            
        except Exception as e:
            print(f"Private WebSocket 연결 실패: {e}")
            return False
    
    async def subscribe_ticker(self, codes: list, callback: Callable = None):
        """현재가 구독"""
        if not self.public_ws:
            print("Public WebSocket에 먼저 연결하세요")
            return
            
        message = [
            {"ticket": f"ticker_{uuid.uuid4().hex[:8]}"},  # 임의의 ticket 문자열
            {"type": "ticker", "codes": codes}
        ]
        
        await self.public_ws.send(json.dumps(message))
        if callback:
            self.callbacks['ticker'] = callback
        print(f"Ticker 구독 시작: {codes}")
    
    async def subscribe_trade(self, codes: list, callback: Callable = None):
        """체결 구독"""
        if not self.public_ws:
            print("Public WebSocket에 먼저 연결하세요")
            return
            
        message = [
            {"ticket": f"trade_{uuid.uuid4().hex[:8]}"},  # 임의의 ticket 문자열
            {"type": "trade", "codes": codes}
        ]
        
        await self.public_ws.send(json.dumps(message))
        if callback:
            self.callbacks['trade'] = callback
        print(f"Trade 구독 시작: {codes}")
    
    async def subscribe_orderbook(self, codes: list, callback: Callable = None):
        """호가 구독"""
        if not self.public_ws:
            print("Public WebSocket에 먼저 연결하세요")
            return
            
        message = [
            {"ticket": f"orderbook_{uuid.uuid4().hex[:8]}"},  # 임의의 ticket 문자열
            {"type": "orderbook", "codes": codes}
        ]
        
        await self.public_ws.send(json.dumps(message))
        if callback:
            self.callbacks['orderbook'] = callback
        print(f"Orderbook 구독 시작: {codes}")
    
    async def subscribe_my_order(self, codes: list, callback: Callable = None):
        """내 주문 구독 (Private)"""
        if not self.private_ws:
            print("Private WebSocket에 먼저 연결하세요")
            return
            
        message = [
            {"ticket": f"myorder_{uuid.uuid4().hex[:8]}"},  # 임의의 ticket 문자열
            {"type": "myOrder", "codes": codes}
        ]
        
        await self.private_ws.send(json.dumps(message))
        if callback:
            self.callbacks['myOrder'] = callback
        print(f"MyOrder 구독 시작: {codes}")
    
    async def subscribe_my_asset(self, callback: Callable = None):
        """내 자산 구독 (Private)"""
        if not self.private_ws:
            print("Private WebSocket에 먼저 연결하세요")
            return
            
        message = [
            {"ticket": f"myasset_{uuid.uuid4().hex[:8]}"},  # 임의의 ticket 문자열
            {"type": "myAsset"}
        ]
        
        await self.private_ws.send(json.dumps(message))
        if callback:
            self.callbacks['myAsset'] = callback
        print("MyAsset 구독 시작")
    
    async def listen_public(self):
        """Public WebSocket 메시지 수신"""
        if not self.public_ws:
            return
            
        try:
            async for message in self.public_ws:
                try:
                    data = json.loads(message)
                    
                    # 메시지 타입별 상세 정보 출력
                    if data.get('type') == 'ticker':
                        stream_type = data.get('stream_type', 'UNKNOWN')
                        code = data.get('code', 'UNKNOWN')
                        trade_price = data.get('trade_price', 0)
                        change = data.get('change', 'UNKNOWN')
                        change_rate = data.get('change_rate', 0)
                        
                        print(f"📊 Ticker [{stream_type}] {code}: {trade_price:,}원 ({change} {change_rate:.2%})")
                        
                    elif data.get('type') == 'trade':
                        code = data.get('code', 'UNKNOWN')
                        trade_price = data.get('trade_price', 0)
                        trade_volume = data.get('trade_volume', 0)
                        ask_bid = data.get('ask_bid', 'UNKNOWN')
                        
                        print(f"💱 Trade {code}: {trade_price:,}원 x {trade_volume} BTC ({ask_bid})")
                        
                    elif data.get('type') == 'orderbook':
                        code = data.get('code', 'UNKNOWN')
                        stream_type = data.get('stream_type', 'UNKNOWN')
                        total_ask_size = data.get('total_ask_size', 0)
                        total_bid_size = data.get('total_bid_size', 0)
                        
                        print(f"📚 Orderbook {code} [{stream_type}] - 총 매도: {total_ask_size} BTC, 총 매수: {total_bid_size} BTC")
                        
                        # orderbook_units에서 상위 5개 호가만 출력
                        orderbook_units = data.get('orderbook_units', [])
                        if orderbook_units:
                            print(f"📊 상위 5개 호가:")
                            for i, unit in enumerate(orderbook_units[:5]):
                                ask_price = unit.get('ask_price', 0)
                                bid_price = unit.get('bid_price', 0)
                                ask_size = unit.get('ask_size', 0)
                                bid_size = unit.get('bid_size', 0)
                                
                                print(f"  {i+1}. 매도: {ask_price:,}원 x {ask_size} BTC | 매수: {bid_price:,}원 x {bid_size} BTC")
                        
                        # 콜백 함수 실행
                        if 'orderbook' in self.callbacks:
                            await self.callbacks['orderbook'](data)
                        
                except json.JSONDecodeError as e:
                    print(f"JSON 파싱 에러: {e}, 메시지: {message}")
                except Exception as e:
                    print(f"메시지 처리 에러: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            print("Public WebSocket 연결이 종료되었습니다")
        except Exception as e:
            print(f"Public WebSocket 에러: {e}")
    
    async def listen_private(self):
        """Private WebSocket 메시지 수신"""
        if not self.private_ws:
            return
            
        try:
            async for message in self.private_ws:
                try:
                    data = json.loads(message)
                    
                    # 메시지 타입별 상세 정보 출력
                    if data.get('type') == 'myOrder':
                        print(f"📋 MyOrder 업데이트: {data}")
                    elif data.get('type') == 'myAsset':
                        print(f"💰 MyAsset 업데이트: {data}")
                    
                    # 콜백 함수 실행
                    if 'type' in data and data['type'] in self.callbacks:
                        await self.callbacks[data['type']](data)
                        
                except json.JSONDecodeError as e:
                    print(f"JSON 파싱 에러: {e}, 메시지: {message}")
                except Exception as e:
                    print(f"메시지 처리 에러: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            print("Private WebSocket 연결이 종료되었습니다")
        except Exception as e:
            print(f"Private WebSocket 에러: {e}")
    
    async def close(self):
        """WebSocket 연결 종료"""
        if self.public_ws:
            await self.public_ws.close()
            print("Public WebSocket 연결 종료")
        
        if self.private_ws:
            await self.private_ws.close()
            print("Private WebSocket 연결 종료")


class BithumbAPI:
    """빗썸 API 래퍼 클래스"""
    
    BASE_URL = "https://api.bithumb.com"
    BASE_WS_URL = "wss://ws-api.bithumb.com/websocket/v1"
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        # 환경변수에서 API 키를 가져오거나 직접 전달받은 키 사용
        self.api_key = api_key or os.getenv('BIT_APP_KEY')
        self.secret_key = secret_key or os.getenv('BIT_APP_SECRET')
        self.session = requests.Session()
    
    def _make_public_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """공개 API 요청"""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}
    
    def _make_private_request(self, endpoint: str, params: Optional[Dict] = None, method: str = "GET") -> Dict[str, Any]:
        """개인 API 요청 (JWT 인증)"""
        if not self.api_key or not self.secret_key:
            return {"status": "error", "message": "API 키가 필요합니다"}
        
        # query_hash 생성 (파라미터가 있는 경우)
        query_hash = ""
        if params:
            query = urlencode(params).encode()
            hash_obj = hashlib.sha512()
            hash_obj.update(query)
            query_hash = hash_obj.hexdigest()
        
        # JWT 토큰 생성
        payload = {
            'access_key': self.api_key,
            'nonce': str(uuid.uuid4()),
            'timestamp': round(time.time() * 1000)
        }
        
        # query_hash가 있는 경우 페이로드에 추가
        if query_hash:
            payload['query_hash'] = query_hash
            payload['query_hash_alg'] = 'SHA512'
        
        try:
            jwt_token = jwt.encode(payload, self.secret_key, algorithm='HS256')
            authorization_token = f'Bearer {jwt_token}'
            
            headers = {
                'Authorization': authorization_token,
                'Content-Type': 'application/json'
            }
            
            url = f"{self.BASE_URL}{endpoint}"
            
            # GET 요청과 POST 요청을 구분하여 처리
            if method.upper() == "POST":
                # POST 요청: 예제와 동일하게 JSON 문자열로 데이터 전송
                import json
                response = self.session.post(url, data=json.dumps(params), headers=headers)
            else:
                # GET 요청: 쿼리 파라미터로 전송
                if params:
                    response = self.session.get(url, params=params, headers=headers)
                else:
                    response = self.session.get(url, headers=headers)
                
            response.raise_for_status()
            return response.json()
            
        except jwt.PyJWTError as e:
            return {"status": "error", "message": f"JWT 토큰 생성 실패: {str(e)}"}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": str(e)}
    
    # PUBLIC API 메서드들
    def get_market_list(self) -> Dict[str, Any]:
        """마켓 코드 조회"""
        return self._make_public_request("/v1/market/all")

    
    def get_ticker(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """현재가(Ticker) 조회"""
        if symbol:
            return self._make_public_request("/v1/ticker", {"markets": symbol})
        else:
            return self._make_public_request("/v1/ticker")
    
    def get_orderbook(self, symbol: str) -> Dict[str, Any]:
        """호가 정보(Orderbook) 조회"""
        # Bithumb API 형식에 맞게 파라미터 수정
        params = {
            "markets": symbol
        }
        return self._make_public_request("/v1/orderbook", params)
    
    def get_candles(self, symbol: str, interval: str = "1m", limit: int = 100) -> Dict[str, Any]:
        """캔들 데이터 조회"""
        # Bithumb API 형식에 맞게 URL 구성
        # interval을 minutes로 변환 (1m -> 1, 5m -> 5, 15m -> 15, 30m -> 30, 1h -> 60, 4h -> 240, 1d -> 1440)
        interval_map = {
            "1m": "1", "5m": "5", "15m": "5", "30m": "30",
            "1h": "60", "4h": "240", "1d": "1440"
        }
        
        minutes = interval_map.get(interval, "1")
        
        params = {
            "market": symbol,
            "count": limit
        }
        
        return self._make_public_request(f"/v1/candles/minutes/{minutes}", params)

    def get_recent_trades(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """최근 체결 내역 조회"""
        # Bithumb API 형식에 맞게 파라미터 수정
        params = {
            "count": limit
        }
        return self._make_public_request("/v1/trades/ticks", params)
    
    # PRIVATE API 메서드들
    def get_account_info(self) -> Dict[str, Any]:
        """전체 계좌 조회"""
        return self._make_private_request("/v1/accounts")
    
    def get_order_info(self, order_id: str) -> Dict[str, Any]:
        """개별 주문 조회"""
        return self._make_private_request("/v1/private/order", {"order_id": order_id})
    
    def get_order_chance(self, market: str) -> Dict[str, Any]:
        """주문 가능 정보 조회"""
        params = {"market": market}
        return self._make_private_request("/v1/orders/chance", params)
    
    def get_order_list(self, market: Optional[str] = None, limit: int = 100, page: int = 1, 
                      order_by: str = 'desc', uuids: Optional[list] = None) -> Dict[str, Any]:
        """주문 리스트 조회"""
        params = {}
        if market:
            params["market"] = market
        if limit:
            params["limit"] = limit
        if page:
            params["page"] = page
        if order_by:
            params["order_by"] = order_by
        if uuids:
            # uuids는 리스트 형태로 전송되어야 함
            for uuid_val in uuids:
                params[f"uuids[]"] = uuid_val
        
        return self._make_private_request("/v1/orders", params)
    
    def place_order(self, market: str, side: str, order_type: str, price: float, volume: float) -> Dict[str, Any]:
        """주문하기"""
        # Bithumb API 요구사항에 맞게 파라미터 조정
        params = {
            "market": market,
            "side": side,
            "order_type": order_type,
            "price": int(price),  # 가격을 정수로 변환
            "volume": round(volume, 8)  # 수량을 8자리 소수점으로 조정
        }
        return self._make_private_request("/v2/orders", params, method="POST")
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """주문 취소"""
        return self._make_private_request("/v1/private/order/cancel", {"order_id": order_id})
