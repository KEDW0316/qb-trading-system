"""
KIS API 래퍼 함수 테스트 스크립트
KIS API Wrapper Functions Test Script

Task 22.4에서 구현한 래퍼 함수들을 테스트하는 스크립트
"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qb.collectors.kis_client import KISClient


async def test_account_functions(client: KISClient):
    """계좌 관련 함수 테스트"""
    print("\n" + "="*50)
    print("📊 계좌 관련 함수 테스트")
    print("="*50)
    
    try:
        # 계좌 잔고 조회
        print("\n1. 계좌 잔고 조회 테스트...")
        balance = await client.get_account_balance()
        print(f"✅ 계좌 잔고 조회 성공")
        
        # 응답 구조 확인
        if balance.get('rt_cd') == '0':
            output1 = balance.get('output1', [])
            output2 = balance.get('output2', [])
            
            print(f"   📈 보유 종목 수: {len(output1)}개")
            if output1:
                print(f"   💰 첫 번째 보유 종목: {output1[0].get('pdno', 'N/A')} - {output1[0].get('prdt_name', 'N/A')}")
            
            if output2:
                for key, value in output2[0].items():
                    if '금액' in key or 'amt' in key.lower():
                        print(f"   💵 {key}: {value}")
        else:
            print(f"   ⚠️ 응답 코드: {balance.get('rt_cd')} - {balance.get('msg1', 'Unknown error')}")
    
    except Exception as e:
        print(f"❌ 계좌 잔고 조회 실패: {str(e)}")


async def test_market_data_functions(client: KISClient):
    """시세 정보 관련 함수 테스트"""
    print("\n" + "="*50)
    print("📈 시세 정보 관련 함수 테스트")
    print("="*50)
    
    test_symbols = ["005930", "000660"]  # 삼성전자, SK하이닉스
    
    for symbol in test_symbols:
        print(f"\n🔍 종목코드: {symbol}")
        
        try:
            # 현재가 조회
            print("   1. 현재가 조회...")
            price_data = await client.get_stock_price(symbol)
            
            if price_data.get('rt_cd') == '0':
                output = price_data.get('output', {})
                stock_name = output.get('hts_kor_isnm', 'N/A')
                current_price = output.get('stck_prpr', 'N/A')
                change_rate = output.get('prdy_ctrt', 'N/A')
                
                print(f"   ✅ {stock_name}: {current_price}원 ({change_rate}%)")
            else:
                print(f"   ⚠️ 현재가 조회 실패: {price_data.get('msg1', 'Unknown error')}")
        
        except Exception as e:
            print(f"   ❌ 현재가 조회 오류: {str(e)}")
        
        try:
            # 호가 정보 조회
            print("   2. 호가 정보 조회...")
            orderbook = await client.get_stock_orderbook(symbol)
            
            if orderbook.get('rt_cd') == '0':
                output = orderbook.get('output1', {})
                ask_price1 = output.get('askp1', 'N/A')
                bid_price1 = output.get('bidp1', 'N/A')
                
                print(f"   ✅ 매도1호가: {ask_price1}원, 매수1호가: {bid_price1}원")
            else:
                print(f"   ⚠️ 호가 조회 실패: {orderbook.get('msg1', 'Unknown error')}")
        
        except Exception as e:
            print(f"   ❌ 호가 조회 오류: {str(e)}")
        
        try:
            # 일봉 차트 조회 (최근 5일)
            print("   3. 일봉 차트 조회 (최근 5일)...")
            chart_data = await client.get_stock_daily_chart(symbol, period=5)
            
            if chart_data.get('rt_cd') == '0':
                output = chart_data.get('output', [])
                print(f"   ✅ 일봉 데이터 {len(output)}개 조회 성공")
                
                if output:
                    latest = output[0]
                    print(f"   📊 최근일: {latest.get('stck_bsop_date', 'N/A')} - "
                          f"종가: {latest.get('stck_clpr', 'N/A')}원")
            else:
                print(f"   ⚠️ 일봉 조회 실패: {chart_data.get('msg1', 'Unknown error')}")
        
        except Exception as e:
            print(f"   ❌ 일봉 조회 오류: {str(e)}")


async def test_order_functions(client: KISClient):
    """주문 관련 함수 테스트 (실제 주문 제외)"""
    print("\n" + "="*50)
    print("📋 주문 관련 함수 테스트")
    print("="*50)
    
    try:
        # 주문 내역 조회
        print("\n1. 주문 내역 조회 테스트...")
        order_history = await client.get_order_history()
        
        if order_history.get('rt_cd') == '0':
            output = order_history.get('output', [])
            print(f"✅ 주문 내역 {len(output)}건 조회 성공")
            
            if output:
                recent_order = output[0]
                print(f"   📝 최근 주문: {recent_order.get('pdno', 'N/A')} - "
                      f"{recent_order.get('ord_qty', 'N/A')}주 "
                      f"({recent_order.get('sll_buy_dvsn_cd_name', 'N/A')})")
            else:
                print("   📝 주문 내역이 없습니다.")
        else:
            print(f"⚠️ 주문 내역 조회 실패: {order_history.get('msg1', 'Unknown error')}")
    
    except Exception as e:
        print(f"❌ 주문 내역 조회 오류: {str(e)}")
    
    # 실제 주문은 테스트에서 제외 (안전상의 이유)
    print("\n⚠️ 실제 주문 기능(place_order, cancel_order, modify_order)은")
    print("   안전상의 이유로 이 테스트에서 제외되었습니다.")
    print("   필요시 별도로 테스트해주세요.")


async def test_rate_limiting(client: KISClient):
    """Rate Limiting 테스트"""
    print("\n" + "="*50)
    print("⏱️ Rate Limiting 테스트")
    print("="*50)
    
    print("\n연속 API 호출 테스트 (Rate Limiting 확인)...")
    
    test_symbol = "005930"  # 삼성전자
    
    for i in range(3):
        print(f"   {i+1}번째 호출...")
        
        try:
            start_time = asyncio.get_event_loop().time()
            await client.get_stock_price(test_symbol)
            end_time = asyncio.get_event_loop().time()
            
            elapsed = end_time - start_time
            print(f"   ✅ 응답 시간: {elapsed:.3f}초")
            
            # Rate limit 상태 확인
            rate_status = client.get_current_rate_limit_status()
            print(f"   📊 초당 요청: {rate_status['requests_last_second']}/{rate_status['max_requests_per_second']}")
            
        except Exception as e:
            print(f"   ❌ API 호출 실패: {str(e)}")


async def main():
    """메인 테스트 함수"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    print("🚀 KIS API 래퍼 함수 테스트 시작")
    print("="*60)
    
    try:
        # KIS 클라이언트 초기화 (실전투자 모드)
        logger.info("KIS 클라이언트 초기화 중...")
        client = KISClient(mode='prod')
        
        # 클라이언트 정보 출력
        print(f"\n📋 클라이언트 정보:")
        print(f"   모드: {'실전투자' if not client.is_paper_trading else '모의투자'}")
        print(f"   계좌: {client.account_info[0]}")
        
        # 토큰 확인
        token = client.auth.get_token()
        print(f"   토큰: {token.access_token[:20]}... (정상)")
        
        # 테스트 실행
        await test_account_functions(client)
        await test_market_data_functions(client)
        await test_order_functions(client)
        await test_rate_limiting(client)
        
        print("\n" + "="*60)
        print("🎉 모든 테스트 완료!")
        
        # 최종 요청 통계
        final_stats = client.get_current_rate_limit_status()
        print(f"\n📊 최종 통계:")
        print(f"   총 요청 수: {final_stats['daily_request_count']}")
        print(f"   현재 Rate Limit 상태: {final_stats['can_make_request']}")
        
    except Exception as e:
        logger.error(f"테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())