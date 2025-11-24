# utils/retries.py
import asyncio
from typing import Callable, Any

async def retry_async(fn: Callable[..., Any], retries: int = 3, delay: float = 1.0, *args, **kwargs):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt == retries:
                raise
            await asyncio.sleep(delay * attempt)
    raise last_exc
