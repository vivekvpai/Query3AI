"""
TOC Service — detects, extracts, and parses Table of Contents from documents.

Uses the unified LLM client for all model calls.
"""
from __future__ import annotations

import json

from query3ai.config.settings import settings
from query3ai.services.llm_client import call_llm


def detect_toc(pages: list[dict]) -> tuple[bool, list[int]]:
    """Scans first N pages for a Table of Contents."""
    check_num = settings.TOC_CHECK_PAGE_NUM
    toc_indices: list[int] = []

    for i in range(min(len(pages), check_num)):
        page = pages[i]
        text = page["text"][:2000]  # send preview

        prompt = settings.TOC_DETECTION_PROMPT.format(text=text)

        messages = [{"role": "user", "content": prompt}]
        response = call_llm("tree", messages).upper()

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
    return call_llm("tree", messages)


def has_page_numbers(toc_text: str) -> bool:
    """Detects if the TOC text likely contains page numbers."""
    prompt = settings.TOC_PAGE_NUMBER_PROMPT.format(toc_text=toc_text)

    messages = [{"role": "user", "content": prompt}]
    response = call_llm("tree", messages).upper()
    return "YES" in response


def parse_toc_to_sections(toc_text: str) -> list[dict]:
    """Parses TOC text into a list of structured section dictionaries."""
    prompt = settings.TOC_PARSING_PROMPT.format(toc_text=toc_text)

    messages = [{"role": "user", "content": prompt}]
    response_content = call_llm(
        "tree", messages, response_format={"type": "json_object"}
    )

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
