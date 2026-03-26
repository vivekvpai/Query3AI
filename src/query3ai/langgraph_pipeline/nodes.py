"""
LangGraph node functions for the Query3AI pipeline.

Each function receives the current QueryState and returns a dict with the keys it updates.
No LLM logic lives here — all LLM calls are delegated to the existing service modules.

Pipeline:
  fetch_nodes_node → decision_node → reasoning_node  (or no_results_node)
"""
from __future__ import annotations

from query3ai.langgraph_pipeline.state import QueryState
from query3ai.services import graph_service, decision_service, reasoning_service


# ---------------------------------------------------------------------------
# Node 1: Fetch sections from Neo4j
# ---------------------------------------------------------------------------

def fetch_nodes_node(state: QueryState) -> dict:
    """Retrieves all relevant section nodes from the Neo4j graph store."""
    try:
        doc_scope = state.get("doc_scope")
        if doc_scope:
            result = graph_service.get_nodes(doc_scope)
            nodes = result.get("sections", [])
        else:
            nodes = graph_service.get_all_nodes()

        return {"all_nodes": nodes}

    except Exception as exc:
        return {"all_nodes": [], "error": f"Neo4j fetch error: {exc}"}


# ---------------------------------------------------------------------------
# Node 2: Decision / Relevance Filter Agent
# ---------------------------------------------------------------------------

def decision_node(state: QueryState) -> dict:
    """Calls the Decision Agent to filter sections relevant to the question."""
    # Short-circuit if a previous node already set an error
    if state.get("error"):
        return {"filtered_nodes": []}

    all_nodes = state.get("all_nodes", [])
    question = state["question"]

    if not all_nodes:
        return {"filtered_nodes": []}

    try:
        filtered = decision_service.filter_nodes(question, all_nodes)
        return {"filtered_nodes": filtered}
    except Exception as exc:
        return {"filtered_nodes": [], "error": f"Decision Agent error: {exc}"}


# ---------------------------------------------------------------------------
# Node 3a: Reasoning Agent (happy path)
# ---------------------------------------------------------------------------

def reasoning_node(state: QueryState) -> dict:
    """Calls the Reasoning Agent to produce the final answer from filtered sections."""
    question = state["question"]
    filtered_nodes = state.get("filtered_nodes", [])

    # Delegate entirely to reasoning_service which has its own error handling
    answer = reasoning_service.answer(question, filtered_nodes)
    return {"answer": answer}


# ---------------------------------------------------------------------------
# Node 3b: No-results fallback (when Decision Agent filtered out everything)
# ---------------------------------------------------------------------------

def no_results_node(state: QueryState) -> dict:
    """Returns a friendly message when no sections passed the relevance filter."""
    return {
        "answer": (
            "⚠️ **No relevant sections found.**\n\n"
            "The Decision Agent did not identify any document sections related to your question. "
            "Try rephrasing your query or checking that the relevant document has been ingested."
        )
    }
