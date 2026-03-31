import json
import litellm  # type: ignore

litellm.suppress_debug_info = True

from query3ai.config.settings import settings  # type: ignore


def build_tree(chunks: list[str]) -> dict:
    """Uses LiteLLM to form a hierarchical tree from chunks."""
    system_prompt = settings.TREE_SYSTEM_PROMPT.strip()

    # Format chunks to match system prompt examples
    chunk_strings = [f'chunk_index {idx}: "{chunk}"\n' for idx, chunk in enumerate(chunks)]
    chunk_text = "".join(chunk_strings)

    user_prompt = chunk_text

    try:
        kwargs = {}
        if settings.get_tree_api_key():
            kwargs["api_key"] = settings.get_tree_api_key()
        if settings.get_tree_api_base():
            kwargs["api_base"] = settings.get_tree_api_base()

        response = litellm.completion(
            model=settings.get_active_tree_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            **kwargs
        )
        raw_content = response.choices[0].message.content or "{}"

        return json.loads(raw_content)

    except Exception as e:
        err_msg = str(e).lower()
        if any(
            keyword in err_msg
            for keyword in ["rate", "context limit", "too large", "maximum context"]
        ):
            raise Exception(
                "Document too large: The extracted chunk text exceeded the AI model's token context window. Ingestion failed."
            )
        raise Exception(f"AI Model Connection Error during Tree Building: {e}")
