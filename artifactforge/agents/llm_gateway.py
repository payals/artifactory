"""Centralized LLM Gateway - Single point for all LLM activity monitoring."""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from artifactforge.agents.llm_client import (
    Provider,
    call_llm as _call_llm,
    call_llm_sync as _call_llm_sync,
    get_provider,
)

logger = logging.getLogger(__name__)


MODEL_REGISTRY = {
    "default": "z-ai/glm-4.5-air:free",
    "reasoning": "meta-llama/llama-3.2-3b-instruct:free",
    "deep_reasoning": "nvidia/nemotron-3-nano-30b-a3b:free",
    "coding": "qwen/qwen3-coder:free",
    "review": "google/gemma-3-4b-it:free",
    "verification": "google/gemma-3-4b-it:free",
    "cheap_worker": "google/gemma-3n-e2b-it:free",
    "fallback_1": "liquid/lfm-2.5-1.2b-instruct:free",
    "fallback_2": "z-ai/glm-4.5-air:free",
}

AGENT_TO_MODEL = {
    "intent_architect": "default",
    "research_lead": "reasoning",
    "evidence_ledger": "cheap_worker",
    "analyst": "deep_reasoning",
    "output_strategist": "default",
    "draft_writer": "reasoning",
    "coding_writer": "coding",
    "adversarial_reviewer": "review",
    "verifier": "verification",
    "polisher": "cheap_worker",
    "final_arbiter": "default",
    "visual_designer": "cheap_worker",
    "visual_reviewer": "verification",
    "visual_generator": "cheap_worker",
}

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

FREE_MODEL_PREFERENCES = {
    "deep_reasoning": [
        "nousresearch/hermes-3-llama-3.1-405b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "nvidia/nemotron-3-nano-30b-a3b:free",
        "google/gemma-3-27b-it:free",
        "z-ai/glm-4.5-air:free",
    ],
    "coding": [
        "qwen/qwen3-coder:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-3-12b-it:free",
        "z-ai/glm-4.5-air:free",
    ],
    "review": [
        "meta-llama/llama-3.3-70b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-3-27b-it:free",
        "z-ai/glm-4.5-air:free",
    ],
    "verification": [
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-3-4b-it:free",
        "z-ai/glm-4.5-air:free",
    ],
    "cheap_worker": [
        "google/gemma-3-4b-it:free",
        "google/gemma-3n-e2b-it:free",
        "z-ai/glm-4.5-air:free",
        "liquid/lfm-2.5-1.2b-instruct:free",
    ],
    "default": [
        "z-ai/glm-4.5-air:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "google/gemma-3-4b-it:free",
    ],
}


def get_free_models_from_api() -> list[str]:
    """Fetch current list of free models from OpenRouter API."""
    import httpx
    from artifactforge.config import get_settings

    settings = get_settings()
    api_key = settings.get_openai_api_key()
    base_url = settings.get_openai_base_url()

    try:
        import asyncio

        async def fetch():
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "application/json",
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("data", [])
                    free = [
                        m["id"]
                        for m in models
                        if m.get("pricing", {}).get("prompt") == "0"
                        and m.get("pricing", {}).get("completion") == "0"
                    ]
                    return sorted(free)
                return []

        try:
            asyncio.get_running_loop()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, fetch()).result()
        except RuntimeError:
            return asyncio.run(fetch())
    except Exception as e:
        logger.warning(f"Failed to fetch free models: {e}")
        return []


def test_model_availability(model_id: str, timeout: float = 10.0) -> bool:
    """Test if a single model is available and working."""
    import httpx
    from artifactforge.config import get_settings

    settings = get_settings()
    api_key = settings.get_openai_api_key()
    base_url = settings.get_openai_base_url()

    try:
        import asyncio

        async def test():
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 3,
                    },
                )
                return response.status_code == 200

        try:
            asyncio.get_running_loop()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, test()).result()
        except RuntimeError:
            return asyncio.run(test())
    except Exception:
        return False


def run_model_preflight_check() -> dict[str, str]:
    """Run preflight check to verify models and auto-replace failed ones.

    Returns dict of slot -> working model_id (either original or replaced).
    """
    import logging

    check_logger = logging.getLogger("preflight")

    check_logger.info("Running model preflight check...")
    free_models = get_free_models_from_api()

    if not free_models:
        check_logger.warning("Could not fetch free models, using current config")
        return {slot: model for slot, model in MODEL_REGISTRY.items()}

    check_logger.info(f"Found {len(free_models)} free models available")

    results = {}
    replaced = []

    for slot, model_id in MODEL_REGISTRY.items():
        is_free = ":free" in model_id or model_id == "openrouter/free"

        if is_free:
            if model_id in free_models or model_id == "openrouter/free":
                results[slot] = model_id
                check_logger.info(f"  {slot}: {model_id} (available)")
            else:
                prefs = FREE_MODEL_PREFERENCES.get(
                    slot, FREE_MODEL_PREFERENCES["default"]
                )
                replacement = None
                for candidate in prefs:
                    if candidate in free_models:
                        if test_model_availability(candidate):
                            replacement = candidate
                            break

                if replacement:
                    results[slot] = replacement
                    replaced.append((slot, model_id, replacement))
                    check_logger.warning(
                        f"  {slot}: {model_id} -> {replacement} (replaced)"
                    )
                else:
                    results[slot] = "z-ai/glm-4.5-air:free"
                    check_logger.warning(
                        f"  {slot}: {model_id} -> fallback (no working replacement)"
                    )
        else:
            if test_model_availability(model_id):
                results[slot] = model_id
                check_logger.info(f"  {slot}: {model_id} (paid, testing OK)")
            else:
                prefs = FREE_MODEL_PREFERENCES.get(
                    slot, FREE_MODEL_PREFERENCES["default"]
                )
                replacement = None
                for candidate in prefs:
                    if candidate in free_models and test_model_availability(candidate):
                        replacement = candidate
                        break

                if replacement:
                    results[slot] = replacement
                    replaced.append((slot, model_id, replacement))
                    check_logger.warning(
                        f"  {slot}: {model_id} -> {replacement} (paid failed, replaced with free)"
                    )
                else:
                    results[slot] = "z-ai/glm-4.5-air:free"
                    check_logger.warning(f"  {slot}: {model_id} -> fallback")

    if replaced:
        check_logger.info(f"Replaced {len(replaced)} non-working models")

    return results


_resolved_models_cache: dict[str, str] | None = None


def resolve_model(agent_name: str) -> str:
    """Resolve primary model for an agent with preflight check."""
    global _resolved_models_cache

    if _resolved_models_cache is None:
        _resolved_models_cache = run_model_preflight_check()

    model_key = AGENT_TO_MODEL.get(agent_name, "default")
    return _resolved_models_cache.get(
        model_key, _resolved_models_cache.get("default", "z-ai/glm-4.5-air:free")
    )


def model_candidates_for_agent(agent_name: str) -> list[str]:
    """Get ordered list of primary + fallback models, deduplicated."""
    global _resolved_models_cache

    if _resolved_models_cache is None:
        _resolved_models_cache = run_model_preflight_check()

    seen = set()
    candidates = []

    primary_key = AGENT_TO_MODEL.get(agent_name, "default")
    primary = _resolved_models_cache.get(
        primary_key, _resolved_models_cache.get("default", "z-ai/glm-4.5-air:free")
    )
    candidates.append(primary)
    seen.add(primary)

    for fallback_key in ("fallback_1", "fallback_2"):
        model = _resolved_models_cache.get(fallback_key)
        if model and model not in seen:
            candidates.append(model)
            seen.add(model)

    return candidates


def get_agent_temperature(agent_name: str) -> float:
    """Get temperature setting for an agent."""
    return AGENT_TEMPERATURES.get(agent_name, 0.7)


@dataclass
class LLMRequest:
    """Incoming LLM request."""

    request_id: str
    timestamp: datetime
    provider: Provider
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


TOKEN_COSTS = {
    "anthropic": {
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},  # per 1M tokens
        "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
    },
    "openai": {
        "gpt-4o": {"input": 2.5, "output": 10.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.6},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-4": {"input": 30.0, "output": 60.0},
    },
}


def estimate_tokens(text: str) -> int:
    """Rough token estimation (~4 chars per token)."""
    return len(text) // 4


def calculate_cost(
    provider: Provider, model: str, input_tokens: int, output_tokens: int
) -> float:
    """Calculate cost in USD."""
    costs = TOKEN_COSTS.get(provider, {}).get(model, {"input": 0, "output": 0})
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return input_cost + output_cost


def register_callback(callback: Callable[[LLMCall], None]) -> None:
    """Register a callback for LLM calls (e.g., for metrics, logging)."""
    CALLbacks.append(callback)


def get_call_history(limit: int = 100) -> list[dict]:
    """Get recent LLM call history."""
    return [call.to_dict() for call in CALL_HISTORY[-limit:]]


def get_stats() -> dict:
    """Get aggregate statistics."""
    if not CALL_HISTORY:
        return {
            "total_calls": 0,
            "total_cost_usd": 0.0,
            "total_duration_ms": 0,
            "success_rate": 0.0,
        }

    total = len(CALL_HISTORY)
    successful = sum(1 for c in CALL_HISTORY if c.response.success)
    total_cost = sum(c.response.cost_usd or 0 for c in CALL_HISTORY)
    total_duration = sum(c.response.duration_ms for c in CALL_HISTORY)

    return {
        "total_calls": total,
        "successful_calls": successful,
        "failed_calls": total - successful,
        "success_rate": successful / total if total else 0,
        "total_cost_usd": round(total_cost, 4),
        "total_duration_ms": round(total_duration, 2),
        "avg_duration_ms": round(total_duration / total, 2) if total else 0,
    }


def clear_history() -> None:
    """Clear call history."""
    CALL_HISTORY.clear()


def call_llm(
    system_prompt: str,
    user_prompt: str,
    agent_name: Optional[str] = None,
    provider: Optional[Provider] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Centralized LLM gateway - sync version."""
    import asyncio

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


async def call_llm_async(
    system_prompt: str,
    user_prompt: str,
    agent_name: Optional[str] = None,
    provider: Optional[Provider] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Centralized LLM gateway - async version with monitoring."""
    if provider is None:
        provider = get_provider()

    if model is None and agent_name:
        model = resolve_model(agent_name)

    if model is None:
        model = _get_default_model(provider)

    if temperature == 0.7 and agent_name:
        temperature = get_agent_temperature(agent_name)

    candidates = model_candidates_for_agent(agent_name) if agent_name else [model]
    last_error = None

    for attempt_idx, attempt_model in enumerate(candidates):
        request_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow()

        if attempt_idx > 0:
            wait_time = min(2 ** (attempt_idx - 1) * 0.5, 8)
            logger.info(f"Rate limited, waiting {wait_time:.1f}s before retry...")
            await asyncio.sleep(wait_time)

        start_time = time.perf_counter()
        success = False
        error = None
        output = None
        input_tokens = estimate_tokens(system_prompt + user_prompt)
        output_tokens = 0

        try:
            output = await _call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                provider=provider,
                model=attempt_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            success = True
            output_tokens = estimate_tokens(output)
        except Exception as e:
            error = str(e)
            last_error = error
            is_rate_limit = "429" in str(e) or "rate limit" in str(e).lower()
            if is_rate_limit:
                logger.warning(f"Rate limited on {attempt_model}, backing off...")
                continue
            logger.warning(f"LLM request {request_id} failed with {attempt_model}: {e}")
            continue

        duration_ms = (time.perf_counter() - start_time) * 1000
        cost = (
            calculate_cost(provider, attempt_model, input_tokens, output_tokens)
            if success
            else None
        )

        request = LLMRequest(
            request_id=request_id,
            timestamp=timestamp,
            provider=provider,
            model=attempt_model,
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
            cost_usd=cost,
            raw_response=output[:200] if output else None,
        )

        call = LLMCall(request=request, response=response)
        CALL_HISTORY.append(call)

        for callback in CALLbacks:
            try:
                callback(call)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        if success:
            return output

    raise RuntimeError(f"All model candidates failed. Last error: {last_error}")


def _get_default_model(provider: Provider) -> str:
    """Get default model for provider."""
    defaults = {
        "anthropic": "claude-3-5-sonnet-20241022",
        "openai": "gpt-4o",
        "mock": "mock",
    }
    return defaults.get(provider, "gpt-4o")


def call_llm_sync(
    system_prompt: str,
    user_prompt: str,
    agent_name: Optional[str] = None,
    provider: Optional[Provider] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Synchronous wrapper with monitoring."""
    import asyncio

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


__all__ = [
    "call_llm",
    "call_llm_async",
    "call_llm_sync",
    "register_callback",
    "get_call_history",
    "get_stats",
    "clear_history",
    "resolve_model",
    "model_candidates_for_agent",
    "get_agent_temperature",
    "run_model_preflight_check",
    "LLMCall",
    "LLMRequest",
    "LLMResponse",
    "MODEL_REGISTRY",
    "AGENT_TO_MODEL",
]
