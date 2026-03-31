"""Async compatibility utilities for running coroutines from sync code.

Handles the case where sync functions need to call async code but may
already be inside a running event loop (e.g., LangGraph ainvoke()).
"""

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


def run_async_safely(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine safely, whether or not an event loop is running.

    If no event loop is running: uses asyncio.run() directly.
    If an event loop IS running: spins up a new loop in a background thread.
    """
    try:
        asyncio.get_running_loop()
        return _run_in_thread(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _run_in_thread(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine in a separate thread with its own event loop."""
    result: T | None = None
    exception: BaseException | None = None

    def _target() -> None:
        nonlocal result, exception
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
        except Exception as e:
            exception = e
        finally:
            loop.close()

    thread = threading.Thread(target=_target)
    thread.start()
    thread.join()
    if exception:
        raise exception
    return result  # type: ignore[return-value]
