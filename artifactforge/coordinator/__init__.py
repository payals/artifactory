"""LangGraph coordinator with checkpointing."""

from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from artifactforge.coordinator.state import GraphState
from artifactforge.coordinator import nodes


def create_app(checkpointer: Optional[Any] = None) -> StateGraph:
    """Create the LangGraph application."""
    graph = StateGraph(GraphState)

    graph.add_node("router", nodes.router_node)
    graph.add_node("research", nodes.research_node)
    graph.add_node("generate", nodes.generate_node)
    graph.add_node("review", nodes.review_node)
    graph.add_node("verify", nodes.verify_node)
    graph.add_node("ask_user", nodes.ask_user_node)

    graph.set_entry_point("router")

    graph.add_edge("router", "research")
    graph.add_edge("research", "generate")
    graph.add_edge("generate", "review")
    graph.add_edge("review", "verify")

    def should_continue(state: GraphState) -> str:
        if state.get("verification_status") == "passed":
            return "end"
        return "ask_user"

    graph.add_conditional_edges(
        "verify",
        should_continue,
        {
            "end": END,
            "ask_user": "ask_user",
        },
    )

    graph.add_edge("ask_user", "research")

    compile_kwargs: dict[str, Any] = {}
    if checkpointer:
        compile_kwargs["checkpointer"] = checkpointer
    else:
        compile_kwargs["checkpointer"] = MemorySaver()

    return graph.compile(**compile_kwargs)


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


__all__ = ["app", "create_app", "create_postgres_checkpointer"]
