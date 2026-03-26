"""
LangGraph StateGraph for Query3AI.

Builds and compiles the query-time pipeline:

    START → fetch_nodes → decision → reasoning → END
                                   ↘ no_results → END  (when filter returns nothing)

Public API:
    run_query_graph(question, doc_id=None) -> str
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END  # type: ignore

from query3ai.langgraph_pipeline.state import QueryState
from query3ai.langgraph_pipeline.nodes import (
    fetch_nodes_node,
    decision_node,
    reasoning_node,
    no_results_node,
)

# ---------------------------------------------------------------------------
# Conditional routing: does the Decision Agent return any nodes?
# ---------------------------------------------------------------------------

def _route_after_decision(state: QueryState) -> str:
    """Route to 'reasoning' if filtered nodes exist, else 'no_results'."""
    if state.get("filtered_nodes"):
        return "reasoning"
    return "no_results"


# ---------------------------------------------------------------------------
# Build the graph (done once at import time)
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    builder = StateGraph(QueryState)

    # Register nodes
    builder.add_node("fetch_nodes", fetch_nodes_node)
    builder.add_node("decision", decision_node)
    builder.add_node("reasoning", reasoning_node)
    builder.add_node("no_results", no_results_node)

    # Edges
    builder.set_entry_point("fetch_nodes")
    builder.add_edge("fetch_nodes", "decision")
    builder.add_conditional_edges(
        "decision",
        _route_after_decision,
        {
            "reasoning": "reasoning",
            "no_results": "no_results",
        },
    )
    builder.add_edge("reasoning", END)
    builder.add_edge("no_results", END)

    return builder.compile()


# Compiled graph singleton — reused for every query invocation
_graph = _build_graph()


# ---------------------------------------------------------------------------
# Public entry point (replaces direct service calls in CLI)
# ---------------------------------------------------------------------------

def run_query_graph(question: str, doc_id: str | None = None) -> str:
    """
    Run the full LangGraph query pipeline and return the final answer string.

    Args:
        question: The user's natural-language question.
        doc_id:   Optional document ID to scope the search.
                  Pass None (default) to search across all ingested documents.

    Returns:
        The answer string from the Reasoning Agent, or an error/no-results message.
    """
    initial_state: QueryState = {
        "question": question,
        "doc_scope": doc_id,
        "all_nodes": [],
        "filtered_nodes": [],
        "answer": "",
        "error": None,
    }

    final_state: QueryState = _graph.invoke(initial_state)
    return final_state.get("answer", "")
