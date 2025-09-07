import sys
import os
import json
import time
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.api.bithumb_api import BithumbAPI


class BithumbResponseCapture:
    """빗썸 API 응답 캡처 및 문서화 클래스"""
    
    def __init__(self):
        self.api = BithumbAPI()
        self.responses = {}
        self.output_file = "bithumb_api_responses.json"
        self.markdown_file = "bithumb_api_responses.md"
        
    def capture_response(self, function_name, response, description="", input_params=None):
        """응답 데이터 캡처"""
        self.responses[function_name] = {
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "input_params": input_params or {},
            "response": response,
            "response_type": type(response).__name__,
            "response_length": len(str(response)) if response else 0
        }
        print(f"✅ {function_name}: 응답 캡처 완료")
        
    def test_public_api_responses(self):
        """공개 API 응답 캡처"""
        print("=== 공개 API 응답 캡처 시작 ===")
        
        try:
            # 1. 마켓 리스트 조회
            print("\n1. 마켓 리스트 조회 중...")
            market_list = self.api.get_market_list()
            self.capture_response(
                "get_market_list", 
                market_list, 
                "마켓 리스트 조회 - 거래 가능한 모든 마켓 정보",
                {"function": "get_market_list()", "params": "없음"}
            )
            
            # 2. BTC 현재가 조회
            print("2. BTC 현재가 조회 중...")
            market = "KRW-BTC"
            ticker = self.api.get_ticker(market)
            self.capture_response(
                "get_ticker", 
                ticker, 
                "현재가 조회 - BTC의 실시간 거래 정보",
                {"function": "get_ticker(market)", "params": {"market": market}}
            )
            
            # 3. BTC 호가 정보 조회
            print("3. BTC 호가 정보 조회 중...")
            market = "KRW-BTC"
            orderbook = self.api.get_orderbook(market)
            self.capture_response(
                "get_orderbook", 
                orderbook, 
                "호가 정보 조회 - BTC의 매수/매도 호가 정보",
                {"function": "get_orderbook(market)", "params": {"market": market}}
            )
            
            # 4. BTC 캔들 데이터 조회
            print("4. BTC 캔들 데이터 조회 중...")
            market = "KRW-BTC"
            unit = "days"
            count = 5
            candles = self.api.get_candles(market, unit, count)
            self.capture_response(
                "get_candles", 
                candles, 
                "캔들 데이터 조회 - BTC의 1분봉 5개 데이터",
                {"function": "get_candles(market, unit, count)", "params": {"market": market, "unit": unit, "count": count}}
            )
            
            # 5. BTC 일봉 데이터 조회 (새로 추가된 함수)
            print("5. BTC 일봉 데이터 조회 중...")
            daily_count = 30
            daily_candles = self.api.get_daily_candles(market=market, count=daily_count)
            self.capture_response(
                "get_daily_candles", 
                daily_candles, 
                "일봉 데이터 조회 - BTC의 30일 일봉 데이터",
                {"function": "get_daily_candles(market, count)", "params": {"market": market, "count": daily_count}}
            )
            
        except Exception as e:
            print(f"❌ 공개 API 테스트 중 오류 발생: {e}")
            
    def test_private_api_responses(self):
        """개인 API 응답 캡처"""
        print("\n=== 개인 API 응답 캡처 시작 ===")
        
        # API 키 상태 확인
        if not self.api.api_key or not self.api.secret_key:
            print("⚠️ API 키가 설정되지 않아 개인 API 테스트를 건너뜁니다.")
            print("환경변수 BIT_APP_KEY와 BIT_APP_SECRET을 설정하세요.")
            return
            
        try:
            # 1. 계좌 정보 조회
            print("\n1. 계좌 정보 조회 중...")
            account = self.api.get_account_info()
            self.capture_response(
                "get_account_info", 
                account, 
                "계좌 정보 조회 - 보유 자산 및 잔고 정보",
                {"function": "get_account_info()", "params": "없음"}
            )
            
            # 2. 주문 리스트 조회
            print("2. 주문 리스트 조회 중...")
            orders = self.api.get_order_list()
            self.capture_response(
                "get_order_list", 
                orders, 
                "주문 리스트 조회 - 현재 주문 상태 및 이력",
                {"function": "get_order_list()", "params": "없음"}
            )
            
            # 3. 주문 가능 정보 조회
            print("3. 주문 가능 정보 조회 중...")
            market = "KRW-BTC"
            order_chance = self.api.get_order_chance(market)
            self.capture_response(
                "get_order_chance", 
                order_chance, 
                "주문 가능 정보 조회 - BTC 거래 가능 정보 및 수수료",
                {"function": "get_order_chance(market)", "params": {"market": market}}
            )
            
        except Exception as e:
            print(f"❌ 개인 API 테스트 중 오류 발생: {e}")
            
    def test_order_creation(self):
        """주문 생성 테스트 (실제 거래 없이)"""
        print("\n=== 주문 생성 테스트 시작 ===")
        
        if not self.api.api_key or not self.api.secret_key:
            print("⚠️ API 키가 설정되지 않아 주문 테스트를 건너뜁니다.")
            return
            
        try:
            # BTC 현재가 조회하여 테스트 가격 결정
            print("BTC 현재가 조회 중...")
            ticker = self.api.get_ticker("KRW-BTC")
            
            if isinstance(ticker, list) and len(ticker) > 0:
                current_price = float(ticker[0].get("trade_price", 45000000))
                test_price = int(current_price * 0.9)  # 현재가의 90%로 테스트 주문
                test_volume = 0.0001  # 최소 주문 수량
                
                print(f"테스트 주문 가격: {test_price:,}원, 수량: {test_volume} BTC")
                
                # 테스트 매수 주문 (낮은 가격으로 체결되지 않도록)
                print("테스트 매수 주문 생성 중...")
                buy_order = self.api.place_order(
                    market="KRW-BTC",
                    side="bid",
                    order_type="limit",
                    price=test_price,
                    volume=test_volume
                )
                self.capture_response(
                    "place_order_buy", 
                    buy_order, 
                    "매수 주문 생성 - 지정가 매수 주문 응답",
                    {
                        "function": "place_order(market, side, order_type, price, volume)",
                        "params": {
                            "market": "KRW-BTC",
                            "side": "bid",
                            "order_type": "limit",
                            "price": test_price,
                            "volume": test_volume
                        }
                    }
                )
                
                # 주문 취소 (테스트용이므로)
                if "uuid" in buy_order:
                    print("테스트 주문 취소 중...")
                    cancel_result = self.api.cancel_order(buy_order["uuid"])
                    self.capture_response(
                        "cancel_order", 
                        cancel_result, 
                        "주문 취소 - 주문 취소 응답",
                        {
                            "function": "cancel_order(uuid)",
                            "params": {"uuid": buy_order["uuid"]}
                        }
                    )
                    
        except Exception as e:
            print(f"❌ 주문 테스트 중 오류 발생: {e}")
            
    def save_responses_to_json(self):
        """응답 데이터를 JSON 파일로 저장"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.responses, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n✅ 응답 데이터를 {self.output_file}에 저장했습니다.")
        except Exception as e:
            print(f"❌ JSON 파일 저장 실패: {e}")
            
    def generate_markdown_documentation(self):
        """응답 데이터를 마크다운 문서로 생성"""
        try:
            with open(self.markdown_file, 'w', encoding='utf-8') as f:
                f.write("# Bithumb API 실제 응답 데이터 문서\n\n")
                f.write(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("이 문서는 실제 API 호출 결과를 바탕으로 작성되었습니다.\n\n")
                
                for func_name, data in self.responses.items():
                    f.write(f"## {func_name}\n\n")
                    f.write(f"**설명**: {data['description']}\n\n")
                    f.write(f"**함수 호출**: `{data['input_params']['function']}`\n\n")
                    f.write(f"**입력 파라미터**:\n")
                    f.write("```json\n")
                    f.write(json.dumps(data['input_params']['params'], ensure_ascii=False, indent=2, default=str))
                    f.write("\n```\n\n")
                    f.write(f"**응답 타입**: {data['response_type']}\n\n")
                    f.write(f"**응답 길이**: {data['response_length']} 문자\n\n")
                    f.write(f"**캡처 시간**: {data['timestamp']}\n\n")
                    
                    f.write("**응답 데이터**:\n")
                    f.write("```json\n")
                    f.write(json.dumps(data['response'], ensure_ascii=False, indent=2, default=str))
                    f.write("\n```\n\n")
                    
                    f.write("---\n\n")
                    
            print(f"✅ 마크다운 문서를 {self.markdown_file}에 생성했습니다.")
            
        except Exception as e:
            print(f"❌ 마크다운 문서 생성 실패: {e}")
            
    def print_summary(self):
        """캡처된 응답 요약 출력"""
        print("\n" + "="*60)
        print("📊 응답 캡처 요약")
        print("="*60)
        
        for func_name, data in self.responses.items():
            status = "✅" if data['response'] else "❌"
            print(f"{status} {func_name}: {data['description']}")
            print(f"   함수: {data['input_params']['function']}")
            print(f"   응답 타입: {data['response_type']}, 길이: {data['response_length']}")
            
        print(f"\n📁 저장된 파일:")
        print(f"   JSON: {self.output_file}")
        print(f"   Markdown: {self.markdown_file}")
        
    def run_all_tests(self):
        """모든 테스트 실행"""
        print("🚀 Bithumb API 응답 캡처 테스트 시작!")
        print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 공개 API 테스트
        self.test_public_api_responses()
        
        # 개인 API 테스트
        self.test_private_api_responses()
        
        # 주문 테스트
        self.test_order_creation()
        
        # 결과 저장
        self.save_responses_to_json()
        self.generate_markdown_documentation()
        
        # 요약 출력
        self.print_summary()
        
        print(f"\n🎉 모든 테스트 완료! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """메인 실행 함수"""
    capture = BithumbResponseCapture()
    capture.run_all_tests()


if __name__ == "__main__":
    main()
