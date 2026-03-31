"""Observability middleware for LangGraph nodes."""

import asyncio
import contextvars
import functools
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Optional

import structlog

from artifactforge.observability.events import get_event_emitter

logger = structlog.get_logger(__name__)

TRACE_ID_CTX: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "TRACE_ID_CTX", default=None
)
_LLM_STATS_BEFORE: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "_LLM_STATS_BEFORE", default=None
)

STATUS_UPDATE_INTERVAL = 5.0


def emit_status(
    message: str,
    *,
    trace_id: Optional[str] = None,
    node_name: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    resolved_trace_id = trace_id or get_trace_id()
    logger.info(
        "status_update",
        trace_id=resolved_trace_id,
        node=node_name,
        message=message,
        **(metadata or {}),
    )
    get_event_emitter().emit_status(
        resolved_trace_id,
        message,
        node_name=node_name,
        metadata=metadata or {},
    )


def _start_heartbeat(
    trace_id: str, node_name: str
) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()

    def heartbeat() -> None:
        while not stop_event.wait(STATUS_UPDATE_INTERVAL):
            emit_status(
                "Still running",
                trace_id=trace_id,
                node_name=node_name,
                metadata={"kind": "heartbeat"},
            )

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    return stop_event, thread


def get_trace_id() -> str:
    """Get or create trace ID for current execution."""
    trace_id = TRACE_ID_CTX.get()
    if trace_id is None:
        trace_id = str(uuid.uuid4())
        TRACE_ID_CTX.set(trace_id)
    return trace_id


def set_trace_id(trace_id: str) -> None:
    """Set trace ID for current execution."""
    TRACE_ID_CTX.set(trace_id)


def _capture_llm_stats(node_name: str) -> dict:
    """Capture LLM stats for a node."""
    try:
        from artifactforge.agents.llm_gateway import get_stats

        stats_store = _LLM_STATS_BEFORE.get() or {}
        stats_before = stats_store.get(
            node_name, {"total_calls": 0, "total_cost_usd": 0.0}
        )
        current_stats = get_stats()

        delta_calls = current_stats["total_calls"] - stats_before["total_calls"]
        delta_cost = current_stats["total_cost_usd"] - stats_before["total_cost_usd"]

        stats_store[node_name] = current_stats
        _LLM_STATS_BEFORE.set(stats_store)

        return {
            "llm_calls": delta_calls,
            "llm_cost_usd": delta_cost,
        }
    except Exception:
        return {"llm_calls": 0, "llm_cost_usd": 0.0}


def _record_llm_stats(node_name: str) -> None:
    """Record LLM stats before node execution for delta calculation."""
    try:
        from artifactforge.agents.llm_gateway import get_stats

        stats_store = _LLM_STATS_BEFORE.get() or {}
        stats_store[node_name] = get_stats()
        _LLM_STATS_BEFORE.set(stats_store)
    except Exception:
        pass


def trace_node(node_name: str) -> Callable:
    """Decorator to add observability to LangGraph nodes.

    Logs entry, exit, timing, errors, and LLM token usage for each node.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(state: dict[str, Any], *args, **kwargs) -> dict[str, Any]:
            trace_id = state.get("trace_id") or get_trace_id()
            set_trace_id(trace_id)
            start_time = time.perf_counter()

            _record_llm_stats(node_name)
            heartbeat_stop, heartbeat_thread = _start_heartbeat(trace_id, node_name)

            emit_status(
                "Starting node execution",
                trace_id=trace_id,
                node_name=node_name,
                metadata={"kind": "status", "phase": "start"},
            )

            logger.info(
                "node_entry",
                node=node_name,
                trace_id=trace_id,
                has_execution_brief=bool(state.get("execution_brief")),
                has_research_map=bool(state.get("research_map")),
            )

            get_event_emitter().emit_node_entry(
                trace_id=trace_id,
                node_name=node_name,
                metadata={
                    "has_execution_brief": bool(state.get("execution_brief")),
                    "has_research_map": bool(state.get("research_map")),
                },
            )

            try:
                result = func(state, *args, **kwargs)

                elapsed = time.perf_counter() - start_time
                llm_stats = _capture_llm_stats(node_name)

                heartbeat_stop.set()
                heartbeat_thread.join(timeout=0.1)

                emit_status(
                    f"Completed in {elapsed:.1f}s",
                    trace_id=trace_id,
                    node_name=node_name,
                    metadata={"kind": "status", "phase": "complete"},
                )

                result = result or {}
                result["current_stage"] = node_name
                result["trace_id"] = trace_id

                if "stage_timing" not in result:
                    result["stage_timing"] = state.get("stage_timing", {})
                result["stage_timing"][node_name] = elapsed

                if "stage_metadata" not in result:
                    result["stage_metadata"] = state.get("stage_metadata", {})
                result["stage_metadata"][node_name] = {
                    "entry_time": start_time,
                    "exit_time": time.perf_counter(),
                    "duration_ms": int(elapsed * 1000),
                    "success": True,
                    "llm_calls": llm_stats.get("llm_calls", 0),
                    "llm_cost_usd": llm_stats.get("llm_cost_usd", 0.0),
                }

                tokens_used = dict(state.get("tokens_used", {}))
                tokens_used[node_name] = llm_stats.get("llm_calls", 0) * 1000
                result["tokens_used"] = tokens_used

                costs = dict(state.get("costs", {}))
                costs[node_name] = llm_stats.get("llm_cost_usd", 0.0)
                result["costs"] = costs

                logger.info(
                    "node_exit",
                    node=node_name,
                    trace_id=trace_id,
                    duration_ms=int(elapsed * 1000),
                    llm_calls=llm_stats.get("llm_calls", 0),
                    llm_cost_usd=llm_stats.get("llm_cost_usd", 0.0),
                    success=True,
                )

                get_event_emitter().emit_node_exit(
                    trace_id=trace_id,
                    node_name=node_name,
                    duration_ms=int(elapsed * 1000),
                    success=True,
                    metadata={
                        "llm_calls": llm_stats.get("llm_calls", 0),
                        "llm_cost_usd": llm_stats.get("llm_cost_usd", 0.0),
                    },
                )

                try:
                    from artifactforge.observability.metrics import (
                        StageMetrics,
                        get_metrics_collector,
                    )

                    collector = get_metrics_collector()
                    pool = getattr(collector, "_pool", None)
                    if pool:
                        stage_metrics = StageMetrics(
                            trace_id=trace_id,
                            node_name=node_name,
                            start_time=datetime.fromtimestamp(start_time),
                            end_time=datetime.fromtimestamp(time.perf_counter()),
                            duration_ms=int(elapsed * 1000),
                            success=True,
                            tokens_used=llm_stats.get("llm_calls", 0) * 1000,
                            cost=llm_stats.get("llm_cost_usd", 0.0),
                        )
                        asyncio.create_task(collector.record_stage(stage_metrics))
                except Exception:
                    pass

                return result

            except Exception as e:
                elapsed = time.perf_counter() - start_time
                errors = list(state.get("errors", []))
                errors.append(f"{node_name}: {str(e)}")

                heartbeat_stop.set()
                heartbeat_thread.join(timeout=0.1)

                emit_status(
                    f"ERROR: {type(e).__name__}: {str(e)[:100]}",
                    trace_id=trace_id,
                    node_name=node_name,
                    metadata={"kind": "status", "phase": "error"},
                )

                logger.error(
                    "node_error",
                    node=node_name,
                    trace_id=trace_id,
                    duration_ms=int(elapsed * 1000),
                    error=str(e),
                    error_type=type(e).__name__,
                )

                get_event_emitter().emit_node_error(
                    trace_id=trace_id,
                    node_name=node_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=int(elapsed * 1000),
                )

                result = {
                    "current_stage": node_name,
                    "trace_id": trace_id,
                    "errors": errors,
                    "stage_timing": state.get("stage_timing", {}),
                    "stage_metadata": state.get("stage_metadata", {}),
                    "tokens_used": state.get("tokens_used", {}),
                    "costs": state.get("costs", {}),
                }
                result["stage_timing"][node_name] = elapsed
                result["stage_metadata"][node_name] = {
                    "entry_time": start_time,
                    "exit_time": time.perf_counter(),
                    "duration_ms": int(elapsed * 1000),
                    "success": False,
                    "error": str(e),
                }

                try:
                    from artifactforge.observability.metrics import (
                        StageMetrics,
                        get_metrics_collector,
                    )

                    collector = get_metrics_collector()
                    pool = getattr(collector, "_pool", None)
                    if pool:
                        stage_metrics = StageMetrics(
                            trace_id=trace_id,
                            node_name=node_name,
                            start_time=datetime.fromtimestamp(start_time),
                            end_time=datetime.fromtimestamp(time.perf_counter()),
                            duration_ms=int(elapsed * 1000),
                            success=False,
                            error=str(e),
                        )
                        asyncio.create_task(collector.record_stage(stage_metrics))
                except Exception:
                    pass

                raise

        return wrapper

    return decorator


__all__ = ["trace_node", "get_trace_id", "set_trace_id", "emit_status"]
