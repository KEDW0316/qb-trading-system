import asyncio
import sys
import os
import time
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qb.collectors.kis_client import KISClient
from qb.utils.api_monitor import APIMonitor
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

async def test_api_monitor():
    """API 모니터링 시스템 테스트"""
    
    print("===== API 모니터링 시스템 테스트 시작 =====\n")
    
    # KIS 클라이언트 초기화 (실전투자 모드)
    client = KISClient(mode='prod')
    
    # 1. 몇 가지 API 호출 수행
    print("1. API 호출 테스트...")
    
    try:
        # 계좌 잔고 조회
        print("- 계좌 잔고 조회 중...")
        balance = await client.get_account_balance()
        print(f"  ✓ 계좌 잔고 조회 성공")
        
        # 삼성전자 현재가 조회
        print("- 삼성전자 현재가 조회 중...")
        price = await client.get_stock_price("005930")
        print(f"  ✓ 삼성전자 현재가: {price.get('output', {}).get('stck_prpr', 'N/A')}원")
        
        # 존재하지 않는 종목 조회 (오류 테스트)
        print("- 잘못된 종목코드로 조회 (오류 테스트)...")
        try:
            await client.get_stock_price("999999")
        except Exception as e:
            print(f"  ✓ 예상된 오류 발생: {str(e)[:50]}...")
        
        # 일봉 차트 조회
        print("- 삼성전자 일봉 차트 조회 중...")
        chart = await client.get_stock_daily_chart("005930", period=7)
        print(f"  ✓ 일봉 데이터 {len(chart.get('output2', []))}개 조회 성공")
        
    except Exception as e:
        print(f"  ✗ API 호출 중 오류 발생: {e}")
    
    print("\n2. API 모니터 통계 확인...")
    
    # API 모니터 직접 접근
    monitor = client.api_monitor
    
    # 통계 저장 (강제)
    monitor._save_stats()
    
    # 일일 통계 출력
    daily_stats = monitor.get_daily_stats()
    print(f"\n일일 통계:")
    print(f"  - 총 요청 수: {daily_stats['total_requests']}")
    print(f"  - 성공 요청 수: {daily_stats['successful_requests']}")
    print(f"  - 실패 요청 수: {daily_stats['failed_requests']}")
    print(f"  - 평균 응답 시간: {daily_stats['avg_response_time']:.4f}초")
    
    # 엔드포인트별 통계 출력
    endpoint_stats = monitor.get_endpoint_stats()
    print(f"\n엔드포인트별 통계:")
    for endpoint, stats in endpoint_stats.items():
        success_rate = (stats['successful_requests'] / stats['total_requests'] * 100) if stats['total_requests'] > 0 else 0
        print(f"  - {endpoint}")
        print(f"    • 요청 수: {stats['total_requests']}")
        print(f"    • 성공률: {success_rate:.1f}%")
        print(f"    • 평균 응답 시간: {stats['avg_response_time']:.4f}초")
    
    # 최근 로그 출력
    recent_logs = monitor.get_recent_logs(5)
    print(f"\n최근 API 요청 로그 ({len(recent_logs)}개):")
    for i, log in enumerate(recent_logs, 1):
        status = "성공" if log["success"] else "실패"
        print(f"  {i}. {log['method']} {log['endpoint']} - {status} ({log['response_time']:.4f}초)")
    
    # 오류 통계 출력
    error_stats = monitor.get_error_stats()
    if error_stats:
        print(f"\n오류 통계:")
        for error, count in error_stats.items():
            print(f"  - {error}: {count}회")
    
    print("\n3. DB 저장 및 조회 테스트...")
    
    # 잠시 대기 (DB 저장 완료 대기)
    await asyncio.sleep(1)
    
    # DB에서 로그 조회
    db_logs = monitor.get_logs_by_endpoint("/uapi/domestic-stock/v1/quotations/inquire-price", limit=3)
    print(f"\n특정 엔드포인트 로그 조회 (DB에서 {len(db_logs)}개):")
    for log in db_logs:
        print(f"  - {log[1]} - {log[2]} {log[3]} - 상태코드: {log[5]}")
    
    print("\n===== API 모니터링 시스템 테스트 완료 =====")

if __name__ == "__main__":
    asyncio.run(test_api_monitor())