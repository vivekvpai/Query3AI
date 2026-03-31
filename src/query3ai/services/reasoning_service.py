import re
import litellm  # type: ignore

litellm.suppress_debug_info = True

from query3ai.config.settings import settings  # type: ignore


def _call_llm(messages: list[dict]) -> str | None:
    """
    Thin LLM dispatch helper using LiteLLM.
    Returns the raw text content from the model response.
    """
    kwargs = {}
    if settings.get_reasoning_api_key():
        kwargs["api_key"] = settings.get_reasoning_api_key()
    if settings.get_reasoning_api_base():
        kwargs["api_base"] = settings.get_reasoning_api_base()

    response = litellm.completion(
        model=settings.get_active_reasoning_model(),
        messages=messages,
        **kwargs
    )
    return response.choices[0].message.content


def answer(question: str, context_nodes: list[dict]) -> str:
    """Uses LLMs to answer a question based on filtered sections from Neo4j."""

    context_blocks = []
    for node in context_nodes:
        heading = str(node.get("heading", ""))
        chunks = node.get("chunks", [])
        chunk_texts = "\n".join(
            [str(c.get("text", "")) for c in chunks if isinstance(c, dict)]
        )
        if chunk_texts.strip():
            context_blocks.append(f"--- Section: {heading} ---\n{chunk_texts}")

    context_text = "\n\n".join(context_blocks)
    if not context_text:
        context_text = "No relevant context found."

    system_prompt = settings.REASONING_SYSTEM_PROMPT.strip()
    try:
        user_prompt = f"Context: \"{context_text}\"\nQuery: \"{question}\""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        content = _call_llm(messages) or ""

        # Clean up Chain-of-Thought reasoning blocks (e.g. from DeepSeek R1)
        if content:
            content = re.sub(
                r"<think>.*?(?:</think>|$)", "", content, flags=re.DOTALL
            ).strip()
        return content

    except Exception as e:
        err_msg = str(e).lower()
        if any(
            keyword in err_msg for keyword in ["context length", "too large", "rate limit"]
        ):
            return "❌ **Reasoning Model Error:** Generating the answer failed. The filtered search nodes exceeded the strict API token limits! Try narrowing your query!"
        return f"❌ **AI Reasoning Error:** {e}"
