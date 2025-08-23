import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.api.bithumb_api import BithumbAPI


def test_public_api():
    """공개 API 테스트"""
    print("=== 빗썸 공개 API 테스트 ===")
    
    api = BithumbAPI()
    
    # 1. 마켓 리스트 조회
    print("\n1. 마켓 리스트 조회:")
    market_list = api.get_market_list()
    print(f"결과: {market_list}")
    
    # 2. BTC 현재가 조회
    print("\n2. BTC 현재가 조회:")
    ticker = api.get_ticker("KRW-BTC")
    print(f"결과: {ticker}")
    
    # 3. BTC 호가 정보 조회
    print("\n3. BTC 호가 정보 조회:")
    orderbook = api.get_orderbook("KRW-BTC")
    print(f"결과: {orderbook}")
    
    # 4. BTC 캔들 데이터 조회
    print("\n4. BTC 캔들 데이터 조회:")
    candles = api.get_candles("KRW-BTC", "1m", 5)
    print(f"결과: {candles}")   
    


def test_private_api():
    """개인 API 테스트 (환경변수에서 API 키 로드)"""
    print("\n=== 빗썸 개인 API 테스트 (환경변수에서 API 키 로드) ===")
    
    api = BithumbAPI()  # 환경변수에서 API 키 자동 로드
    
    # 1. 계좌 정보 조회
    print("\n1. 계좌 정보 조회:")
    account = api.get_account_info()
    print(f"결과: {account}")
    
    # 2. 주문 리스트 조회
    print("\n2. 주문 리스트 조회:")
    orders = api.get_order_list()
    print(f"결과: {orders}")
    
    # 3. 주문 가능 정보 조회
    print("\n3. 주문 가능 정보 조회:")
    order_chance = api.get_order_chance("KRW-BTC")
    print(f"결과: {order_chance}")
    
    # 4. 실제 BTC 매수/매도 테스트 (10000원)
    print("\n4. 실제 BTC 매수/매도 테스트 (10000원):")
    
    # BTC 현재가 조회하여 매수 가격 결정
    print("BTC 현재가 조회 중...")
    ticker = api.get_ticker("KRW-BTC")
    print(f"전체 ticker 응답: {ticker}")
    
    # 실제 API 응답 구조에 맞게 현재가 추출
    if isinstance(ticker, list) and len(ticker) > 0 and "trade_price" in ticker[0]:
        current_price = float(ticker[0]["trade_price"])
        # 10000원으로 살 수 있는 BTC 수량 계산 (최소 수량 고려)
        volume = max(10000 / current_price, 0.0001)  # 최소 0.0001 BTC
        print(f"BTC 현재가: {current_price:,}원")
        print(f"10000원으로 매수 가능한 BTC 수량: {volume:.8f}")
        
        # BTC 매수 주문 (지정가) - 3만원치로 현재가에 매수
        print("BTC 매수 주문 진행 중...")
        buy_price = int(current_price)  # 현재 BTC 가격 사용
        buy_volume = 30000 / current_price  # 3만원으로 살 수 있는 BTC 수량
        buy_order = api.place_order(
            market="KRW-BTC",
            side="bid",
            order_type="limit",
            price=buy_price,
            volume=buy_volume
        )
        print(f"매수 주문 결과: {buy_order}")
        
        # 에러가 발생한 경우 더 자세한 정보 출력
        if "status" in buy_order and buy_order["status"] == "error":
            print(f"매수 주문 에러 상세: {buy_order}")
            print(f"사용된 파라미터: market=KRW-BTC, side=bid, order_type=limit, price={buy_price}, volume={buy_volume}")
        
        # 잠시 대기 후 매도 주문
        import time
        print("5초 대기 후 매도 주문 진행...")
        time.sleep(5)
        
        # BTC 매도 주문 (지정가) - 3만원치로 현재가에 매도
        print("BTC 매도 주문 진행 중...")
        sell_price = int(current_price)  # 현재 BTC 가격 사용
        sell_volume = buy_volume  # 매수한 수량만큼 매도
        sell_order = api.place_order(
            market="KRW-BTC",
            side="ask",
            order_type="limit",
            price=sell_price,
            volume=sell_volume
        )
        print(f"매도 주문 결과: {sell_order}")
        
        # 에러가 발생한 경우 더 자세한 정보 출력
        if "status" in sell_order and sell_order["status"] == "error":
            print(f"매도 주문 에러 상세: {sell_order}")
            print(f"사용된 파라미터: market=KRW-BTC, side=ask, order_type=limit, price={sell_price}, volume={sell_volume}")
        
    else:
        print("BTC 현재가 조회 실패")
        print("응답 구조 확인:")
        if isinstance(ticker, list) and len(ticker) > 0:
            print(f"첫 번째 요소의 키들: {list(ticker[0].keys())}")
        else:
            print("응답이 리스트가 아니거나 비어있음")


def test_api_key_status():
    """API 키 상태 확인"""
    print("\n=== API 키 상태 확인 ===")
    
    api = BithumbAPI()
    print(f"API 키 존재 여부: {'있음' if api.api_key else '없음'}")
    print(f"시크릿 키 존재 여부: {'있음' if api.secret_key else '없음'}")
    
    if api.api_key and api.secret_key:
        print("✅ 환경변수에서 API 키를 성공적으로 로드했습니다.")
    else:
        print("❌ 환경변수에서 API 키를 로드하지 못했습니다.")


if __name__ == "__main__":
    test_api_key_status()
    test_public_api()
    test_private_api()
