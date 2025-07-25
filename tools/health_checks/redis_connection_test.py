#!/usr/bin/env python3
"""
Redis 연결 및 상태 확인 도구
QB Trading System용 헬스체크 유틸리티

사용법:
    python tools/health_checks/redis_connection_test.py
    python tools/health_checks/redis_connection_test.py --host localhost --port 6379
    python tools/health_checks/redis_connection_test.py --detailed
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'qb'))

from utils.redis_manager import RedisManager

def setup_logging(verbose=False):
    """로깅 설정"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def test_redis_connection(host='localhost', port=6379, db=0, detailed=False, verbose=False):
    """Redis 연결 및 기본 기능 테스트"""
    
    setup_logging(verbose)
    
    print("=" * 60)
    print(f"🔍 Redis 헬스체크 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 서버: {host}:{port} (DB: {db})")
    print("=" * 60)
    
    success_count = 0
    total_tests = 7 if detailed else 4
    
    try:
        # RedisManager 인스턴스 생성
        redis_manager = RedisManager(host=host, port=port, db=db)
        
        # 1. 연결 확인
        print("\n🔌 1. Redis 연결 확인:")
        if redis_manager.ping():
            print("   ✅ Redis 연결 성공!")
            success_count += 1
        else:
            print("   ❌ Redis 연결 실패!")
            return False, success_count, total_tests
            
        # 2. 서버 정보 조회
        print("\n📊 2. Redis 서버 정보:")
        info = redis_manager.get_info()
        if info:
            print(f"   ✅ Redis 버전: {info.get('redis_version', 'Unknown')}")
            print(f"   ✅ 가동 시간: {info.get('uptime_in_days', 0)} 일")
            print(f"   ✅ 연결된 클라이언트: {info.get('connected_clients', 0)}")
            success_count += 1
        else:
            print("   ❌ 서버 정보 조회 실패!")
            
        # 3. 메모리 사용량 조회
        print("\n💾 3. Redis 메모리 사용량:")
        memory_stats = redis_manager.get_memory_stats()
        if memory_stats:
            print(f"   ✅ 사용 중인 메모리: {memory_stats.get('used_memory_human', 'Unknown')}")
            print(f"   ✅ 최대 메모리: {memory_stats.get('maxmemory_human', 'Unlimited')}")
            print(f"   ✅ 메모리 정책: {memory_stats.get('maxmemory_policy', 'noeviction')}")
            success_count += 1
        else:
            print("   ❌ 메모리 정보 조회 실패!")
            
        # 4. 기본 데이터 저장/조회 테스트
        print("\n📝 4. 기본 데이터 작업 테스트:")
        test_key = f"healthcheck:test:{int(datetime.now().timestamp())}"
        test_value = "QB Trading System Health Check"
        
        try:
            # 데이터 저장
            redis_manager.redis.set(test_key, test_value)
            print(f"   ✅ 데이터 저장: {test_key}")
            
            # 데이터 조회
            retrieved_value = redis_manager.redis.get(test_key)
            if retrieved_value == test_value:
                print(f"   ✅ 데이터 조회 성공")
                success_count += 1
            else:
                print(f"   ❌ 데이터 조회 실패! 예상: {test_value}, 실제: {retrieved_value}")
                
            # TTL 테스트
            redis_manager.redis.expire(test_key, 10)
            ttl = redis_manager.redis.ttl(test_key)
            if ttl > 0:
                print(f"   ✅ TTL 설정 성공: {ttl}초")
            
            # 데이터 삭제
            redis_manager.redis.delete(test_key)
            print("   ✅ 테스트 데이터 정리 완료")
            
        except Exception as e:
            print(f"   ❌ 데이터 작업 중 오류: {e}")
        
        # 상세 테스트 (옵션)
        if detailed:
            print("\n🔬 5. 상세 테스트:")
            
            # 5. Pub/Sub 테스트
            try:
                test_channel = "healthcheck:pubsub"
                test_message = "test message"
                
                # 메시지 발행
                subscribers = redis_manager.redis.publish(test_channel, test_message)
                print(f"   ✅ Pub/Sub 발행 성공 (구독자: {subscribers}명)")
                success_count += 1
            except Exception as e:
                print(f"   ❌ Pub/Sub 테스트 실패: {e}")
            
            # 6. 키 공간 통계
            try:
                keyspace_info = {k: v for k, v in info.items() if k.startswith('db')}
                if keyspace_info:
                    print(f"   ✅ 키 공간 정보: {keyspace_info}")
                else:
                    print(f"   ✅ 키 공간: 비어있음")
                success_count += 1
            except Exception as e:
                print(f"   ❌ 키 공간 조회 실패: {e}")
            
            # 7. 성능 간단 측정
            try:
                import time
                start_time = time.time()
                for i in range(100):
                    redis_manager.redis.set(f"perf:test:{i}", f"value{i}")
                for i in range(100):
                    redis_manager.redis.get(f"perf:test:{i}")
                for i in range(100):
                    redis_manager.redis.delete(f"perf:test:{i}")
                end_time = time.time()
                
                ops_per_sec = 300 / (end_time - start_time)
                print(f"   ✅ 성능 테스트: {ops_per_sec:.0f} ops/sec (300 작업)")
                success_count += 1
            except Exception as e:
                print(f"   ❌ 성능 테스트 실패: {e}")
        
        print("\n" + "=" * 60)
        print(f"🎯 테스트 결과: {success_count}/{total_tests} 성공")
        
        if success_count == total_tests:
            print("🎉 모든 테스트 통과! Redis가 정상 작동 중입니다.")
            print("=" * 60)
            return True, success_count, total_tests
        else:
            print("⚠️  일부 테스트 실패. Redis 상태를 확인해주세요.")
            print("=" * 60)
            return False, success_count, total_tests
        
    except Exception as e:
        print(f"\n💥 치명적 오류 발생: {e}")
        print("=" * 60)
        return False, success_count, total_tests

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='Redis 연결 및 상태 확인 도구')
    parser.add_argument('--host', default='localhost', help='Redis 서버 호스트 (기본값: localhost)')
    parser.add_argument('--port', type=int, default=6379, help='Redis 서버 포트 (기본값: 6379)')
    parser.add_argument('--db', type=int, default=0, help='Redis 데이터베이스 번호 (기본값: 0)')
    parser.add_argument('--detailed', action='store_true', help='상세 테스트 실행')
    parser.add_argument('--verbose', '-v', action='store_true', help='상세한 로그 출력')
    
    args = parser.parse_args()
    
    success, passed, total = test_redis_connection(
        host=args.host,
        port=args.port, 
        db=args.db,
        detailed=args.detailed,
        verbose=args.verbose
    )
    
    # 종료 코드 설정 (성공: 0, 실패: 1)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 