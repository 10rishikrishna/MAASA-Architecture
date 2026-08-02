# backend/fault_tolerance.py
"""
Fault Tolerance Module for Mosaic Studio
Implements Circuit Breaker, Retry with Backoff, and Bulkhead patterns.
"""
import time
import asyncio
import logging
from functools import wraps
from typing import Callable, Any, Optional
from enum import Enum

logger = logging.getLogger("mosaic_studio.fault_tolerance")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit Breaker pattern to prevent cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED

    def _can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 3:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info("Circuit breaker CLOSED - service recovered")
        else:
            self.failure_count = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker OPENED after {self.failure_count} failures. "
                f"Recovery in {self.recovery_timeout}s"
            )

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not self._can_execute():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. Service unavailable for {self.recovery_timeout}s"
                )
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except self.expected_exception as e:
                self.record_failure()
                raise
        return wrapper


class CircuitBreakerOpenError(Exception):
    pass


class RetryWithBackoff:
    """Exponential backoff retry pattern."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,),
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(self.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except self.retryable_exceptions as e:
                    last_exception = e
                    if attempt < self.max_retries:
                        delay = min(
                            self.base_delay * (self.exponential_base ** attempt),
                            self.max_delay,
                        )
                        if self.jitter:
                            import random
                            delay *= (0.5 + random.random())

                        logger.warning(
                            f"Retry {attempt + 1}/{self.max_retries} for {func.__name__} "
                            f"after {delay:.2f}s delay. Error: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {self.max_retries} retries exhausted for {func.__name__}"
                        )
            raise last_exception
        return wrapper


class Bulkhead:
    """Bulkhead pattern to limit concurrent executions per service."""

    def __init__(self, max_concurrent: int = 10, max_wait_time: float = 30.0):
        self.max_concurrent = max_concurrent
        self.max_wait_time = max_wait_time
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0

    async def acquire(self):
        acquired = await asyncio.wait_for(
            self.semaphore.acquire(),
            timeout=self.max_wait_time,
        )
        self.active_count += 1
        return acquired

    def release(self):
        self.semaphore.release()
        self.active_count -= 1

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await self.acquire()
            try:
                return await func(*args, **kwargs)
            finally:
                self.release()
        return wrapper


# ── Pre-configured Instances ────────────────────────────────────────────────

# Circuit breaker for LLM API calls
llm_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60,
    expected_exception=Exception,
)

# Circuit breaker for database operations
db_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30,
    expected_exception=Exception,
)

# Retry decorator for external API calls
external_api_retry = RetryWithBackoff(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError, OSError),
)

# Bulkhead for concurrent analysis processing
analysis_bulkhead = Bulkhead(max_concurrent=5, max_wait_time=60.0)

# Bulkhead for chat processing
chat_bulkhead = Bulkhead(max_concurrent=20, max_wait_time=10.0)


# ── Health Check with Circuit Breaker ────────────────────────────────────────

class ServiceHealthChecker:
    """Checks health of dependent services with circuit breaker protection."""

    def __init__(self):
        self.checks = {}

    def register(self, name: str, check_fn: Callable):
        self.checks[name] = check_fn

    async def check_all(self) -> dict:
        results = {}
        for name, check_fn in self.checks.items():
            try:
                await check_fn()
                results[name] = "healthy"
            except CircuitBreakerOpenError:
                results[name] = "circuit_open"
            except Exception as e:
                results[name] = f"unhealthy: {e}"
        return results


health_checker = ServiceHealthChecker()
