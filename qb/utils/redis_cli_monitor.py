#!/usr/bin/env python3
"""
Redis CLI Monitor - Redis 서버 상태를 실시간으로 모니터링하는 CLI 도구

사용법:
    python -m qb.utils.redis_cli_monitor [options]
    
옵션:
    --host HOST         Redis 서버 호스트 (기본값: localhost)
    --port PORT         Redis 서버 포트 (기본값: 6379)
    --interval SECONDS  새로고침 간격 (기본값: 5초)
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime
from typing import Dict, Any

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from qb.utils.redis_manager import RedisManager
from qb.utils.redis_monitor import RedisMonitor


class RedisCliMonitor:
    """Redis CLI 모니터링 도구"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379):
        self.host = host
        self.port = port
        self.redis = RedisManager(host=host, port=port)
        self.monitor = RedisMonitor(self.redis)
        
    def clear_screen(self):
        """화면 지우기 (크로스 플랫폼)"""
        if sys.platform.startswith('win'):
            os.system('cls')
        else:
            print("\033[H\033[J", end="")
    
    def format_bytes(self, bytes_value: int) -> str:
        """바이트를 읽기 쉬운 형식으로 변환"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f}{unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f}TB"
    
    def draw_progress_bar(self, percent: float, width: int = 30) -> str:
        """진행률 바 그리기"""
        filled = int(width * percent / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}] {percent:.1f}%"
    
    def display_header(self):
        """헤더 표시"""
        print(f"Redis Monitor - {self.host}:{self.port} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
    
    def display_basic_info(self, stats: Dict[str, Any]):
        """기본 정보 표시"""
        print(f"Redis Version: {stats.get('redis_version', 'Unknown')}")
        print(f"Uptime: {stats.get('uptime_days', 0)} days")
        print(f"Connected Clients: {stats.get('clients_connected', 0)}")
        print(f"Total Commands: {stats.get('total_commands', 0):,}")
        print("-" * 80)
    
    def display_memory_info(self, stats: Dict[str, Any]):
        """메모리 정보 표시"""
        used_memory = stats.get('used_memory', 0)
        max_memory = stats.get('max_memory', 0)
        memory_percent = stats.get('memory_usage_percent', 0)
        
        print("Memory Usage:")
        print(f"  Used: {stats.get('used_memory_human', '0B')} / "
              f"Max: {stats.get('max_memory_human', 'unlimited')}")
        
        # 메모리 사용률에 따른 색상 코드
        if memory_percent > 90:
            color = '\033[91m'  # 빨간색
        elif memory_percent > 75:
            color = '\033[93m'  # 노란색
        else:
            color = '\033[92m'  # 초록색
        
        print(f"  {color}{self.draw_progress_bar(memory_percent)}\033[0m")
        print("-" * 80)
    
    def display_performance_info(self, stats: Dict[str, Any]):
        """성능 정보 표시"""
        hit_rate = stats.get('hit_rate', 0)
        
        print("Performance:")
        print(f"  Hit Rate: {hit_rate:.1f}%")
        print(f"  Keyspace Hits: {stats.get('keyspace_hits', 0):,}")
        print(f"  Keyspace Misses: {stats.get('keyspace_misses', 0):,}")
        print(f"  Evicted Keys: {stats.get('evicted_keys', 0):,}")
        print(f"  Expired Keys: {stats.get('expired_keys', 0):,}")
        print("-" * 80)
    
    def display_key_distribution(self):
        """키 분포 표시"""
        try:
            key_dist = self.monitor.get_key_distribution()
            mem_dist = self.monitor.get_key_memory_distribution()
            
            print("Key Distribution:")
            print(f"  {'Pattern':<20} {'Count':<10} {'Memory':<15}")
            print(f"  {'-'*20} {'-'*10} {'-'*15}")
            
            for pattern, count in key_dist.items():
                memory = mem_dist.get(pattern, 0)
                memory_str = self.format_bytes(memory)
                print(f"  {pattern:<20} {count:<10} {memory_str:<15}")
                
            total_keys = sum(key_dist.values())
            total_memory = sum(mem_dist.values())
            print(f"  {'-'*20} {'-'*10} {'-'*15}")
            print(f"  {'TOTAL':<20} {total_keys:<10} {self.format_bytes(total_memory):<15}")
            
        except Exception as e:
            print(f"  Error collecting key distribution: {e}")
        
        print("-" * 80)
    
    def display_db_info(self, stats: Dict[str, Any]):
        """데이터베이스별 정보 표시"""
        db_keys = stats.get('db_keys', {})
        if db_keys:
            print("Database Keys:")
            for db_num, key_count in sorted(db_keys.items()):
                print(f"  DB{db_num}: {key_count} keys")
            print("-" * 80)
    
    async def run(self, interval: int = 5):
        """모니터링 실행"""
        print("Starting Redis Monitor... Press Ctrl+C to exit.")
        await asyncio.sleep(1)
        
        try:
            while True:
                stats = self.monitor.collect_stats()
                
                if not stats.get('is_connected', False):
                    self.clear_screen()
                    print(f"\033[91mConnection Error: {stats.get('error', 'Cannot connect to Redis server')}\033[0m")
                    print(f"\nRetrying in {interval} seconds...")
                    await asyncio.sleep(interval)
                    continue
                
                # 화면 지우고 통계 표시
                self.clear_screen()
                self.display_header()
                self.display_basic_info(stats)
                self.display_memory_info(stats)
                self.display_performance_info(stats)
                self.display_key_distribution()
                self.display_db_info(stats)
                
                # 상태 요약
                summary = self.monitor.get_status_summary()
                status = summary['status']
                
                if status == 'critical':
                    status_color = '\033[91m'  # 빨간색
                elif status == 'warning':
                    status_color = '\033[93m'  # 노란색
                else:
                    status_color = '\033[92m'  # 초록색
                
                print(f"Status: {status_color}{status.upper()}\033[0m")
                print(f"\nRefreshing every {interval} seconds... Press Ctrl+C to exit.")
                
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            sys.exit(0)
        except Exception as e:
            print(f"\n\033[91mError: {e}\033[0m")
            sys.exit(1)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='Redis Monitoring CLI - Real-time Redis server monitoring'
    )
    parser.add_argument('--host', default='localhost', help='Redis host (default: localhost)')
    parser.add_argument('--port', type=int, default=6379, help='Redis port (default: 6379)')
    parser.add_argument('--interval', type=int, default=5, 
                       help='Refresh interval in seconds (default: 5)')
    
    args = parser.parse_args()
    
    # 모니터 인스턴스 생성 및 실행
    monitor = RedisCliMonitor(args.host, args.port)
    
    try:
        asyncio.run(monitor.run(args.interval))
    except Exception as e:
        print(f"\033[91mFailed to start monitor: {e}\033[0m")
        sys.exit(1)


if __name__ == '__main__':
    main()