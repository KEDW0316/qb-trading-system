#!/usr/bin/env python3
"""
Mock KIS Adapter 기본 동작 테스트
"""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from tests.mock_kis_adapter import MockKISDataAdapter


async def test_basic_functionality():
    """기본 기능 테스트"""
    print("🎭 Testing Mock KIS Adapter Basic Functionality")
    print("=" * 60)
    
    # 어댑터 초기화
    config = {
        'tick_interval': 0.5,  # 0.5초마다 데이터 생성
        'mode': 'mock'
    }
    
    adapter = MockKISDataAdapter(config)
    
    try:
        # 1. 연결 테스트
        print("1️⃣ Testing connection...")
        connected = await adapter.connect()
        print(f"   Connection result: {'✅ Success' if connected else '❌ Failed'}")
        
        if not connected:
            return
        
        # 2. 심볼 구독 테스트
        print("\n2️⃣ Testing symbol subscription...")
        symbols = ["005930", "000660"]
        for symbol in symbols:
            subscribed = await adapter.subscribe_symbol(symbol)
            print(f"   Subscribe {symbol}: {'✅ Success' if subscribed else '❌ Failed'}")
        
        # 3. 데이터 생성 대기 및 수집
        print("\n3️⃣ Waiting for data generation...")
        await asyncio.sleep(3)  # 3초 대기
        
        # 4. 데이터 수집 테스트
        print("\n4️⃣ Testing data collection...")
        messages = await adapter.collect_data()
        print(f"   Collected {len(messages)} messages")
        
        # 5. 메시지 분석
        if messages:
            print("\n5️⃣ Analyzing messages...")
            trade_msgs = [m for m in messages if m.get('message_type') == 'trade']
            orderbook_msgs = [m for m in messages if m.get('message_type') == 'orderbook']
            
            print(f"   Trade messages: {len(trade_msgs)}")
            print(f"   Orderbook messages: {len(orderbook_msgs)}")
            
            # 첫 번째 거래 메시지 샘플 출력
            if trade_msgs:
                sample = trade_msgs[0]
                print(f"\n   📊 Sample Trade Message:")
                print(f"      Symbol: {sample.get('symbol')}")
                print(f"      Price: ₩{sample.get('close'):,}")
                print(f"      Volume: {sample.get('volume'):,}")
                print(f"      Timestamp: {sample.get('timestamp')}")
            
            # 첫 번째 호가 메시지 샘플 출력
            if orderbook_msgs:
                sample = orderbook_msgs[0]
                print(f"\n   📋 Sample Orderbook Message:")
                print(f"      Symbol: {sample.get('symbol')}")
                print(f"      Bid Price: ₩{sample.get('bid_price'):,}")
                print(f"      Ask Price: ₩{sample.get('ask_price'):,}")
                print(f"      Timestamp: {sample.get('timestamp')}")
        
        # 6. 어댑터 상태 확인
        print("\n6️⃣ Checking adapter status...")
        status = adapter.get_status()
        print(f"   Status: {status.get('status')}")
        print(f"   Messages Received: {status.get('messages_received')}")
        print(f"   Current Prices:")
        for symbol, price in status.get('current_prices', {}).items():
            print(f"      {symbol}: ₩{price:,.0f}")
        
        # 7. 동적 설정 변경 테스트
        print("\n7️⃣ Testing dynamic configuration...")
        adapter.set_tick_interval(0.2)  # 더 빠르게
        adapter.set_volatility("005930", 0.05)  # 변동성 증가
        adapter.set_trend("005930", 0.5)  # 상승 추세
        
        print("   Settings changed - waiting for more data...")
        await asyncio.sleep(2)
        
        new_messages = await adapter.collect_data()
        print(f"   Collected {len(new_messages)} new messages with updated settings")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 8. 연결 해제
        print("\n8️⃣ Disconnecting...")
        disconnected = await adapter.disconnect()
        print(f"   Disconnect result: {'✅ Success' if disconnected else '❌ Failed'}")
    
    print("\n🎉 Basic functionality test complete!")


async def test_data_quality():
    """데이터 품질 테스트"""
    print("\n🔍 Testing Data Quality")
    print("=" * 60)
    
    config = {'tick_interval': 0.1}  # 빠른 데이터 생성
    adapter = MockKISDataAdapter(config)
    
    try:
        await adapter.connect()
        await adapter.subscribe_symbol("005930")
        
        # 3초 동안 데이터 수집
        await asyncio.sleep(3)
        messages = await adapter.collect_data()
        
        if not messages:
            print("❌ No messages received")
            return
        
        trade_messages = [m for m in messages if m.get('message_type') == 'trade']
        
        if len(trade_messages) < 10:
            print(f"⚠️ Too few trade messages: {len(trade_messages)}")
            return
        
        # 가격 연속성 체크
        prices = [m['close'] for m in trade_messages]
        price_changes = []
        
        for i in range(1, len(prices)):
            change_rate = abs(prices[i] - prices[i-1]) / prices[i-1]
            price_changes.append(change_rate)
        
        avg_change = sum(price_changes) / len(price_changes)
        max_change = max(price_changes)
        
        print(f"   💹 Price Analysis:")
        print(f"      Total messages: {len(trade_messages)}")
        print(f"      Price range: ₩{min(prices):,.0f} - ₩{max(prices):,.0f}")
        print(f"      Average change rate: {avg_change:.4f} ({avg_change*100:.2f}%)")
        print(f"      Maximum change rate: {max_change:.4f} ({max_change*100:.2f}%)")
        
        # 합리적인 변동성인지 체크
        if 0.001 < avg_change < 0.1:  # 0.1% ~ 10% 변동성
            print("   ✅ Price volatility looks reasonable")
        else:
            print("   ⚠️ Price volatility might be too extreme")
        
        # 호가 데이터 품질 체크
        orderbook_messages = [m for m in messages if m.get('message_type') == 'orderbook']
        if orderbook_messages:
            print(f"\n   📋 Orderbook Analysis:")
            print(f"      Orderbook messages: {len(orderbook_messages)}")
            
            # 호가 스프레드 분석
            spreads = []
            for msg in orderbook_messages:
                bid = msg.get('bid_price', 0)
                ask = msg.get('ask_price', 0)
                if bid > 0 and ask > 0:
                    spread = (ask - bid) / bid
                    spreads.append(spread)
            
            if spreads:
                avg_spread = sum(spreads) / len(spreads)
                print(f"      Average spread: {avg_spread:.4f} ({avg_spread*100:.2f}%)")
                
                if 0.001 < avg_spread < 0.02:  # 0.1% ~ 2% 스프레드
                    print("   ✅ Orderbook spreads look reasonable")
                else:
                    print("   ⚠️ Orderbook spreads might be unusual")
        
    except Exception as e:
        print(f"❌ Data quality test failed: {e}")
    finally:
        await adapter.disconnect()
    
    print("🔍 Data quality test complete!")


async def main():
    """메인 함수"""
    # 로깅 설정
    logging.basicConfig(level=logging.WARNING)  # 경고 이상만 출력
    
    print("🎭 Mock KIS Adapter Test Suite")
    print("=" * 60)
    
    try:
        # 기본 기능 테스트
        await test_basic_functionality()
        
        # 데이터 품질 테스트
        await test_data_quality()
        
        print("\n🎉 All tests completed successfully!")
        
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())