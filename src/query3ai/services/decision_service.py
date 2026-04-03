"""
Decision Service — filters document sections by relevance to a user query.

Uses the unified LLM client for all model calls.
"""
from __future__ import annotations

import json
from datetime import datetime

from rich.console import Console  # type: ignore

from query3ai.config.paths import TEMP_OUTPUT_DIR  # type: ignore
from query3ai.config.settings import settings  # type: ignore
from query3ai.services.llm_client import call_llm

console = Console()


def filter_nodes(question: str, nodes: list) -> list:
    """Uses the Decision Agent to check each section's relevance (YES/NO)."""
    system_prompt = settings.DECISION_SYSTEM_PROMPT.strip()
    yes_nodes: list[dict] = []

    # Ensure global temp directory exists
    TEMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file = TEMP_OUTPUT_DIR / f"related_nodes_{timestamp}.json"

    debug_logs: list[str] = []

    if len(nodes) > 15:
        console.print(f"  [dim]Global Context: Batch evaluating {len(nodes)} sections sequentially...[/dim]")

    for node in nodes:
        node_id = node.get("node_id", "")
        heading = node.get("heading", "")
        summary = node.get("summary", "")

        user_prompt = (
            f'Query: "{question}"\n'
            f'Heading: "{heading}" | Summary: "{summary}"'
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw = call_llm("decision", messages, temperature=0.0).upper()
            debug_logs.append(f"Query: {question}\nNode {heading} response: {raw}\n---\n")

            if "YES" in raw:
                # Restrict to maximum 5 chunks (leaf nodes) from parent Section
                chunks = node.get("chunks", [])
                node["chunks"] = chunks[:5]
                yes_nodes.append(node)

        except Exception as e:
            err_msg = str(e).lower()
            if any(
                keyword in err_msg for keyword in ["rate limit", "context window", "too large"]
            ):
                console.print(f"[yellow]Warning: Decision Agent API boundary triggered for node {node_id}[/yellow]")
            else:
                console.print(f"[red]Warning: Error evaluating node {node_id}: {e}[/red]")

    # Write debug file once at the end
    if debug_logs:
        debug_file = TEMP_OUTPUT_DIR / "debug.txt"
        with open(debug_file, "a", encoding="utf-8") as df:
            df.write("".join(debug_logs))

    # Write temp file once at the end
    dump_data = [
        {
            "node_id": n.get("node_id"),
            "heading": n.get("heading"),
            "summary": n.get("summary"),
            "keywords": n.get("keywords", []),
            "chunks": n.get("chunks", []),
        }
        for n in yes_nodes
    ]
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(dump_data, f, indent=2)

    return yes_nodes
