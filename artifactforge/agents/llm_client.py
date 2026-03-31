"""Shared LLM client for MCRS agents."""

import json
import os
from typing import Literal

import httpx

from artifactforge.config import get_settings

settings = get_settings()
OPENAI_API_KEY = settings.get_openai_api_key()
OPENAI_API_BASE = settings.get_openai_base_url()
ANTHROPIC_API_KEY = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")

MLX_SERVER_URL = os.getenv("MLX_SERVER_URL", "")
MLX_MODEL_PATH = os.getenv(
    "MLX_MODEL_PATH",
    "/Users/pi/.cache/huggingface/hub/models--mlx-community--Qwen3.5-9B-MLX-4bit/snapshots/938d8919941c6e7efd3c7150eff7fe9d12afa631",
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2.5:cloud")


Provider = Literal["openai", "anthropic", "mock", "openrouter", "mlx", "ollama"]


def get_provider() -> Provider:
    if OLLAMA_BASE_URL and OLLAMA_BASE_URL.strip():
        return "ollama"
    if MLX_SERVER_URL and MLX_SERVER_URL.strip():
        return "mlx"
    if OPENAI_API_KEY:
        if "openrouter.ai" in OPENAI_API_BASE:
            return "openrouter"
        return "openai"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return "mock"


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    provider: Provider | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
) -> str:
    if provider is None:
        provider = get_provider()

    if provider == "ollama":
        return await _call_ollama(
            system_prompt,
            user_prompt,
            model or OLLAMA_MODEL,
            temperature,
            max_tokens,
        )
    elif provider == "mlx":
        return await _call_mlx(
            system_prompt,
            user_prompt,
            model or "qwen3.5-9b-mlx",
            temperature,
            max_tokens,
        )
    elif provider == "openrouter":
        return await _call_openai(
            system_prompt,
            user_prompt,
            model or "z-ai/glm-4.5-air:free",
            temperature,
            max_tokens,
        )
    elif provider == "anthropic":
        return await _call_anthropic(
            system_prompt,
            user_prompt,
            model or "claude-3-5-sonnet-20241022",
            temperature,
            max_tokens,
        )
    elif provider == "openai":
        return await _call_openai(
            system_prompt, user_prompt, model or "gpt-4o", temperature, max_tokens
        )
    else:
        return _mock_response(user_prompt)


async def _call_anthropic(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Call Anthropic API."""
    assert ANTHROPIC_API_KEY is not None

    combined_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        response.raise_for_status()
        data = response.json()

    return data["content"][0]["text"]


async def _call_openai(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    """Call OpenAI-compatible API (supports OpenRouter)."""
    assert OPENAI_API_KEY is not None

    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            f"{OPENAI_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()

    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning") or ""


async def _call_mlx(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    mlx_model = "qwen3.5-9b-mlx" if model == "mlx" else model
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            f"{MLX_SERVER_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": mlx_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()

    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning") or ""


async def _call_ollama(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> str:
    ollama_model = model if model and model != "ollama" else OLLAMA_MODEL
    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": ollama_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "options": {"num_predict": max_tokens},
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()

    return data.get("message", {}).get("content", "")


def _mock_response(user_prompt: str) -> str:
    """Mock response when no API keys available."""
    return json.dumps(
        {
            "error": "No LLM API key configured",
            "received_prompt_length": len(user_prompt),
        }
    )


def call_llm_sync(
    system_prompt: str,
    user_prompt: str,
    provider: Provider | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 32000,
) -> str:
    """Synchronous wrapper for call_llm."""
    import asyncio

    return asyncio.run(
        call_llm(system_prompt, user_prompt, provider, model, temperature, max_tokens)
    )


__all__ = ["call_llm", "call_llm_sync", "get_provider", "Provider"]
