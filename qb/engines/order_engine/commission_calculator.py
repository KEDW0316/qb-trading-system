"""
수수료 계산기 (Commission Calculator) 구현

QB Trading System의 거래 수수료 계산 시스템입니다.
한국 주식 시장의 수수료 체계에 맞춰 정확한 수수료를 계산합니다.
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

from .base import BaseCommissionCalculator, Order, OrderType, OrderSide

logger = logging.getLogger(__name__)


class KoreanStockCommissionCalculator(BaseCommissionCalculator):
    """
    한국 주식 수수료 계산기
    
    한국투자증권 기준 수수료 체계:
    1. 위탁수수료: 거래대금의 0.015% (최소 100원)
    2. 증권거래세: 매도시 거래대금의 0.23%
    3. 농어촌특별세: 증권거래세의 20%
    4. 거래소수수료: 거래대금의 0.0008%
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # 기본 수수료율 설정 (한국투자증권 기준)
        self.commission_rates = {
            # 위탁수수료율
            "brokerage_rate": Decimal(str(self.config.get("brokerage_rate", 0.00015))),  # 0.015%
            "min_brokerage_fee": Decimal(str(self.config.get("min_brokerage_fee", 100))),  # 최소 100원
            
            # 세금
            "transaction_tax_rate": Decimal(str(self.config.get("transaction_tax_rate", 0.0023))),  # 0.23% (매도시만)
            "rural_tax_rate": Decimal(str(self.config.get("rural_tax_rate", 0.2))),  # 증권거래세의 20%
            
            # 거래소수수료
            "exchange_fee_rate": Decimal(str(self.config.get("exchange_fee_rate", 0.000008))),  # 0.0008%
            
            # 기타
            "clearing_fee_rate": Decimal(str(self.config.get("clearing_fee_rate", 0.0000154))),  # 0.00154%
        }
        
        # 할인 설정
        self.discount_rates = {
            "vip_discount": Decimal(str(self.config.get("vip_discount", 0.5))),  # VIP 고객 50% 할인
            "online_discount": Decimal(str(self.config.get("online_discount", 0.2))),  # 온라인 거래 20% 할인
            "frequent_trader_discount": Decimal(str(self.config.get("frequent_trader_discount", 0.1))),  # 빈번한 거래자 10% 할인
        }
        
        # 종목별 특별 수수료 (ETF, 리츠 등)
        self.special_rates = self.config.get("special_rates", {})
        
        # 정밀도 설정
        self.precision = Decimal("0.01")  # 원 단위 반올림
        
        logger.info("KoreanStockCommissionCalculator initialized")
    
    def calculate_commission(self, order: Order, fill_price: float, fill_quantity: int) -> float:
        """
        수수료 계산
        
        Args:
            order: 주문 정보
            fill_price: 체결 가격
            fill_quantity: 체결 수량
            
        Returns:
            float: 총 수수료
        """
        try:
            # 거래대금 계산
            trade_amount = Decimal(str(fill_price)) * Decimal(str(fill_quantity))
            
            # 기본 수수료 계산
            total_commission = self._calculate_base_commission(order, trade_amount)
            
            # 세금 계산 (매도시만)
            if order.side == OrderSide.SELL:
                taxes = self._calculate_taxes(trade_amount)
                total_commission += taxes
            
            # 할인 적용
            total_commission = self._apply_discounts(order, total_commission)
            
            # 원 단위 반올림
            total_commission = total_commission.quantize(self.precision, rounding=ROUND_HALF_UP)
            
            logger.debug(f"Commission calculated: {order.symbol} - ₩{total_commission}")
            
            return float(total_commission)
            
        except Exception as e:
            logger.error(f"Error calculating commission: {e}")
            # 기본 수수료 반환 (거래대금의 0.1%)
            return float(fill_price * fill_quantity * 0.001)
    
    def get_commission_rate(self, symbol: str, order_type: OrderType) -> float:
        """
        수수료율 조회
        
        Args:
            symbol: 종목 코드
            order_type: 주문 타입
            
        Returns:
            float: 수수료율
        """
        try:
            # 특별 수수료율 확인
            if symbol in self.special_rates:
                return float(self.special_rates[symbol])
            
            # 기본 수수료율
            return float(self.commission_rates["brokerage_rate"])
            
        except Exception as e:
            logger.error(f"Error getting commission rate: {e}")
            return 0.00015  # 기본값
    
    def calculate_total_cost(self, order: Order, fill_price: float, fill_quantity: int) -> Dict[str, float]:
        """
        총 거래 비용 계산 (주문 금액 + 수수료)
        
        Args:
            order: 주문 정보
            fill_price: 체결 가격
            fill_quantity: 체결 수량
            
        Returns:
            Dict[str, float]: 상세 비용 내역
        """
        try:
            trade_amount = float(fill_price * fill_quantity)
            commission = self.calculate_commission(order, fill_price, fill_quantity)
            
            # 상세 수수료 계산
            commission_breakdown = self._get_commission_breakdown(order, Decimal(str(trade_amount)))
            
            if order.side == OrderSide.BUY:
                total_cost = trade_amount + commission
                net_amount = trade_amount
            else:  # SELL
                total_cost = trade_amount
                net_amount = trade_amount - commission
            
            return {
                "trade_amount": trade_amount,
                "total_commission": commission,
                "total_cost": total_cost,
                "net_amount": net_amount,
                "commission_breakdown": commission_breakdown
            }
            
        except Exception as e:
            logger.error(f"Error calculating total cost: {e}")
            return {
                "trade_amount": float(fill_price * fill_quantity),
                "total_commission": 0.0,
                "total_cost": float(fill_price * fill_quantity),
                "net_amount": float(fill_price * fill_quantity),
                "commission_breakdown": {}
            }
    
    def estimate_commission(self, symbol: str, side: OrderSide, quantity: int, price: float) -> float:
        """
        수수료 예상 계산 (주문 전 미리 계산)
        
        Args:
            symbol: 종목 코드
            side: 주문 방향
            quantity: 수량
            price: 가격
            
        Returns:
            float: 예상 수수료
        """
        try:
            # 임시 주문 객체 생성
            temp_order = Order(
                symbol=symbol,
                side=side,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=price
            )
            
            return self.calculate_commission(temp_order, price, quantity)
            
        except Exception as e:
            logger.error(f"Error estimating commission: {e}")
            return float(price * quantity * 0.001)  # 기본 추정치
    
    def _calculate_base_commission(self, order: Order, trade_amount: Decimal) -> Decimal:
        """기본 수수료 계산"""
        try:
            # 위탁수수료 계산
            brokerage_fee = trade_amount * self.commission_rates["brokerage_rate"]
            brokerage_fee = max(brokerage_fee, self.commission_rates["min_brokerage_fee"])
            
            # 거래소수수료 계산
            exchange_fee = trade_amount * self.commission_rates["exchange_fee_rate"]
            
            # 결제대행수수료 계산
            clearing_fee = trade_amount * self.commission_rates["clearing_fee_rate"]
            
            total_commission = brokerage_fee + exchange_fee + clearing_fee
            
            return total_commission
            
        except Exception as e:
            logger.error(f"Error calculating base commission: {e}")
            return trade_amount * Decimal("0.001")  # 기본값
    
    def _calculate_taxes(self, trade_amount: Decimal) -> Decimal:
        """세금 계산 (매도시만)"""
        try:
            # 증권거래세
            transaction_tax = trade_amount * self.commission_rates["transaction_tax_rate"]
            
            # 농어촌특별세 (증권거래세의 20%)
            rural_tax = transaction_tax * self.commission_rates["rural_tax_rate"]
            
            total_tax = transaction_tax + rural_tax
            
            return total_tax
            
        except Exception as e:
            logger.error(f"Error calculating taxes: {e}")
            return Decimal("0")
    
    def _apply_discounts(self, order: Order, commission: Decimal) -> Decimal:
        """할인 적용"""
        try:
            discount_rate = Decimal("0")
            
            # 메타데이터에서 할인 정보 확인
            if order.metadata:
                if order.metadata.get("vip_customer"):
                    discount_rate += self.discount_rates["vip_discount"]
                
                if order.metadata.get("online_order", True):  # 기본값: 온라인 주문
                    discount_rate += self.discount_rates["online_discount"]
                
                if order.metadata.get("frequent_trader"):
                    discount_rate += self.discount_rates["frequent_trader_discount"]
            
            # 최대 할인율 제한 (80%)
            discount_rate = min(discount_rate, Decimal("0.8"))
            
            discounted_commission = commission * (Decimal("1") - discount_rate)
            
            return discounted_commission
            
        except Exception as e:
            logger.error(f"Error applying discounts: {e}")
            return commission
    
    def _get_commission_breakdown(self, order: Order, trade_amount: Decimal) -> Dict[str, float]:
        """수수료 세부 내역"""
        try:
            # 위탁수수료
            brokerage_fee = trade_amount * self.commission_rates["brokerage_rate"]
            brokerage_fee = max(brokerage_fee, self.commission_rates["min_brokerage_fee"])
            
            # 거래소수수료
            exchange_fee = trade_amount * self.commission_rates["exchange_fee_rate"]
            
            # 결제대행수수료
            clearing_fee = trade_amount * self.commission_rates["clearing_fee_rate"]
            
            breakdown = {
                "brokerage_fee": float(brokerage_fee),
                "exchange_fee": float(exchange_fee),
                "clearing_fee": float(clearing_fee)
            }
            
            # 매도시 세금 추가
            if order.side == OrderSide.SELL:
                transaction_tax = trade_amount * self.commission_rates["transaction_tax_rate"]
                rural_tax = transaction_tax * self.commission_rates["rural_tax_rate"]
                
                breakdown.update({
                    "transaction_tax": float(transaction_tax),
                    "rural_tax": float(rural_tax)
                })
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Error getting commission breakdown: {e}")
            return {}
    
    def get_daily_commission_summary(self, fills: list) -> Dict[str, float]:
        """일일 수수료 요약"""
        try:
            total_commission = 0.0
            total_trades = len(fills)
            buy_commission = 0.0
            sell_commission = 0.0
            total_taxes = 0.0
            
            for fill in fills:
                commission = float(fill.commission)
                total_commission += commission
                
                if fill.side == OrderSide.BUY:
                    buy_commission += commission
                else:
                    sell_commission += commission
                    
                    # 매도 거래의 세금 계산
                    trade_amount = fill.price * fill.quantity
                    tax = float(trade_amount * (self.commission_rates["transaction_tax_rate"] + 
                                              self.commission_rates["transaction_tax_rate"] * self.commission_rates["rural_tax_rate"]))
                    total_taxes += tax
            
            return {
                "total_commission": total_commission,
                "total_trades": total_trades,
                "buy_commission": buy_commission,
                "sell_commission": sell_commission,
                "total_taxes": total_taxes,
                "average_commission_per_trade": total_commission / total_trades if total_trades > 0 else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating daily commission summary: {e}")
            return {}
    
    def update_commission_rates(self, new_rates: Dict[str, float]):
        """수수료율 업데이트"""
        try:
            for key, value in new_rates.items():
                if key in self.commission_rates:
                    self.commission_rates[key] = Decimal(str(value))
                    logger.info(f"Commission rate updated: {key} = {value}")
            
        except Exception as e:
            logger.error(f"Error updating commission rates: {e}")
    
    def set_special_rate(self, symbol: str, rate: float):
        """특정 종목의 특별 수수료율 설정"""
        try:
            self.special_rates[symbol] = rate
            logger.info(f"Special commission rate set: {symbol} = {rate}")
            
        except Exception as e:
            logger.error(f"Error setting special rate: {e}")


class ETFCommissionCalculator(KoreanStockCommissionCalculator):
    """ETF 전용 수수료 계산기"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # ETF 특별 수수료율 (일반적으로 더 낮음)
        self.commission_rates.update({
            "brokerage_rate": Decimal(str(self.config.get("etf_brokerage_rate", 0.00005))),  # 0.005%
            "min_brokerage_fee": Decimal(str(self.config.get("etf_min_brokerage_fee", 50))),  # 최소 50원
        })
        
        logger.info("ETFCommissionCalculator initialized")


class ForeignStockCommissionCalculator(BaseCommissionCalculator):
    """해외 주식 수수료 계산기"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # 해외 주식 수수료 (USD 기준)
        self.commission_rates = {
            "us_stock_rate": Decimal(str(self.config.get("us_stock_rate", 0.25))),  # $0.25 per share
            "min_commission": Decimal(str(self.config.get("min_commission", 0.99))),  # 최소 $0.99
            "max_commission": Decimal(str(self.config.get("max_commission", 19.99))),  # 최대 $19.99
        }
        
        logger.info("ForeignStockCommissionCalculator initialized")
    
    def calculate_commission(self, order: Order, fill_price: float, fill_quantity: int) -> float:
        """해외 주식 수수료 계산"""
        try:
            # 주당 수수료 방식
            commission = float(self.commission_rates["us_stock_rate"]) * fill_quantity
            
            # 최소/최대 수수료 적용
            commission = max(commission, float(self.commission_rates["min_commission"]))
            commission = min(commission, float(self.commission_rates["max_commission"]))
            
            return commission
            
        except Exception as e:
            logger.error(f"Error calculating foreign stock commission: {e}")
            return 0.99  # 기본 최소 수수료
    
    def get_commission_rate(self, symbol: str, order_type: OrderType) -> float:
        """해외 주식 수수료율 조회"""
        return float(self.commission_rates["us_stock_rate"])