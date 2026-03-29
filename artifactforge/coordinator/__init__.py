"""LangGraph coordinator with checkpointing."""

from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

from artifactforge.coordinator.state import MCRSState
from artifactforge.coordinator import mcrs_graph


def create_app(checkpointer: Optional[Any] = None) -> StateGraph:
    """Create MCRS LangGraph application (10-agent system).

    Args:
        checkpointer: Optional checkpoint store
    """
    return mcrs_graph.create_mcrs_app(checkpointer)


def create_postgres_checkpointer(database_url: str) -> Any:
    """Create PostgreSQL checkpointer from database URL.

    Note: Requires langgraph-checkpoint[postgres] package.
    For now, returns MemorySaver as fallback.
    """
    try:
        from langgraph.checkpoint.postgres import PostgresSaver

        return PostgresSaver.from_conn_string(database_url)
    except ImportError:
        return MemorySaver()


app = create_app()


__all__ = [
    "app",
    "create_app",
    "create_postgres_checkpointer",
]
