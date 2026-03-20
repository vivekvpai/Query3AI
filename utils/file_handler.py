import os
import fitz  # PyMuPDF
import docx

def get_file_extension(file_path: str) -> str:
    _, ext = os.path.splitext(file_path)
    return ext.lower()

def extract_from_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def extract_from_pdf(file_path: str) -> str:
    text = ""
    with fitz.open(file_path) as pdf_doc:
        for page in pdf_doc:
            text += page.get_text() + "\n"
    return text

def extract_from_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

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
