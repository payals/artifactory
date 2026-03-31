import asyncio

import pytest

from artifactforge.tools.research.async_compat import run_async_safely


async def _double(x: int) -> int:
    return x * 2


async def _explode() -> None:
    raise ValueError("boom")


def test_run_async_safely_no_loop() -> None:
    result = run_async_safely(_double(5))
    assert result == 10


@pytest.mark.asyncio
async def test_run_async_safely_inside_running_loop() -> None:
    result = run_async_safely(_double(7))
    assert result == 14


def test_run_async_safely_propagates_exceptions() -> None:
    with pytest.raises(ValueError, match="boom"):
        run_async_safely(_explode())


@pytest.mark.asyncio
async def test_run_async_safely_propagates_exceptions_in_loop() -> None:
    with pytest.raises(ValueError, match="boom"):
        run_async_safely(_explode())
