"""Centralized LLM Gateway - Single point for all LLM activity monitoring."""

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, cast

from artifactforge.agents.llm_client import (
    Provider,
    call_llm as _call_llm,
    get_provider,
)
from artifactforge.observability.middleware import emit_status, get_trace_id

logger = logging.getLogger(__name__)

OLLAMA_MODEL = "kimi-k2.5:cloud"

AGENT_TEMPERATURES = {
    "intent_architect": 0.1,
    "research_lead": 0.2,
    "evidence_ledger": 0.0,
    "analyst": 0.3,
    "output_strategist": 0.3,
    "draft_writer": 0.4,
    "adversarial_reviewer": 0.2,
    "verifier": 0.0,
    "polisher": 0.4,
    "final_arbiter": 0.1,
    "visual_designer": 0.3,
    "visual_reviewer": 0.1,
    "visual_generator": 0.1,
}


def get_agent_temperature(agent_name: str) -> float:
    """Get temperature setting for an agent."""
    return AGENT_TEMPERATURES.get(agent_name, 0.7)


@dataclass
class LLMRequest:
    """Incoming LLM request."""

    request_id: str
    timestamp: datetime
    provider: str
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: int
    agent_name: Optional[str] = None


@dataclass
class LLMResponse:
    """LLM response with metadata."""

    request_id: str
    timestamp: datetime
    duration_ms: float
    success: bool
    error: Optional[str] = None
    output_tokens: Optional[int] = None
    input_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    raw_response: Optional[str] = None


@dataclass
class LLMCall:
    """Complete LLM call record."""

    request: LLMRequest
    response: LLMResponse

    def to_dict(self) -> dict:
        return {
            "request_id": self.request.request_id,
            "timestamp": self.request.timestamp.isoformat(),
            "agent": self.request.agent_name,
            "provider": self.request.provider,
            "model": self.request.model,
            "duration_ms": self.response.duration_ms,
            "success": self.response.success,
            "error": self.response.error,
            "input_tokens": self.response.input_tokens,
            "output_tokens": self.response.output_tokens,
            "cost_usd": self.response.cost_usd,
        }


CALL_HISTORY: list[LLMCall] = []
CALLbacks: list[Callable[[LLMCall], None]] = []


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def register_callback(callback: Callable[[LLMCall], None]) -> None:
    CALLbacks.append(callback)


def get_call_history(limit: int = 100) -> list[dict]:
    return [call.to_dict() for call in CALL_HISTORY[-limit:]]


def get_stats() -> dict:
    if not CALL_HISTORY:
        return {
            "total_calls": 0,
            "total_cost_usd": 0.0,
            "total_duration_ms": 0,
            "success_rate": 0.0,
        }

    total = len(CALL_HISTORY)
    successful = sum(1 for c in CALL_HISTORY if c.response.success)
    total_duration = sum(c.response.duration_ms for c in CALL_HISTORY)

    return {
        "total_calls": total,
        "successful_calls": successful,
        "failed_calls": total - successful,
        "success_rate": successful / total if total else 0,
        "total_cost_usd": 0.0,
        "total_duration_ms": round(total_duration, 2),
        "avg_duration_ms": round(total_duration / total, 2) if total else 0,
    }


def clear_history() -> None:
    CALL_HISTORY.clear()


async def call_llm_async(
    system_prompt: str,
    user_prompt: str,
    agent_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
) -> str:
    if provider is None:
        provider = get_provider()
    if model is None:
        model = OLLAMA_MODEL

    provider = cast(Provider, provider)

    if temperature == 0.7 and agent_name:
        temperature = get_agent_temperature(agent_name)

    request_id = str(uuid.uuid4())[:8]
    timestamp = datetime.utcnow()

    start_time = time.perf_counter()
    success = False
    error = None
    output = None
    input_tokens = estimate_tokens(system_prompt + user_prompt)
    output_tokens = 0

    emit_status(
        f"Calling LLM model={model} max_tokens={max_tokens}",
        trace_id=get_trace_id(),
        node_name=agent_name,
        metadata={
            "kind": "llm_call",
            "model": model,
            "max_tokens": max_tokens,
        },
    )

    try:
        output = await _call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        success = True
        output_tokens = estimate_tokens(output)
        emit_status(
            f"LLM response generated {output_tokens} tokens",
            trace_id=get_trace_id(),
            node_name=agent_name,
            metadata={
                "kind": "llm_response",
                "model": model,
                "output_tokens": output_tokens,
            },
        )
    except Exception as e:
        error = str(e)
        logger.warning(f"LLM request {request_id} failed: {e}")
        raise RuntimeError(f"LLM request failed: {error}") from e

    duration_ms = (time.perf_counter() - start_time) * 1000

    request = LLMRequest(
        request_id=request_id,
        timestamp=timestamp,
        provider=provider,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        agent_name=agent_name,
    )

    response = LLMResponse(
        request_id=request_id,
        timestamp=timestamp,
        duration_ms=duration_ms,
        success=success,
        error=error,
        output_tokens=output_tokens,
        input_tokens=input_tokens,
        cost_usd=0.0,
        raw_response=output[:200] if output else None,
    )

    call = LLMCall(request=request, response=response)
    CALL_HISTORY.append(call)

    for callback in CALLbacks:
        try:
            callback(call)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    return output


def _run_in_thread(coro) -> str:
    """Run an async coroutine in a separate thread to avoid nested event loops."""
    import concurrent.futures
    import threading

    result: str = ""
    exception: BaseException | None = None

    def _target():
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
    return result


def call_llm(
    system_prompt: str,
    user_prompt: str,
    agent_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
) -> str:
    try:
        asyncio.get_running_loop()
        return _run_in_thread(
            call_llm_async(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                agent_name=agent_name,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
    except RuntimeError:
        return asyncio.run(
            call_llm_async(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                agent_name=agent_name,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )


def call_llm_sync(
    system_prompt: str,
    user_prompt: str,
    agent_name: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
) -> str:
    try:
        asyncio.get_running_loop()
        return _run_in_thread(
            call_llm_async(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                agent_name=agent_name,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
    except RuntimeError:
        return asyncio.run(
            call_llm_async(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                agent_name=agent_name,
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )


def extract_json(text: str) -> str:
    """Strip markdown code fences from LLM output to extract raw JSON.

    Many LLMs wrap JSON in ```json ... ``` blocks. This extracts the
    content so json.loads() can parse it.
    """
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


__all__ = [
    "call_llm",
    "call_llm_async",
    "call_llm_sync",
    "extract_json",
    "register_callback",
    "get_call_history",
    "get_stats",
    "clear_history",
    "LLMCall",
    "LLMRequest",
    "LLMResponse",
]
