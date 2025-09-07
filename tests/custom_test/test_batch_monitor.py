import sys
import os
import asyncio
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.strategy.batch_volume_monitor import BatchVolumeMonitor
from src.api.bithumb_api import BithumbAPI


async def test_batch_monitor():
    """실전 배치 모니터링 - 전체 종목 매수 조건 체크"""
    print("🚀 실전 배치 모니터링 시작!")
    
    try:
        # API 초기화
        api = BithumbAPI()
        
        # 모니터 초기화
        monitor = BatchVolumeMonitor(api)
        
        print("\n1️⃣ 초기화 중...")
        success = await monitor.initialize()
        
        if success:
            print(f"✅ 초기화 성공! {len(monitor.markets)}개 종목 발견")
            
            # 전체 종목을 실제로 체크
            print(f"\n2️⃣ 전체 종목 매수 조건 체크 시작...")
            print(f"   배치 크기: {monitor.batch_size}개")
            print(f"   지연 시간: {monitor.delay}초")
            print(f"   예상 소요 시간: {len(monitor.markets) // monitor.batch_size * monitor.delay:.0f}초")
            
            # 실제 배치 처리 실행
            start_time = time.time()
            await monitor.process_all_markets()
            elapsed = time.time() - start_time
            
            print(f"\n⏱️ 전체 처리 완료: {elapsed:.1f}초 소요")
            
            # 매수 조건 만족 종목 요약
            buy_candidates = []
            for market, condition in monitor.market_conditions.items():
                if condition.is_sideways and condition.is_volume_explosion and condition.is_bullish_candle:
                    buy_candidates.append({
                        'market': market,
                        'volume_multiplier': condition.volume_multiplier,
                        'current_price': condition.current_price
                    })
            
            print(f"\n🎯 매수 조건 만족 종목: {len(buy_candidates)}개")
            if buy_candidates:
                print("="*60)
                for candidate in sorted(buy_candidates, key=lambda x: x['volume_multiplier'], reverse=True):
                    print(f"   {candidate['market']}: 거래량 {candidate['volume_multiplier']:.1f}배, 현재가 {candidate['current_price']:,.0f}원")
                print("="*60)
            else:
                print("   현재 매수 조건을 만족하는 종목이 없습니다.")
            
        else:
            print("❌ 초기화 실패")
            
    except Exception as e:
        print(f"❌ 실전 모니터링 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


async def test_single_market():
    """단일 종목 조건 체크 테스트"""
    print("\n🔍 단일 종목 조건 체크 테스트...")
    
    try:
        api = BithumbAPI()
        monitor = BatchVolumeMonitor(api)
        
        # BTC만 테스트
        market = "KRW-BTC"
        print(f"테스트 종목: {market}")
        
        # 조건 체크
        condition = await monitor.check_market_conditions(market)
        
        # 매수 조건만 간단히 표시
        is_buy_condition = condition.is_sideways and condition.is_volume_explosion and condition.is_bullish_candle
        
        if is_buy_condition:
            print(f"🎯 {market}: 매수 조건 만족!")
        else:
            print(f"⚠️ {market}: 매수 조건 불만족")
                
    except Exception as e:
        print(f"❌ 단일 종목 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()


async def test_continuous_monitoring():
    """연속 순환 모니터링 테스트 (3사이클만 실행)"""
    print("\n🔄 연속 순환 모니터링 테스트 시작!")
    print("="*60)
    
    try:
        # API 초기화
        api = BithumbAPI()
        monitor = BatchVolumeMonitor(api)
        
        # 초기화
        print("🚀 초기화 중...")
        success = await monitor.initialize()
        
        if not success:
            print("❌ 초기화 실패")
            return
        
        print(f"✅ 초기화 완료! {len(monitor.markets)}개 종목 발견")
        
        # 배치 크기와 지연 시간 설정
        batch_size = 10
        delay = 1.0
        
        print(f"\n⚙️ 배치 설정:")
        print(f"   배치 크기: {batch_size}개")
        print(f"   지연 시간: {delay}초")
        print(f"   전체 배치 수: {(len(monitor.markets) + batch_size - 1) // batch_size}개")
        print(f"   전체 스캔 시간: {(len(monitor.markets) + batch_size - 1) // batch_size}초")
        
        # 3사이클만 실행 (테스트용)
        print(f"\n🧪 테스트용 3사이클 실행 (Ctrl+C로 중단 가능)")
        print("="*60)
        
        total_start_time = time.time()
        cycle_count = 0
        
        try:
            while cycle_count < 3:  # 3사이클만 실행
                cycle_start = time.time()
                cycle_count += 1
                
                print(f"\n🔄 사이클 {cycle_count}/3 시작! ({time.strftime('%H:%M:%S')})")
                print("-" * 40)
                
                # 전체 마켓을 배치로 순차 처리
                for i in range(0, len(monitor.markets), batch_size):
                    batch_start = time.time()
                    batch = monitor.markets[i:i + batch_size]
                    batch_num = i // batch_size + 1
                    total_batches = (len(monitor.markets) + batch_size - 1) // batch_size
                    
                    print(f"📦 배치 {batch_num}/{total_batches} 처리 중...")
                    print(f"   처리할 종목들: {batch}")
                    print(f"   시작 시간: {time.strftime('%H:%M:%S')}")
                    
                    # 실제 배치 처리 및 매수 조건 체크
                    print("   🔍 종목별 조건 체크 중...")
                    
                    for j, market in enumerate(batch):
                        print(f"     [{j+1:2d}/{len(batch)}] {market} 체크 중...", end="")
                        
                        try:
                            # 실제 매수 조건 체크
                            condition = await monitor.check_market_conditions(market)
                            
                            # 매수 조건 만족 여부만 간단히 표시
                            if condition.is_sideways and condition.is_volume_explosion and condition.is_bullish_candle:
                                print(" 🎯")  # 매수 조건 만족
                            else:
                                print(" ⚠️")  # 매수 조건 불만족
                                
                        except Exception as e:
                            print(f" ❌")  # 오류 발생
                        
                        # 짧은 대기
                        await asyncio.sleep(0.1)
                    
                    batch_elapsed = time.time() - batch_start
                    print(f"   ⏱️ 배치 처리 완료: {batch_elapsed:.2f}초")
                    
                    # 다음 배치까지 대기 (마지막 배치가 아닌 경우)
                    if i + batch_size < len(monitor.markets):
                        print(f"   ⏳ 다음 배치까지 {delay}초 대기...")
                        await asyncio.sleep(delay)
                    else:
                        print("   ✅ 마지막 배치 완료!")
                
                cycle_time = time.time() - cycle_start
                print(f"\n🎉 사이클 {cycle_count}/3 완료!")
                print(f"   사이클 소요 시간: {cycle_time:.1f}초")
                
                if cycle_count < 3:
                    print(f"   다음 사이클 시작까지 3초 대기...")
                    await asyncio.sleep(3)  # 3초 대기 후 다음 사이클
                else:
                    print(f"   🏁 테스트 완료!")
                
        except KeyboardInterrupt:
            print(f"\n⏹️ 사용자에 의해 중단됨 (사이클 {cycle_count} 완료)")
        
        total_elapsed = time.time() - total_start_time
        print(f"\n📊 테스트 결과 요약:")
        print(f"   완료된 사이클: {cycle_count}개")
        print(f"   총 소요 시간: {total_elapsed:.1f}초")
        print(f"   평균 사이클당 시간: {total_elapsed / cycle_count:.1f}초")
        print(f"   처리된 종목 수: {len(monitor.markets)}개")
        
    except Exception as e:
        print(f"❌ 연속 모니터링 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()


async def test_batch_timing():
    """배치 타이밍 정확성 테스트"""
    print("\n⏱️ 배치 타이밍 정확성 테스트!")
    print("="*60)
    
    try:
        # API 초기화
        api = BithumbAPI()
        monitor = BatchVolumeMonitor(api)
        
        # 초기화
        success = await monitor.initialize()
        if not success:
            print("❌ 초기화 실패")
            return
        
        print(f"✅ {len(monitor.markets)}개 종목으로 타이밍 테스트 시작")
        
        # 배치 크기와 지연 시간
        batch_size = 10
        delay = 1.0
        
        print(f"\n📊 타이밍 측정:")
        print(f"   배치 크기: {batch_size}개")
        print(f"   지연 시간: {delay}초")
        print(f"   예상 총 시간: {len(monitor.markets) // batch_size * delay:.1f}초")
        
        # 실제 타이밍 측정
        start_time = time.time()
        batch_times = []
        
        for i in range(0, len(monitor.markets), batch_size):
            batch_start = time.time()
            batch = monitor.markets[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            print(f"\n📦 배치 {batch_num}: {len(batch)}개 종목")
            start_time_str = time.strftime('%H:%M:%S')
            print(f"   시작: {start_time_str}")
            
            # 실제 배치 처리 및 매수 조건 체크
            for market in batch:
                try:
                    await monitor.check_market_conditions(market)
                except Exception as e:
                    pass  # 오류 무시하고 계속 진행
            
            batch_end = time.time()
            batch_time = batch_end - batch_start
            batch_times.append(batch_time)
            
            end_time_str = time.strftime('%H:%M:%S')
            print(f"   완료: {end_time_str}")
            print(f"   처리 시간: {batch_time:.3f}초")
            
            # 다음 배치까지 대기 (마지막 배치가 아닌 경우)
            if i + batch_size < len(monitor.markets):
                wait_start = time.time()
                await asyncio.sleep(delay)
                wait_end = time.time()
                actual_wait = wait_end - wait_start
                print(f"   대기 시간: {actual_wait:.3f}초")
        
        total_time = time.time() - start_time
        
        print(f"\n📈 타이밍 분석 결과:")
        print(f"   총 소요 시간: {total_time:.2f}초")
        print(f"   평균 배치 처리 시간: {sum(batch_times) / len(batch_times):.3f}초")
        print(f"   최소 배치 처리 시간: {min(batch_times):.3f}초")
        print(f"   최대 배치 처리 시간: {max(batch_times):.3f}초")
        print(f"   배치 간 평균 간격: {delay:.1f}초")
        
        # 효율성 계산
        total_processing_time = sum(batch_times)
        total_waiting_time = total_time - total_processing_time
        efficiency = (total_processing_time / total_time) * 100
        
        print(f"\n⚡ 효율성 분석:")
        print(f"   실제 처리 시간: {total_processing_time:.2f}초 ({efficiency:.1f}%)")
        print(f"   대기 시간: {total_waiting_time:.2f}초 ({100-efficiency:.1f}%)")
        
        if efficiency > 80:
            print("   🎯 효율성: 우수")
        elif efficiency > 60:
            print("   ✅ 효율성: 양호")
        else:
            print("   ⚠️ 효율성: 개선 필요")
        
    except Exception as e:
        print(f"❌ 타이밍 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """실전 배치 모니터링 실행"""
    print("🚀 실전 배치 모니터링 시작!")
    print("="*60)
    
    # 1. 단일 종목 체크 (BTC)
    await test_single_market()
    
    # 2. 실전 전체 종목 모니터링
    await test_batch_monitor()
    
    print("\n🎉 실전 모니터링 완료!")
    print("💡 매수 조건을 만족하는 종목이 발견되면 위에 표시됩니다.")


if __name__ == "__main__":
    asyncio.run(main())
