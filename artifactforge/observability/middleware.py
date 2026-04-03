"""Observability middleware for LangGraph nodes."""

import contextvars
import functools
import json
import threading
import time
import uuid
from pathlib import Path
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


# ---------------------------------------------------------------------------
# Intermediate state dump to disk
# ---------------------------------------------------------------------------

_STATE_DUMP_DIR = Path(__file__).parent.parent.parent / "outputs"

_DUMP_FIELDS: frozenset[str] = frozenset({
    "user_prompt", "output_constraints",
    "execution_brief", "research_map", "claim_ledger",
    "analytical_backbone", "content_blueprint",
    "draft_v1", "red_team_review", "verification_report",
    "polished_draft", "release_decision",
    "visual_specs", "visual_reviews", "generated_visuals", "final_with_visuals",
    "revision_history", "revision_quality_history",
    "errors", "stage_timing", "current_stage",
    "trace_id", "artifact_id",
})


def _dump_state(trace_id: str, node_name: str, state: dict, result: dict) -> None:
    """Best-effort dump of pipeline state to disk after a node completes."""
    try:
        merged = {**state, **result}
        filtered = {k: v for k, v in merged.items() if k in _DUMP_FIELDS and v is not None}

        run_dir = _STATE_DUMP_DIR / trace_id
        run_dir.mkdir(parents=True, exist_ok=True)

        def _write(path: Path, data: dict) -> None:
            path.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False))

        _write(run_dir / f"state_after_{node_name}.json", filtered)
        _write(run_dir / "state_latest.json", filtered)
    except Exception as exc:
        logger.warning("state_dump_failed", node=node_name, error=str(exc))


# Mapping from node name to the primary output field it produces.
# Used by resume logic to skip nodes whose output already exists.
_NODE_OUTPUT_KEY: dict[str, str] = {
    "intent_architect": "execution_brief",
    "research_lead": "research_map",
    "evidence_ledger": "claim_ledger",
    "analyst": "analytical_backbone",
    "output_strategist": "content_blueprint",
    "draft_writer": "draft_v1",
    "adversarial_reviewer": "red_team_review",
    "verifier": "verification_report",
    "polisher": "polished_draft",
    "final_arbiter": "release_decision",
}


def trace_node(node_name: str) -> Callable:
    """Decorator to add observability to LangGraph nodes.

    Logs entry, exit, timing, errors, and LLM token usage for each node.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(state: dict[str, Any], *args, **kwargs) -> dict[str, Any]:
            # ----------------------------------------------------------
            # Resume: skip nodes whose output was loaded from disk
            # ----------------------------------------------------------
            resumed_nodes: set | None = state.get("_resumed_nodes")
            output_key = _NODE_OUTPUT_KEY.get(node_name)
            if (
                resumed_nodes is not None
                and output_key
                and output_key in resumed_nodes
                and state.get(output_key) is not None
            ):
                logger.info(
                    "node_skipped_resume",
                    node=node_name,
                    output_key=output_key,
                )
                emit_status(
                    f"Skipped (resumed from disk)",
                    trace_id=state.get("trace_id"),
                    node_name=node_name,
                    metadata={"kind": "status", "phase": "skipped"},
                )
                # Remove key so revision loops re-execute this node
                remaining = resumed_nodes - {output_key}
                return {"_resumed_nodes": remaining or None}

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

                # Persist node execution and evaluation data to DB
                try:
                    from artifactforge.db.persistence import get_persistence

                    persistence = get_persistence()
                    artifact_id = state.get("artifact_id")
                    if artifact_id and persistence.enabled:
                        persistence.record_node(
                            artifact_id=artifact_id,
                            node_name=node_name,
                            duration_ms=int(elapsed * 1000),
                            tokens=llm_stats.get("llm_calls", 0) * 1000,
                            cost=llm_stats.get("llm_cost_usd", 0.0),
                            success=True,
                        )

                        # Record evaluations for reviewer/verifier/arbiter
                        if node_name == "adversarial_reviewer":
                            review = result.get("red_team_review")
                            if review:
                                persistence.record_evaluation(
                                    artifact_id=artifact_id,
                                    node_name=node_name,
                                    issues=review.get("issues", []),
                                    passed=review.get("passed", False),
                                )
                        elif node_name == "verifier":
                            report = result.get("verification_report")
                            if report:
                                persistence.record_evaluation(
                                    artifact_id=artifact_id,
                                    node_name=node_name,
                                    issues=report.get("items", []),
                                    passed=report.get("passed", False),
                                )
                        elif node_name == "final_arbiter":
                            decision = result.get("release_decision")
                            if decision:
                                persistence.record_quality_gate(
                                    artifact_id=artifact_id,
                                    gate_name="final_arbiter",
                                    passed=decision.get("status") == "READY",
                                    score=decision.get("confidence"),
                                    details=decision,
                                )
                except Exception:
                    pass

                # Dump intermediate state to disk (best-effort)
                if trace_id:
                    _dump_state(trace_id, node_name, state, result)

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

                # Persist failed node execution to DB
                try:
                    from artifactforge.db.persistence import get_persistence

                    persistence = get_persistence()
                    artifact_id = state.get("artifact_id")
                    if artifact_id and persistence.enabled:
                        persistence.record_node(
                            artifact_id=artifact_id,
                            node_name=node_name,
                            duration_ms=int(elapsed * 1000),
                            tokens=0,
                            cost=0.0,
                            success=False,
                            error=str(e),
                        )
                except Exception:
                    pass

                # Dump state on error too — captures partial progress
                if trace_id:
                    _dump_state(trace_id, node_name, state, result)

                raise

        return wrapper

    return decorator


__all__ = ["trace_node", "get_trace_id", "set_trace_id", "emit_status"]
