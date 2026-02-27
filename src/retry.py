import time
import functools
from typing import Callable, Type, Tuple
import random
import logging

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    backoff_factor: float = 2.0,
    jitter: bool = True,
    logger: logging.Logger = None
):
    """
    Retry decorator with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to catch and retry on
        backoff_factor: Multiplier for delay after each failure
        jitter: Add random jitter to delay to prevent thundering herd
        logger: Optional logger for retry logging
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            attempt = 0

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    attempt += 1

                    if attempt == max_attempts:
                        break

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)

                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    # Log retry attempt
                    if logger:
                        logger.warning(
                            f"Retry attempt {attempt}/{max_attempts} for {func.__name__}",
                            extra={
                                "attempt": attempt,
                                "max_attempts": max_attempts,
                                "delay": delay,
                                "exception": str(e)
                            }
                        )
                    else:
                        print(f"Retry attempt {attempt}/{max_attempts} for {func.__name__} - "
                              f"Exception: {e} - Waiting {delay:.2f}s")

                    time.sleep(delay)

            # If we get here, all attempts failed
            if logger:
                logger.error(
                    f"All {max_attempts} attempts failed for {func.__name__}",
                    extra={"exception": str(last_exception)}
                )
            else:
                print(f"All {max_attempts} attempts failed for {func.__name__} - "
                      f"Last exception: {last_exception}")

            raise last_exception
        return wrapper
    return decorator


# Example usage:
# @retry(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
# def fetch_data():
#     # Your API call here
#     pass


class RetryManager:
    """Manager for retry configurations and statistics"""

    def __init__(self):
        self.retry_stats = {}

    def record_retry(self, func_name: str, attempt: int, max_attempts: int, delay: float):
        """Record retry statistics"""
        if func_name not in self.retry_stats:
            self.retry_stats[func_name] = {
                "attempts": 0,
                "max_attempts": max_attempts,
                "total_delay": 0.0,
                "success": False
            }

        self.retry_stats[func_name]["attempts"] += 1
        self.retry_stats[func_name]["total_delay"] += delay

    def get_stats(self) -> dict:
        """Get retry statistics"""
        return self.retry_stats

    def reset_stats(self):
        """Reset retry statistics"""
        self.retry_stats = {}


# Global retry manager instance
retry_manager = RetryManager()
