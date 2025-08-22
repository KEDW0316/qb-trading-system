"""
ABOUTME: Constants and configurations for US stock market
"""

from typing import Dict

# TR_ID 매핑 - 미국 주식
USA_TR_IDS = {
    "prod": {
        "current_price": "HHDFS00000300",     # 미국 현재가
        "daily_chart": "FHKST03030100",       # 미국 일봉/주봉/월봉
        "account_balance": "TTTS3012R",       # 미국 잔고
        "place_buy_order": "TTTT1002U",       # 미국 매수
        "place_sell_order": "TTTT1006U",      # 미국 매도
        "order_list": "TTTS3035R",            # 미국 주문내역
        "cancel_order": "TTTT1004U"           # 미국 주문취소/정정
    },
    "vps": {
        "current_price": "HHDFS00000300",     # 미국 현재가 (실전과 동일)
        "daily_chart": "FHKST03030100",       # 미국 일봉/주봉/월봉 (실전과 동일)
        "account_balance": "VTTS3012R",       # 미국 모의 잔고
        "place_buy_order": "VTTT1002U",       # 미국 모의 매수
        "place_sell_order": "VTTT1006U",      # 미국 모의 매도
        "order_list": "VTTS3035R",            # 미국 모의 주문내역
        "cancel_order": "VTTT1004U"           # 미국 모의 주문취소/정정
    }
}

# WebSocket TR_ID - 미국 주식
USA_WS_TR_IDS = {
    "quote": "HDFSASP0",        # 실시간 호가 (1호가 무료)
    "tick": "HDFSCNT0",         # 실시간 체결 (무료)
    "delayed_tick": "HDFSCNT2", # 지연 체결
    "notice": "H0GSCNI0"        # 체결 통보
}

# 미국 주식 호가 컬럼 (1호가만 무료)
USA_QUOTE_COLUMNS = [
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

# 미국 주식 체결 컬럼 (무료)
USA_TICK_COLUMNS = [
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

# 거래소 코드 매핑
EXCHANGE_CODE_MAP = {
    "NASD": "NAS",  # 나스닥
    "NYSE": "NYS",  # 뉴욕증권거래소
    "AMEX": "AMS",  # 아멕스
    # 주간거래
    "NASD_DAY": "BAQ",
    "NYSE_DAY": "BAY",
    "AMEX_DAY": "BAA"
}