import json
import ollama # type: ignore
from groq import Groq # type: ignore
from config.settings import settings # type: ignore

import os

def filter_nodes(question: str, nodes: list) -> list:
    """Uses Ollama or Groq to check each section's relevance individually (YES/NO)."""
    system_prompt = settings.DECISION_SYSTEM_PROMPT.strip()
    
    yes_nodes = []
    
    # Create temp directory and clear any existing file
    import datetime
    temp_dir = os.path.join(os.getcwd(), 'temp_output')
    os.makedirs(temp_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file = os.path.join(temp_dir, f'related_nodes_{timestamp}.json')
    
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump([], f)

    for node in nodes:
        node_id = node.get("node_id", "")
        heading = node.get("heading", "")
        summary = node.get("summary", "")
        keywords = node.get("keywords", [])
        
        # Format keywords as a comma-separated string if it's a list
        keywords_str = ", ".join(keywords) if isinstance(keywords, list) else str(keywords)
        
        chunk_texts = "\n".join([str(c.get("text", "")) for c in node.get("chunks", []) if isinstance(c, dict)])
        
        user_prompt = (
            f"Question: '{question}'\n\n"
            f"Section Heading: {heading}\n"
            f"Section Summary: {summary}\n"
            f"Section Keywords: {keywords_str}\n"
            f"Section Content Details:\n{chunk_texts}\n\n"
            "Based on the content details, is this section relevant? Reply ONLY YES or NO."
        )
        
        try:
            if settings.MODEL_PROVIDER == "groq":
                client = Groq(api_key=settings.GROQ_API_KEY)
                response = client.chat.completions.create(
                    model=settings.GROQ_DECISION_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.0
                )
                raw = response.choices[0].message.content.strip().upper()
            else:
                model = settings.CLOUD_DECISION_MODEL if settings.MODEL_PROVIDER == "ollama_cloud" else settings.DECISION_MODEL
                response = ollama.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                raw = response['message']['content'].strip().upper()

            with open(os.path.join(temp_dir, 'debug.txt'), 'a', encoding='utf-8') as df:
                df.write(f"Query: {question}\nNode {heading} response: {raw}\n---\n")

            if "YES" in raw:
                # Restrict to maximum 5 chunks (leaf nodes) from parent Section exactly as requested
                chunks = node.get("chunks", [])
                node["chunks"] = chunks[:5]
                
                yes_nodes.append(node)
                # Keep updating the JSON dump with the full object
                with open(temp_file, 'w', encoding='utf-8') as f:
                    # Provide a clean view of the related nodes to the JSON
                    dump_data = [
                        {
                            "node_id": n.get("node_id"),
                            "heading": n.get("heading"),
                            "summary": n.get("summary"),
                            "keywords": n.get("keywords", []),
                            "chunks": n.get("chunks", [])
                        } for n in yes_nodes
                    ]
                    json.dump(dump_data, f, indent=2)

        except Exception as e:
            err_msg = str(e).lower()
            if "rate limit" in err_msg or "context window" in err_msg or "too large" in err_msg:
                print(f"Warning: Decision Agent API boundary triggered for node {node_id}")
            else:
                print(f"Warning: Error evaluating node {node_id}: {e}")

    return yes_nodes
