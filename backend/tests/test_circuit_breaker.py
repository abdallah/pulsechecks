"""Tests for circuit breaker functionality."""
import pytest
import asyncio
from unittest.mock import AsyncMock
from app.utils.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState, with_circuit_breaker


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state allows calls."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        async def success_func():
            return "success"
        
        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        breaker = CircuitBreaker(failure_threshold=2)
        
        async def failing_func():
            raise ValueError("Test error")
        
        # First failure
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        assert breaker.state == CircuitState.CLOSED
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_breaker_fails_fast_when_open(self):
        """Test circuit breaker fails fast when open."""
        breaker = CircuitBreaker(failure_threshold=1)
        
        async def failing_func():
            raise ValueError("Test error")
        
        # Trigger failure to open circuit
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        assert breaker.state == CircuitState.OPEN
        
        # Should fail fast now
        with pytest.raises(CircuitBreakerError):
            await breaker.call(failing_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery through half-open state."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        async def failing_func():
            raise ValueError("Test error")
        
        async def success_func():
            return "recovered"
        
        # Open the circuit
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Should transition to half-open and then closed on success
        result = await breaker.call(success_func)
        assert result == "recovered"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_decorator(self):
        """Test circuit breaker decorator."""
        call_count = 0
        
        @with_circuit_breaker(failure_threshold=2)
        async def test_func(should_fail=False):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise ValueError("Test error")
            return f"call_{call_count}"
        
        # Successful calls
        result1 = await test_func()
        assert result1 == "call_1"
        
        result2 = await test_func()
        assert result2 == "call_2"
        
        # Failures to open circuit
        with pytest.raises(ValueError):
            await test_func(should_fail=True)
        
        with pytest.raises(ValueError):
            await test_func(should_fail=True)
        
        # Should fail fast now
        with pytest.raises(CircuitBreakerError):
            await test_func()
        
        # Call count should not increase for circuit breaker errors
        assert call_count == 4
