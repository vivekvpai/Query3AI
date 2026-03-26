"""
Query state definition for the LangGraph pipeline.
All nodes read from and write to this shared TypedDict.
"""
from __future__ import annotations
from typing import Optional
from typing_extensions import TypedDict


class QueryState(TypedDict):
    """Shared state passed between every node in the Query3AI LangGraph pipeline."""

    # Input
    question: str                      # The user's question
    doc_scope: Optional[str]           # Optional doc_id to scope the search; None = global (all docs)

    # Intermediate
    all_nodes: list[dict]              # All section nodes fetched from Neo4j
    filtered_nodes: list[dict]         # Sections that passed the Decision Agent filter

    # Output
    answer: str                        # Final answer produced by the Reasoning Agent
    error: Optional[str]               # Set if any node encounters a fatal error
