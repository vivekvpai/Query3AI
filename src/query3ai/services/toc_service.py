import json
import litellm  # type: ignore
from query3ai.config.settings import settings

litellm.suppress_debug_info = True

def _call_llm(messages: list[dict], response_format: dict | None = None) -> str:
    """Helper for LLM calls."""
    kwargs = {}
    if settings.get_tree_api_key():
        kwargs["api_key"] = settings.get_tree_api_key()
    if settings.get_tree_api_base():
        kwargs["api_base"] = settings.get_tree_api_base()

    response = litellm.completion(
        model=settings.get_active_tree_model(),
        messages=messages,
        response_format=response_format,
        **kwargs
    )
    return response.choices[0].message.content or ""

def detect_toc(pages: list[dict]) -> tuple[bool, list[int]]:
    """Scans first N pages for a Table of Contents."""
    check_num = settings.TOC_CHECK_PAGE_NUM
    toc_indices = []
    
    for i in range(min(len(pages), check_num)):
        page = pages[i]
        text = page["text"][:2000] # send preview
        
        prompt = settings.TOC_DETECTION_PROMPT.format(text=text)
        
        messages = [{"role": "user", "content": prompt}]
        response = _call_llm(messages).strip().upper()
        
        if "YES" in response:
            toc_indices.append(i)
            
    return len(toc_indices) > 0, toc_indices

def extract_toc(pages: list[dict], toc_page_indices: list[int]) -> str:
    """Extracts and cleans TOC text from specified pages."""
    raw_toc_text = ""
    for idx in toc_page_indices:
        raw_toc_text += pages[idx]["text"] + "\n"
        
    prompt = settings.TOC_EXTRACTION_PROMPT.format(raw_toc_text=raw_toc_text)
    
    messages = [{"role": "user", "content": prompt}]
    return _call_llm(messages).strip()

def has_page_numbers(toc_text: str) -> bool:
    """Detects if the TOC text likely contains page numbers."""
    prompt = settings.TOC_PAGE_NUMBER_PROMPT.format(toc_text=toc_text)
    
    messages = [{"role": "user", "content": prompt}]
    response = _call_llm(messages).strip().upper()
    return "YES" in response

def parse_toc_to_sections(toc_text: str) -> list[dict]:
    """Parses TOC text into a list of structured section dictionaries."""
    prompt = settings.TOC_PARSING_PROMPT.format(toc_text=toc_text)
    
    messages = [{"role": "user", "content": prompt}]
    response_content = _call_llm(messages, response_format={"type": "json_object"})
    
    try:
        data = json.loads(response_content)
        # Handle cases where LLM returns {"sections": [...]} instead of [...]
        if isinstance(data, dict):
            for key in ["sections", "chapters", "toc"]:
                if key in data:
                    return data[key]
        return data if isinstance(data, list) else []
    except Exception:
        return []
