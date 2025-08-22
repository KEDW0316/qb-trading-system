"""
ABOUTME: Market and exchange enumerations for stock trading API
"""

from enum import Enum


class Market(Enum):
    """시장 구분"""
    KOREA = "KR"
    USA = "US"
    JAPAN = "JP"
    HONGKONG = "HK"
    CHINA = "CN"
    VIETNAM = "VN"


class KoreaExchange(Enum):
    """한국 거래소 코드"""
    KOSPI = "UN"      # 유가증권
    KOSDAQ = "UQ"     # 코스닥
    KONEX = "UK"      # 코넥스
    KRX = "KRX"       # 정규장
    NXT = "NXT"       # 야간거래
    SOR = "SOR"       # 스마트라우팅


class USExchange(Enum):
    """미국 거래소 코드"""
    NASDAQ = "NASD"
    NYSE = "NYSE"
    AMEX = "AMEX"
    # 주간거래
    NASDAQ_DAY = "BAQ"
    NYSE_DAY = "BAY"
    AMEX_DAY = "BAA"


class OrderType(Enum):
    """주문 유형"""
    BUY = "buy"
    SELL = "sell"


class OrderDiv(Enum):
    """주문 구분"""
    # 한국
    KR_LIMIT = "00"       # 지정가
    KR_MARKET = "01"      # 시장가
    KR_CONDITIONAL = "03" # 조건부지정가
    # 미국
    US_LIMIT = "00"       # 지정가
    US_LOO = "32"         # LOO (Limit on Open)
    US_LOC = "34"         # LOC (Limit on Close)


class PriceUnit(Enum):
    """가격 단위"""
    KRW = "KRW"  # 원화
    USD = "USD"  # 달러
    JPY = "JPY"  # 엔화
    HKD = "HKD"  # 홍콩달러
    CNY = "CNY"  # 위안화
    EUR = "EUR"  # 유로