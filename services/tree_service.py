import json
import ollama # type: ignore
from groq import Groq # type_ignore
from config.settings import settings # type: ignore

def build_tree(chunks: list[str]) -> dict:
    """Uses Ollama or Groq to form a hierarchical tree from chunks."""
    system_prompt = settings.TREE_SYSTEM_PROMPT.strip()
    
    chunk_text = ""
    for idx, chunk in enumerate(chunks):
        chunk_text += f"\n--- Chunk {idx} ---\n{chunk}\n"
        
    user_prompt = (
        "Given these document chunks, organise them into a hierarchical tree structure.\n"
        "Return JSON only.\n"
        f"{chunk_text}"
    )
    
    try:
        if settings.USE_GROQ:
            client = Groq(api_key=settings.GROQ_API_KEY)
            response = client.chat.completions.create(
                model=settings.GROQ_TREE_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            raw_content = response.choices[0].message.content
        else:
            model = settings.CLOUD_TREE_MODEL if settings.USE_CLOUD else settings.TREE_MODEL
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                format="json"
            )
            raw_content = response['message']['content']
            
        return json.loads(raw_content)
    except Exception as e:
        err_msg = str(e).lower()
        if "rate" in err_msg or "context limit" in err_msg or "too large" in err_msg or "maximum context" in err_msg:
            raise Exception("Document too large: The extracted chunk text exceeded the AI model's token context window. Ingestion failed.")
        raise Exception(f"AI Model Connection Error during Tree Building: {e}")
