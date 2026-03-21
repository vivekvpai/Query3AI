import re
import ollama  # type: ignore
from groq import Groq  # type: ignore
from config.settings import settings  # type: ignore


def answer(question: str, context_nodes: list[dict]) -> str:
    """Uses Ollama or Groq to answer a question based on filtered sections from Neo4j."""

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
        user_prompt = f"Context:\n{context_text}\n\nQuestion:\n{question}"

        if settings.MODEL_PROVIDER == "groq":
            client = Groq(api_key=settings.GROQ_API_KEY)
            response = client.chat.completions.create(
                model=settings.GROQ_REASONING_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content
        else:
            model = (
                settings.CLOUD_REASONING_MODEL
                if settings.MODEL_PROVIDER == "ollama_cloud"
                else settings.REASONING_MODEL
            )
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response["message"]["content"]

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

