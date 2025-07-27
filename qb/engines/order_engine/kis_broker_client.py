"""
한국투자증권 브로커 클라이언트 (KIS Broker Client)

QB Trading System의 주문 엔진과 한국투자증권 API를 연결하는 브로커 클라이언트입니다.
실제 주문 제출, 취소, 체결 조회 등의 거래 기능을 제공합니다.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from .base import (
    BaseBrokerClient, Order, OrderResult, Position, OrderType, OrderSide, OrderStatus
)
from ...collectors.kis_client import KISClient
from ...utils.redis_manager import RedisManager

logger = logging.getLogger(__name__)


class KISBrokerClient(BaseBrokerClient):
    """
    한국투자증권 브로커 클라이언트
    
    KIS API를 통한 실제 거래 기능:
    1. 주식 매수/매도 주문
    2. 주문 취소 및 정정
    3. 주문 상태 조회
    4. 포지션 및 잔고 조회
    """
    
    def __init__(
        self,
        kis_client: KISClient,
        redis_manager: RedisManager,
        config: Optional[Dict[str, Any]] = None
    ):
        self.kis_client = kis_client
        self.redis_manager = redis_manager
        self.config = config or {}
        
        # KIS API 설정
        self.account_number = self.config.get("account_number")
        self.product_code = self.config.get("product_code", "01")  # 종합계좌
        
        # 주문 관련 설정
        self.default_order_type = self.config.get("default_order_type", "01")  # 지정가
        self.market_order_type = self.config.get("market_order_type", "01")    # 시장가
        
        # 캐시 설정
        self.cache_timeout = self.config.get("cache_timeout", 10)  # 10초
        self._position_cache = {}
        self._balance_cache = {}
        self._last_cache_update = {}
        
        logger.info("KISBrokerClient initialized")
    
    async def place_order(self, order: Order) -> OrderResult:
        """
        주문 제출
        
        Args:
            order: 제출할 주문 객체
            
        Returns:
            OrderResult: 주문 실행 결과
        """
        try:
            logger.info(f"Placing order: {order.order_id} - {order.side.value} {order.quantity} {order.symbol}")
            
            # KIS API 주문 파라미터 구성
            order_params = await self._build_order_params(order)
            
            # 주문 타입에 따른 API 호출
            if order.side == OrderSide.BUY:
                response = await self._place_buy_order(order_params)
            else:
                response = await self._place_sell_order(order_params)
            
            # 응답 처리
            if response and response.get("rt_cd") == "0":
                # 성공
                broker_order_id = response.get("output", {}).get("odno", "")
                
                # 주문 정보 캐시에 저장
                await self._cache_order_info(order.order_id, broker_order_id, order)
                
                return OrderResult(
                    order_id=order.order_id,
                    success=True,
                    broker_order_id=broker_order_id,
                    message="Order placed successfully",
                    metadata={
                        "response": response,
                        "kis_message": response.get("msg1", "")
                    }
                )
            else:
                # 실패
                error_msg = response.get("msg1", "Unknown error") if response else "No response"
                error_code = response.get("rt_cd", "UNKNOWN") if response else "NO_RESPONSE"
                
                return OrderResult(
                    order_id=order.order_id,
                    success=False,
                    message=f"Order placement failed: {error_msg}",
                    error_code=error_code,
                    metadata={"response": response}
                )
                
        except Exception as e:
            logger.error(f"Error placing order {order.order_id}: {e}")
            return OrderResult(
                order_id=order.order_id,
                success=False,
                message=f"Exception during order placement: {str(e)}",
                error_code="EXCEPTION"
            )
    
    async def cancel_order(self, order_id: str) -> OrderResult:
        """
        주문 취소
        
        Args:
            order_id: 취소할 주문 ID
            
        Returns:
            OrderResult: 취소 실행 결과
        """
        try:
            logger.info(f"Cancelling order: {order_id}")
            
            # 캐시에서 주문 정보 조회
            order_info = await self._get_cached_order_info(order_id)
            if not order_info:
                return OrderResult(
                    order_id=order_id,
                    success=False,
                    message="Order not found in cache",
                    error_code="ORDER_NOT_FOUND"
                )
            
            broker_order_id = order_info.get("broker_order_id")
            original_order = order_info.get("order")
            
            if not broker_order_id:
                return OrderResult(
                    order_id=order_id,
                    success=False,
                    message="Broker order ID not found",
                    error_code="BROKER_ORDER_ID_NOT_FOUND"
                )
            
            # KIS API 취소 파라미터 구성
            cancel_params = {
                "CANO": self.account_number.split("-")[0],
                "ACNT_PRDT_CD": self.account_number.split("-")[1],
                "KRX_FWDG_ORD_ORGNO": "",  # 한국거래소전송주문조직번호
                "ORGN_ODNO": broker_order_id,  # 원주문번호
                "ORD_DVSN": "00",  # 주문구분(취소)
                "RVSE_CNCL_DVSN_CD": "02",  # 정정취소구분코드(취소)
                "ORD_QTY": "0",  # 주문수량(취소시 0)
                "ORD_UNPR": "0",  # 주문단가(취소시 0)
                "QTY_ALL_ORD_YN": "Y"  # 잔량전부주문여부
            }
            
            # API 호출
            path = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
            response = await self.kis_client._make_api_request("POST", path, cancel_params)
            
            if response and response.get("rt_cd") == "0":
                # 성공
                return OrderResult(
                    order_id=order_id,
                    success=True,
                    message="Order cancelled successfully",
                    metadata={
                        "response": response,
                        "kis_message": response.get("msg1", "")
                    }
                )
            else:
                # 실패
                error_msg = response.get("msg1", "Unknown error") if response else "No response"
                error_code = response.get("rt_cd", "UNKNOWN") if response else "NO_RESPONSE"
                
                return OrderResult(
                    order_id=order_id,
                    success=False,
                    message=f"Order cancellation failed: {error_msg}",
                    error_code=error_code,
                    metadata={"response": response}
                )
                
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return OrderResult(
                order_id=order_id,
                success=False,
                message=f"Exception during order cancellation: {str(e)}",
                error_code="EXCEPTION"
            )
    
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """
        주문 상태 조회
        
        Args:
            order_id: 조회할 주문 ID
            
        Returns:
            Optional[Order]: 주문 객체 (없으면 None)
        """
        try:
            # 캐시에서 주문 정보 조회
            order_info = await self._get_cached_order_info(order_id)
            if not order_info:
                return None
            
            broker_order_id = order_info.get("broker_order_id")
            if not broker_order_id:
                return None
            
            # KIS API로 주문 상태 조회
            params = {
                "CANO": self.account_number.split("-")[0],
                "ACNT_PRDT_CD": self.account_number.split("-")[1],
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
                "INQR_DVSN": "00",  # 조회구분(전체)
                "ODNO": broker_order_id,  # 주문번호
                "INQR_STRT_DT": datetime.now().strftime("%Y%m%d"),  # 조회시작일자
                "INQR_END_DT": datetime.now().strftime("%Y%m%d")    # 조회종료일자
            }
            
            path = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
            response = await self.kis_client._make_api_request("GET", path, params)
            
            if response and response.get("rt_cd") == "0":
                # 주문 정보 파싱 및 Order 객체 업데이트
                output = response.get("output", [])
                if output:
                    order_data = output[0]  # 첫 번째 결과 사용
                    return await self._parse_order_from_kis_response(order_data, order_info["order"])
            
            return order_info["order"]  # 캐시된 주문 반환
            
        except Exception as e:
            logger.error(f"Error getting order status {order_id}: {e}")
            return None
    
    async def get_positions(self) -> List[Position]:
        """
        포지션 조회
        
        Returns:
            List[Position]: 포지션 목록
        """
        try:
            # 캐시 확인
            cache_key = "positions"
            if await self._is_cache_valid(cache_key):
                return self._position_cache.get(cache_key, [])
            
            # KIS API로 잔고 조회
            params = {
                "CANO": self.account_number.split("-")[0],
                "ACNT_PRDT_CD": self.account_number.split("-")[1],
                "AFHR_FLPR_YN": "N",  # 시간외단일가여부
                "OFL_YN": "",  # 오프라인여부
                "INQR_DVSN": "02",  # 조회구분(수량)
                "UNPR_DVSN": "01",  # 단가구분(기준가)
                "FUND_STTL_ICLD_YN": "N",  # 펀드결제분포함여부
                "FNCG_AMT_AUTO_RDPT_YN": "N",  # 융자금액자동상환여부
                "PRCS_DVSN": "01",  # 처리구분(전일매매포함)
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": ""
            }
            
            path = "/uapi/domestic-stock/v1/trading/inquire-balance"
            response = await self.kis_client._make_api_request("GET", path, params)
            
            positions = []
            if response and response.get("rt_cd") == "0":
                output1 = response.get("output1", [])
                
                for item in output1:
                    # 보유수량이 0이 아닌 것만 포지션으로 처리
                    quantity = int(item.get("hldg_qty", "0"))
                    if quantity > 0:
                        position = Position(
                            symbol=item.get("pdno", ""),  # 상품번호(종목코드)
                            quantity=quantity,
                            average_price=float(item.get("pchs_avg_pric", "0")),  # 매입평균가격
                            market_price=float(item.get("prpr", "0")),  # 현재가
                            unrealized_pnl=float(item.get("evlu_pfls_amt", "0")),  # 평가손익금액
                            total_commission=0.0,  # KIS API에서 제공하지 않음
                            updated_at=datetime.now()
                        )
                        positions.append(position)
            
            # 캐시 업데이트
            self._position_cache[cache_key] = positions
            self._last_cache_update[cache_key] = datetime.now()
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_account_balance(self) -> Dict[str, float]:
        """
        계좌 잔고 조회
        
        Returns:
            Dict[str, float]: 잔고 정보
        """
        try:
            # 캐시 확인
            cache_key = "balance"
            if await self._is_cache_valid(cache_key):
                return self._balance_cache.get(cache_key, {})
            
            # KIS API로 잔고 조회
            params = {
                "CANO": self.account_number.split("-")[0],
                "ACNT_PRDT_CD": self.account_number.split("-")[1],
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "01",  # 조회구분(금액)
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": ""
            }
            
            path = "/uapi/domestic-stock/v1/trading/inquire-balance"
            response = await self.kis_client._make_api_request("GET", path, params)
            
            balance_info = {}
            if response and response.get("rt_cd") == "0":
                output2 = response.get("output2", [])
                if output2:
                    data = output2[0]
                    balance_info = {
                        "total_assets": float(data.get("tot_evlu_amt", "0")),  # 총평가금액
                        "available_cash": float(data.get("ord_psbl_cash", "0")),  # 주문가능현금
                        "total_purchase_amount": float(data.get("pchs_amt_smtl_amt", "0")),  # 매입금액합계
                        "total_evaluation_amount": float(data.get("evlu_amt_smtl_amt", "0")),  # 평가금액합계
                        "total_profit_loss": float(data.get("evlu_pfls_smtl_amt", "0")),  # 평가손익합계
                        "deposit": float(data.get("dnca_tot_amt", "0"))  # 예수금총액
                    }
            
            # 캐시 업데이트
            self._balance_cache[cache_key] = balance_info
            self._last_cache_update[cache_key] = datetime.now()
            
            return balance_info
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return {}
    
    async def _build_order_params(self, order: Order) -> Dict[str, Any]:
        """주문 파라미터 구성"""
        # 주문구분 코드 결정
        if order.order_type == OrderType.MARKET:
            ord_dvsn = "01"  # 시장가
        elif order.order_type == OrderType.LIMIT:
            ord_dvsn = "00"  # 지정가
        else:
            ord_dvsn = "00"  # 기본값: 지정가
        
        # 주문가격 결정
        if order.order_type == OrderType.MARKET:
            ord_unpr = "0"  # 시장가는 0
        else:
            ord_unpr = str(int(order.price)) if order.price else "0"
        
        return {
            "CANO": self.account_number.split("-")[0],  # 종합계좌번호
            "ACNT_PRDT_CD": self.account_number.split("-")[1],  # 계좌상품코드
            "PDNO": order.symbol,  # 종목코드
            "ORD_DVSN": ord_dvsn,  # 주문구분
            "ORD_QTY": str(order.quantity),  # 주문수량
            "ORD_UNPR": ord_unpr,  # 주문단가
        }
    
    async def _place_buy_order(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """매수 주문 실행"""
        path = "/uapi/domestic-stock/v1/trading/order-cash"
        return await self.kis_client._make_api_request("POST", path, params)
    
    async def _place_sell_order(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """매도 주문 실행"""
        path = "/uapi/domestic-stock/v1/trading/order-cash"
        return await self.kis_client._make_api_request("POST", path, params)
    
    async def _cache_order_info(self, order_id: str, broker_order_id: str, order: Order):
        """주문 정보 캐시에 저장"""
        try:
            cache_key = f"order_info:{order_id}"
            order_info = {
                "order_id": order_id,
                "broker_order_id": broker_order_id,
                "order": order,
                "cached_at": datetime.now().isoformat()
            }
            
            # Redis에 24시간 동안 저장
            await self.redis_manager.set_data(cache_key, order_info, expire_seconds=24*3600)
            
        except Exception as e:
            logger.error(f"Error caching order info: {e}")
    
    async def _get_cached_order_info(self, order_id: str) -> Optional[Dict[str, Any]]:
        """캐시에서 주문 정보 조회"""
        try:
            cache_key = f"order_info:{order_id}"
            return await self.redis_manager.get_data(cache_key)
        except Exception as e:
            logger.error(f"Error getting cached order info: {e}")
            return None
    
    async def _parse_order_from_kis_response(self, kis_data: Dict[str, Any], original_order: Order) -> Order:
        """KIS API 응답에서 Order 객체 생성"""
        try:
            # 체결수량 및 상태 업데이트
            filled_qty = int(kis_data.get("tot_ccld_qty", "0"))  # 총체결수량
            order_status = kis_data.get("ord_stts_name", "")  # 주문상태명
            
            # 상태 매핑
            if "체결" in order_status:
                if filled_qty == original_order.quantity:
                    status = OrderStatus.FILLED
                else:
                    status = OrderStatus.PARTIAL_FILLED
            elif "취소" in order_status:
                status = OrderStatus.CANCELLED
            elif "거부" in order_status:
                status = OrderStatus.REJECTED
            else:
                status = OrderStatus.SUBMITTED
            
            # 주문 객체 업데이트
            original_order.status = status
            original_order.filled_quantity = filled_qty
            
            # 평균체결가격 업데이트
            if filled_qty > 0:
                avg_price = float(kis_data.get("avg_prvs", "0"))
                if avg_price > 0:
                    original_order.average_fill_price = avg_price
            
            original_order.updated_at = datetime.now()
            
            return original_order
            
        except Exception as e:
            logger.error(f"Error parsing order from KIS response: {e}")
            return original_order
    
    async def _is_cache_valid(self, cache_key: str) -> bool:
        """캐시 유효성 확인"""
        if cache_key not in self._last_cache_update:
            return False
        
        last_update = self._last_cache_update[cache_key]
        return (datetime.now() - last_update).total_seconds() < self.cache_timeout