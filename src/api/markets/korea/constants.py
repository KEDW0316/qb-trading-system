"""
ABOUTME: Constants and configurations for Korean stock market
"""

from typing import Dict

# TR_ID 매핑 - 한국 주식
KOREA_TR_IDS = {
    "prod": {
        "current_price": "FHKST01010100",     # 실전 현재가
        "daily_chart": "FHKST01010400",       # 실전 일봉
        "account_balance": "TTTC8434R",       # 실전 잔고
        "place_buy_order": "TTTC0802U",       # 실전 매수
        "place_sell_order": "TTTC0801U",      # 실전 매도
        "order_list": "TTTC8001R",            # 실전 주문내역
        "cancel_order": "TTTC0803U"           # 실전 주문취소
    },
    "vps": {
        "current_price": "FHKST01010100",     # 모의 현재가 (실전과 동일)
        "daily_chart": "FHKST01010400",       # 모의 일봉 (실전과 동일)
        "account_balance": "VTTC8434R",       # 모의 잔고
        "place_buy_order": "VTTC0802U",       # 모의 매수
        "place_sell_order": "VTTC0801U",      # 모의 매도
        "order_list": "VTTC8001R",            # 모의 주문내역
        "cancel_order": "VTTC0803U"           # 모의 주문취소
    }
}

# WebSocket TR_ID - 한국 주식
KOREA_WS_TR_IDS = {
    "quote": "H0STASP0",      # 실시간 호가
    "tick": "H0STCNT0",       # 실시간 체결
    "night_quote": "H0NXASP0" # 야간 호가
}

# 한국 주식 호가 컬럼
KOREA_QUOTE_COLUMNS = [
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

# 한국 주식 체결 컬럼
KOREA_TICK_COLUMNS = [
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