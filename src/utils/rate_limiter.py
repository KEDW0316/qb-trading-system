"""
KIS API Rate Limit 관리 클래스
TDD로 구현 - 테스트를 통과하는 최소 구현
"""

import asyncio
import time
from collections import deque
from typing import Optional
import heapq


class RateLimiter:
    """KIS API Rate Limit 관리 클래스"""
    
    def __init__(self, 
                 max_calls: int = 18,      # 안전 마진 (KIS: 20건)
                 time_window: float = 1.0,  # 1초 윈도우
                 burst_limit: int = 5):     # 버스트 제한
        """Rate Limiter 초기화"""
        self.max_calls = max_calls
        self.time_window = time_window
        self.burst_limit = burst_limit
        
        # 호출 기록 (시간별)
        self.calls = deque()
        
        # 우선순위 큐 (priority, timestamp, future)
        self.priority_queue = []
        self.waiting_requests = 0
    
    async def acquire(self, priority: int = 0) -> None:
        """Rate Limit 체크 및 대기"""
        current_time = time.time()
        
        # 오래된 호출 기록 정리
        self._cleanup_old_calls()
        
        # 제한 내라면 즉시 통과
        if len(self.calls) < self.max_calls:
            self._record_call()
            return
        
        # 제한 초과 - 우선순위 큐에서 대기
        future = asyncio.Future()
        heapq.heappush(self.priority_queue, (priority, current_time, future))
        self.waiting_requests += 1
        
        # 대기 시간 계산
        wait_time = self._calculate_wait_time()
        
        # 대기 후 처리
        if wait_time > 0:
            await asyncio.sleep(wait_time)
            self._cleanup_old_calls()
        
        # 대기 완료 - 호출 기록
        self._record_call()
        self.waiting_requests -= 1
        future.set_result(None)
    
    async def wait_if_needed(self) -> float:
        """필요시 대기하고 대기 시간 반환"""
        wait_time = self._calculate_wait_time()
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        return wait_time
    
    def get_remaining_calls(self) -> int:
        """현재 윈도우에서 남은 호출 횟수"""
        self._cleanup_old_calls()
        return max(0, self.max_calls - len(self.calls))
    
    def get_reset_time(self) -> float:
        """다음 리셋까지 남은 시간 (초)"""
        if not self.calls:
            return 0
        
        current_time = time.time()
        oldest_call = self.calls[0]
        
        reset_time = oldest_call + self.time_window - current_time
        return max(0, reset_time)
    
    def _cleanup_old_calls(self) -> None:
        """시간 윈도우 밖의 호출 기록 정리"""
        current_time = time.time()
        cutoff_time = current_time - self.time_window
        
        while self.calls and self.calls[0] <= cutoff_time:
            self.calls.popleft()
    
    def _calculate_wait_time(self) -> float:
        """다음 호출까지 대기 시간 계산"""
        if len(self.calls) < self.max_calls:
            return 0
        
        # 가장 오래된 호출이 윈도우에서 나갈 때까지 대기
        current_time = time.time()
        oldest_call = self.calls[0]
        
        wait_time = oldest_call + self.time_window - current_time
        return max(0, wait_time)
    
    def _record_call(self) -> None:
        """호출 기록 추가"""
        self.calls.append(time.time())


class ExponentialBackoff:
    """지수 백오프 재시도 관리"""
    
    def __init__(self,
                 initial_delay: float = 0.1,
                 max_delay: float = 60.0,
                 multiplier: float = 2.0,
                 max_retries: int = 5):
        """백오프 설정 초기화"""
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.max_retries = max_retries
        
        # 상태 변수
        self.current_attempt = 0
    
    async def wait(self, attempt: int) -> float:
        """재시도 대기 (지수적 증가)"""
        delay = self.calculate_delay(attempt)
        await asyncio.sleep(delay)
        return delay
    
    def calculate_delay(self, attempt: int) -> float:
        """재시도 지연 시간 계산"""
        if attempt <= 0:
            return 0
        
        # 지수적 증가: initial_delay * (multiplier ^ (attempt - 1))
        delay = self.initial_delay * (self.multiplier ** (attempt - 1))
        
        # 최대 지연시간 제한
        return min(delay, self.max_delay)
    
    def reset(self) -> None:
        """백오프 상태 리셋"""
        self.current_attempt = 0


class PriorityQueue:
    """우선순위 큐 (중요한 API 호출 우선 처리)"""
    
    def __init__(self):
        """우선순위 큐 초기화"""
        self.queue = []
        self.counter = 0  # 같은 우선순위일 때 FIFO 보장
    
    async def put(self, item: any, priority: int = 0) -> None:
        """아이템 추가 (낮은 숫자 = 높은 우선순위)"""
        heapq.heappush(self.queue, (priority, self.counter, item))
        self.counter += 1
    
    async def get(self) -> any:
        """우선순위 순으로 아이템 조회"""
        if self.empty():
            raise asyncio.QueueEmpty()
        
        priority, counter, item = heapq.heappop(self.queue)
        return item
    
    def empty(self) -> bool:
        """큐가 비어있는지 확인"""
        return len(self.queue) == 0