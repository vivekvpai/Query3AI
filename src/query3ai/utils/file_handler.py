import os
import fitz  # PyMuPDF
import docx

def get_file_extension(file_path: str) -> str:
    _, ext = os.path.splitext(file_path)
    return ext.lower()

def extract_from_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def extract_pages_from_txt(file_path: str) -> list[dict]:
    text = extract_from_txt(file_path)
    return [{
        "page_number": 1,
        "text": text,
        "token_count": len(text.split())
    }]

def extract_from_pdf(file_path: str) -> str:
    text = ""
    with fitz.open(file_path) as pdf_doc:
        for page in pdf_doc:
            text += page.get_text() + "\n"
    return text

def extract_pages_from_pdf(file_path: str) -> list[dict]:
    pages = []
    with fitz.open(file_path) as pdf_doc:
        for page_num, page in enumerate(pdf_doc, start=1):
            text = page.get_text()
            pages.append({
                "page_number": page_num,
                "text": text,
                "token_count": len(text.split())
            })
    return pages

def extract_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_pages_from_docx(file_path: str) -> list[dict]:
    doc = docx.Document(file_path)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    pages = []
    chunk_size = 20 # heuristic: 20 paragraphs per "page"
    for i in range(0, len(paragraphs), chunk_size):
        page_text = "\n".join(paragraphs[i:i + chunk_size])
        pages.append({
            "page_number": (i // chunk_size) + 1,
            "text": page_text,
            "token_count": len(page_text.split())
        })
    return pages

def extract_raw_text(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = get_file_extension(file_path)

    if ext == ".txt" or ext == ".md":
        return extract_from_txt(file_path)
    elif ext == ".pdf":
        return extract_from_pdf(file_path)
    elif ext == ".docx":
        return extract_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def extract_pages_raw(file_path: str) -> list[dict]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = get_file_extension(file_path)

    if ext == ".txt" or ext == ".md":
        return extract_pages_from_txt(file_path)
    elif ext == ".pdf":
        return extract_pages_from_pdf(file_path)
    elif ext == ".docx":
        return extract_pages_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
