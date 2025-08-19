"""
Rate Limiter 테스트 (TDD)
실패하는 테스트를 먼저 작성하여 요구사항을 명확히 정의
"""

import pytest
import asyncio
import time
from unittest.mock import patch, Mock

# 아직 구현되지 않은 모듈 - 테스트가 실패해야 함!
from src.utils.rate_limiter import RateLimiter, ExponentialBackoff


class TestRateLimiter:
    """Rate Limiter 테스트 클래스"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        self.rate_limiter = RateLimiter(max_calls=3, time_window=1.0)

    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        """제한 내 호출 테스트"""
        # Given - 제한이 3건/초이고 아직 호출한 적 없음
        
        # When - 3번 연속 호출
        start_time = time.time()
        await self.rate_limiter.acquire()
        await self.rate_limiter.acquire()  
        await self.rate_limiter.acquire()
        end_time = time.time()
        
        # Then - 즉시 통과해야 함 (대기시간 거의 없음)
        elapsed = end_time - start_time
        assert elapsed < 0.1  # 0.1초 미만

    @pytest.mark.asyncio
    async def test_acquire_exceeds_limit_waits(self):
        """제한 초과시 대기 테스트"""
        # Given - 이미 3번 호출 완료
        await self.rate_limiter.acquire()
        await self.rate_limiter.acquire()
        await self.rate_limiter.acquire()
        
        # When - 4번째 호출 (제한 초과)
        start_time = time.time()
        await self.rate_limiter.acquire()  # 이때 대기해야 함
        end_time = time.time()
        
        # Then - 약 1초 대기했어야 함
        elapsed = end_time - start_time
        assert 0.8 < elapsed < 1.2  # 1초 전후 허용오차

    def test_get_remaining_calls_initial(self):
        """초기 남은 호출 횟수 테스트"""
        # Given - 아직 호출한 적 없음
        
        # When
        remaining = self.rate_limiter.get_remaining_calls()
        
        # Then
        assert remaining == 3

    @pytest.mark.asyncio
    async def test_get_remaining_calls_after_usage(self):
        """사용 후 남은 호출 횟수 테스트"""
        # Given - 2번 호출
        await self.rate_limiter.acquire()
        await self.rate_limiter.acquire()
        
        # When
        remaining = self.rate_limiter.get_remaining_calls()
        
        # Then
        assert remaining == 1

    def test_get_reset_time_initial(self):
        """초기 리셋 시간 테스트"""
        # Given - 아직 호출한 적 없음
        
        # When
        reset_time = self.rate_limiter.get_reset_time()
        
        # Then - 리셋할 필요 없음
        assert reset_time == 0

    @pytest.mark.asyncio 
    async def test_get_reset_time_after_usage(self):
        """사용 후 리셋 시간 테스트"""
        # Given - 1번 호출
        await self.rate_limiter.acquire()
        
        # When
        reset_time = self.rate_limiter.get_reset_time()
        
        # Then - 약 1초 후 리셋
        assert 0.8 < reset_time < 1.2

    @pytest.mark.asyncio
    async def test_cleanup_old_calls(self):
        """오래된 호출 기록 정리 테스트"""
        # Given - 3번 호출 후 1.5초 대기 (time window 초과)
        await self.rate_limiter.acquire()
        await self.rate_limiter.acquire()
        await self.rate_limiter.acquire()
        
        await asyncio.sleep(1.5)  # time window(1초) 초과 대기
        
        # When - 새로운 호출 (정리 후 가능해야 함)
        start_time = time.time()
        await self.rate_limiter.acquire()
        end_time = time.time()
        
        # Then - 즉시 통과 (대기 없음)
        elapsed = end_time - start_time
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_priority_queue_higher_priority_first(self):
        """우선순위 큐 테스트 - 높은 우선순위 먼저"""
        # Given - 제한 도달 상태
        await self.rate_limiter.acquire()
        await self.rate_limiter.acquire()
        await self.rate_limiter.acquire()
        
        # When - 우선순위가 다른 요청들을 동시에 요청
        results = []
        
        async def low_priority_request():
            await self.rate_limiter.acquire(priority=10)  # 낮은 우선순위
            results.append("low")
            
        async def high_priority_request():
            await self.rate_limiter.acquire(priority=1)   # 높은 우선순위  
            results.append("high")
        
        # 동시 실행
        await asyncio.gather(
            low_priority_request(),
            high_priority_request()
        )
        
        # Then - 높은 우선순위가 먼저 처리되어야 함
        assert results[0] == "high"
        assert results[1] == "low"


class TestExponentialBackoff:
    """지수 백오프 테스트 클래스"""

    def setup_method(self):
        """각 테스트 전 초기화"""
        self.backoff = ExponentialBackoff(
            initial_delay=0.1,
            max_delay=10.0,
            multiplier=2.0
        )

    @pytest.mark.asyncio
    async def test_wait_first_attempt(self):
        """첫 번째 재시도 대기시간 테스트"""
        # Given - 첫 번째 재시도 (attempt=1)
        
        # When
        start_time = time.time()
        delay = await self.backoff.wait(attempt=1)
        end_time = time.time()
        
        # Then - initial_delay(0.1초) 대기
        elapsed = end_time - start_time
        assert 0.08 < elapsed < 0.12  # 0.1초 전후
        assert delay == 0.1

    @pytest.mark.asyncio
    async def test_wait_exponential_increase(self):
        """지수적 증가 테스트"""
        # When
        delay1 = await self.backoff.wait(attempt=1)  # 0.1초
        delay2 = await self.backoff.wait(attempt=2)  # 0.2초
        delay3 = await self.backoff.wait(attempt=3)  # 0.4초
        
        # Then - 지수적으로 증가
        assert delay1 == 0.1
        assert delay2 == 0.2
        assert delay3 == 0.4

    def test_calculate_delay_max_limit(self):
        """최대 지연시간 제한 테스트"""
        # Given - 매우 높은 재시도 횟수
        
        # When
        delay = self.backoff.calculate_delay(attempt=10)  # 매우 큰 값
        
        # Then - max_delay(10.0초)를 초과하면 안됨
        assert delay <= 10.0

    def test_reset(self):
        """백오프 상태 리셋 테스트"""
        # Given - 몇 번 재시도 후
        self.backoff.calculate_delay(attempt=3)
        
        # When
        self.backoff.reset()
        
        # Then - 초기 상태로 복원 (구현에 따라 달라질 수 있음)
        # 이 부분은 실제 구현에서 reset이 어떻게 작동하는지에 따라 달라짐
        delay = self.backoff.calculate_delay(attempt=1)
        assert delay == 0.1


class TestRateLimiterIntegration:
    """Rate Limiter 통합 테스트"""

    @pytest.mark.asyncio
    async def test_rate_limiter_with_backoff_on_failure(self):
        """Rate Limiter + Exponential Backoff 통합 테스트"""
        # Given
        rate_limiter = RateLimiter(max_calls=2, time_window=1.0)
        backoff = ExponentialBackoff(initial_delay=0.1, multiplier=2.0)
        
        # When - 제한 초과 상황에서 백오프 적용
        await rate_limiter.acquire()
        await rate_limiter.acquire()  # 제한 도달
        
        # 제한 초과시 백오프 적용
        start_time = time.time()
        
        # 첫 번째 재시도 - 0.1초 대기
        await backoff.wait(attempt=1)
        await rate_limiter.acquire()  # 여전히 제한 상태라면 대기
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Then - 백오프 시간 + rate limit 대기시간
        assert elapsed > 0.1  # 최소 백오프 시간은 대기