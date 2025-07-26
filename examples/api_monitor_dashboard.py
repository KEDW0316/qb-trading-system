import asyncio
import sys
import os
from datetime import datetime, timedelta

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qb.utils.api_monitor import APIMonitor

async def show_dashboard():
    monitor = APIMonitor()
    
    # 일일 통계 출력
    daily_stats = monitor.get_daily_stats()
    print("\n===== 일일 API 통계 =====")
    print(f"총 요청 수: {daily_stats['total_requests']}")
    print(f"성공 요청 수: {daily_stats['successful_requests']}")
    print(f"실패 요청 수: {daily_stats['failed_requests']}")
    print(f"평균 응답 시간: {daily_stats['avg_response_time']:.4f}초")
    
    # 엔드포인트 통계 출력
    endpoint_stats = monitor.get_endpoint_stats()
    print("\n===== 엔드포인트별 통계 =====")
    for endpoint, stats in endpoint_stats.items():
        print(f"\n엔드포인트: {endpoint}")
        print(f"  총 요청 수: {stats['total_requests']}")
        print(f"  성공률: {stats['successful_requests'] / stats['total_requests'] * 100:.1f}%")
        print(f"  평균 응답 시간: {stats['avg_response_time']:.4f}초")
        print(f"  마지막 사용: {stats['last_used']}")
    
    # 오류 통계 출력
    error_stats = monitor.get_error_stats()
    if error_stats:
        print("\n===== 오류 통계 =====")
        for error, count in sorted(error_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"{error}: {count}회")
    
    # 최근 로그 출력
    recent_logs = monitor.get_recent_logs(10)
    print("\n===== 최근 API 요청 로그 =====")
    for log in recent_logs:
        status = "성공" if log["success"] else "실패"
        print(f"{log['timestamp']} - {log['method']} {log['endpoint']} - {status} ({log['response_time']:.4f}초)")
    
    # 최근 오류 로그 출력
    error_logs = monitor.get_error_logs(5)
    if error_logs:
        print("\n===== 최근 오류 로그 =====")
        for log in error_logs:
            print(f"{log[1]} - {log[2]} {log[3]} - {log[7]}")

if __name__ == "__main__":
    asyncio.run(show_dashboard())