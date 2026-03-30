import json
import datetime
import litellm  # type: ignore

litellm.suppress_debug_info = True

from rich.console import Console  # type: ignore
from query3ai.config.settings import settings  # type: ignore
from query3ai.config.paths import TEMP_OUTPUT_DIR  # type: ignore

console = Console()


def _call_llm(messages: list[dict], temperature: float = 0.0) -> str:
    """
    Thin LLM dispatch helper shared across this module using LiteLLM.
    Returns the raw text content from the model response.
    """
    kwargs = {}
    if settings.LLM_API_KEY:
        kwargs["api_key"] = settings.LLM_API_KEY
    if settings.get_api_base():
        kwargs["api_base"] = settings.get_api_base()

    response = litellm.completion(
        model=settings.get_active_decision_model(),
        messages=messages,
        temperature=temperature,
        **kwargs
    )
    content = response.choices[0].message.content or ""
    return content.strip().upper()


def filter_nodes(question: str, nodes: list) -> list:
    """Uses LLMs to check each section's relevance individually (YES/NO)."""
    system_prompt = settings.DECISION_SYSTEM_PROMPT.strip()

    yes_nodes = []

    # Ensure global temp directory exists
    TEMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file = TEMP_OUTPUT_DIR / f"related_nodes_{timestamp}.json"

    debug_logs = []

    if len(nodes) > 15:
        console.print(f"  [dim]Global Context: Batch evaluating {len(nodes)} sections sequentially...[/dim]")

    for node in nodes:
        node_id = node.get("node_id", "")
        heading = node.get("heading", "")
        summary = node.get("summary", "")
        keywords = node.get("keywords", [])

        # Format keywords as a comma-separated string if it's a list
        keywords_str = (
            ", ".join(keywords) if isinstance(keywords, list) else str(keywords)
        )

        chunk_texts = "\n".join(
            [
                str(c.get("text", ""))
                for c in node.get("chunks", [])
                if isinstance(c, dict)
            ]
        )

        user_prompt = (
            f"Question: \"{question}\"\n"
            f"Section heading: \"{heading}\"\n"
            f"Section summary: \"{summary}\"\n"
            f"Section keywords: \"{keywords_str}\"\n\nContent details:\n{chunk_texts}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw = _call_llm(messages, temperature=0.0)
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
