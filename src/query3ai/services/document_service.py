from query3ai.utils.file_handler import extract_raw_text, extract_pages_raw

def extract_text(file_path: str) -> str:
    """Wrapper to extract text safely."""
    return extract_raw_text(file_path)

def extract_pages(file_path: str) -> list[dict]:
    """Returns page-level extraction: [{"page_number": int, "text": str, "token_count": int}]"""
    return extract_pages_raw(file_path)

def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Splits text into overlapping chunks of ~chunk_size words."""
    words = text.split()
    chunks = []
    
    overlap = max(50, chunk_size // 10) # roughly 10% overlap or at least 50 words
    if chunk_size <= overlap:
        overlap = 0

    step = chunk_size - overlap
    if step <= 0:
        step = chunk_size

    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        
    return chunks
