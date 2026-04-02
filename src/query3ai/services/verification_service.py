import random
import litellm  # type: ignore
from query3ai.config.settings import settings

litellm.suppress_debug_info = True

def _call_llm(messages: list[dict]) -> str:
    """Helper for LLM calls."""
    kwargs = {}
    if settings.get_tree_api_key():
        kwargs["api_key"] = settings.get_tree_api_key()
    if settings.get_tree_api_base():
        kwargs["api_base"] = settings.get_tree_api_base()

    response = litellm.completion(
        model=settings.get_active_tree_model(),
        messages=messages,
        **kwargs
    )
    return response.choices[0].message.content or ""

def verify_tree(
    tree: dict, 
    pages: list[dict], 
    sample_size: int | None = None
) -> dict:
    """Verifies that section headings appear in their assigned page ranges."""
    sample_size = sample_size or settings.VERIFICATION_SAMPLE_SIZE
    
    sections = []
    for chapter in tree.get("chapters", []):
        for section in chapter.get("sections", []):
            sections.append(section)
            
    if not sections:
        return {"accuracy": 1.0, "total_checked": 0, "correct_count": 0, "incorrect_nodes": []}
        
    to_check = random.sample(sections, min(len(sections), sample_size))
    incorrect_nodes = []
    
    for sec in to_check:
        heading = sec.get("heading")
        start_page = sec.get("start_page")
        
        if not start_page:
            incorrect_nodes.append(sec)
            continue
            
        # Get text from start_page and start_page + 1
        relevant_pages = [p for p in pages if start_page <= p.get("page_number", 0) <= start_page + 1]
        text = "\n".join([p["text"] for p in relevant_pages])
        
        prompt = settings.VERIFICATION_PROMPT.format(heading=heading, text=text[:2000])
        
        messages = [{"role": "user", "content": prompt}]
        response = _call_llm(messages).strip().upper()
        
        if "YES" not in response:
            incorrect_nodes.append(sec)
            
    correct_count = len(to_check) - len(incorrect_nodes)
    accuracy = correct_count / len(to_check) if to_check else 1.0
    
    return {
        "accuracy": accuracy,
        "total_checked": len(to_check),
        "correct_count": correct_count,
        "incorrect_nodes": incorrect_nodes
    }

def correct_nodes(
    tree: dict,
    pages: list[dict],
    incorrect_nodes: list[dict],
    max_retries: int | None = None
) -> dict:
    """Corrects each incorrect node by searching a narrow page range."""
    max_retries = max_retries or settings.CORRECTION_MAX_RETRIES
    
    # Simple correction: Expand search range around reported start_page
    for node in incorrect_nodes:
        heading = node.get("heading")
        current_start = node.get("start_page", 1)
        
        # Search range: current_start - 5 to current_start + 10
        search_range_start = max(1, current_start - 5)
        search_range_end = min(len(pages), current_start + 10)
        
        range_pages = [p for p in pages if search_range_start <= p.get("page_number", 0) <= search_range_end]
        range_text = ""
        for p in range_pages:
            range_text += f"PA_GE {p['page_number']}:\n{p['text'][:500]}\n"
            
        prompt = settings.CORRECTION_PROMPT.format(
            heading=heading,
            search_range_start=search_range_start,
            search_range_end=search_range_end,
            range_text=range_text
        )
        
        messages = [{"role": "user", "content": prompt}]
        response = _call_llm(messages).strip()
        
        try:
            new_page = int(response)
            if new_page > 0:
                node["start_page"] = new_page
                # End page heuristic: either next section start or +5 pages
                node["end_page"] = min(len(pages), new_page + 5)
        except Exception:
            pass
            
    return tree

def get_accuracy_threshold() -> float:
    return settings.VERIFICATION_ACCURACY_THRESHOLD
