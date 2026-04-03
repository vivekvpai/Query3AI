import json
from query3ai.config.settings import settings  # type: ignore
from query3ai.services.llm_client import call_llm
from query3ai.services.toc_service import detect_toc, extract_toc, has_page_numbers, parse_toc_to_sections
from query3ai.services.verification_service import verify_tree, correct_nodes, get_accuracy_threshold


def split_pages_with_overlap(
    pages: list[dict], batch_size: int, overlap: int
) -> list[list[dict]]:
    """Splits pages into overlapping batches."""
    batches = []
    step = batch_size - overlap
    if step <= 0:
        step = 1
    for i in range(0, len(pages), step):
        batch = pages[i : i + batch_size]
        if batch:
            batches.append(batch)
        if i + batch_size >= len(pages):
            break
    return batches


def merge_overlapping_trees(trees: list[dict]) -> dict:
    """
    Merges mini-trees from overlapping batches.
    Deduplicates sections that appear in overlap zones based on heading similarity.
    """
    if not trees:
        return {}
    if len(trees) == 1:
        return trees[0]

    merged = {
        "title": trees[0].get("title", ""),
        "summary": trees[0].get("summary", ""),
        "keywords": list(set(trees[0].get("keywords", []))),
        "chapters": [],
    }

    all_chapters = []
    for tree in trees:
        all_chapters.extend(tree.get("chapters", []))

    chapters_by_heading = {}
    for chap in all_chapters:
        heading = chap.get("heading")
        if heading not in chapters_by_heading:
            chapters_by_heading[heading] = chap
            chap["keywords"] = list(set(chap.get("keywords", [])))
        else:
            existing_chap = chapters_by_heading[heading]
            existing_sections = {
                s.get("heading"): s for s in existing_chap.get("sections", [])
            }

            for section in chap.get("sections", []):
                sec_heading = section.get("heading")
                if sec_heading not in existing_sections:
                    existing_chap["sections"].append(section)
                else:
                    existing_sec = existing_sections[sec_heading]
                    if "chunks" in section and "chunks" in existing_sec:
                        existing_chunk_indices = {
                            c.get("chunk_index") for c in existing_sec["chunks"]
                        }
                        for chunk in section["chunks"]:
                            if chunk.get("chunk_index") not in existing_chunk_indices:
                                existing_sec["chunks"].append(chunk)

                    if "start_page" in section:
                        existing_sec["start_page"] = min(
                            existing_sec.get("start_page", float("inf")),
                            section["start_page"],
                        )
                        existing_sec["end_page"] = max(
                            existing_sec.get("end_page", 0), section["end_page"]
                        )

            existing_chap["keywords"] = list(
                set(existing_chap["keywords"] + chap.get("keywords", []))
            )

    merged["chapters"] = list(chapters_by_heading.values())
    return merged


def is_large_section(node: dict, pages: list[dict]) -> bool:
    """Returns True if section exceeds MAX_PAGES_PER_NODE or MAX_TOKENS_PER_NODE."""
    start = node.get("start_page", 0)
    end = node.get("end_page", 0)
    if not start or not end:
        return False

    page_count = end - start + 1
    if page_count > settings.MAX_PAGES_PER_NODE:
        return True

    token_count = sum(
        p.get("token_count", 0)
        for p in pages
        if start <= p.get("page_number", 0) <= end
    )
    return token_count > settings.MAX_TOKENS_PER_NODE


def build_subtree(node: dict, pages: list[dict], current_depth: int = 1) -> list[dict]:
    """Recursively builds child nodes for an oversized section."""
    if current_depth >= settings.MAX_RECURSION_DEPTH:
        return []

    start_page = node.get("start_page")
    end_page = node.get("end_page")

    if not start_page or not end_page:
        return []

    section_pages = [
        p for p in pages if start_page <= p.get("page_number", 0) <= end_page
    ]
    if not section_pages:
        return []

    batches = split_pages_with_overlap(
        section_pages, settings.PAGE_BATCH_SIZE, settings.PAGE_BATCH_OVERLAP
    )

    mini_trees = []
    for batch in batches:
        batch_text = [
            f"Page {p['page_number']}:\n{p['text'][:2000]}" for p in batch
        ]  # truncated preview
        mini_tree = _legacy_build_tree(batch_text)
        # Update mini_tree sections to reflect real page numbers within batch
        for chap in mini_tree.get("chapters", []):
            for sec in chap.get("sections", []):
                # Heuristic: assign pages from batch to section
                if batch:
                    sec["start_page"] = batch[0]["page_number"]
                    sec["end_page"] = batch[-1]["page_number"]
        mini_trees.append(mini_tree)

    merged_tree = merge_overlapping_trees(mini_trees)
    child_sections = []
    for chap in merged_tree.get("chapters", []):
        child_sections.extend(chap.get("sections", []))

    for child in child_sections:
        if is_large_section(child, section_pages):
            child["sections"] = build_subtree(child, section_pages, current_depth + 1)

    return child_sections


def build_tree(
    chunks: list[str] | None = None,
    pages: list[dict] | None = None,
    file_path: str | None = None,
) -> tuple[dict, float, str]:
    """Multi-strategy tree builder. Returns (tree, accuracy, strategy_used)."""
    if settings.FORCE_STRATEGY != "auto":
        tree = _run_strategy(settings.FORCE_STRATEGY, chunks, pages)
        return tree, 1.0, settings.FORCE_STRATEGY

    # Strategy 1: TOC with page numbers
    if pages:
        has_toc, toc_indices = detect_toc(pages)
        if has_toc:
            toc_text = extract_toc(pages, toc_indices)
            if has_page_numbers(toc_text):
                tree, accuracy = _strategy_toc_with_pages(toc_text, pages)
                if accuracy >= get_accuracy_threshold():
                    return tree, accuracy, "toc_with_pages"

            # Strategy 2: TOC without page numbers
            tree, accuracy = _strategy_toc_no_pages(toc_text, pages)
            if accuracy >= get_accuracy_threshold():
                return tree, accuracy, "toc_no_pages"

    # Strategy 3: No TOC — AI-generated structure
    tree, accuracy = _strategy_no_toc(chunks, pages)
    return tree, accuracy, "no_toc"


def _run_strategy(strategy: str, chunks: list[str] | None, pages: list[dict] | None) -> dict:
    if strategy == "no_toc":
        tree, _ = _strategy_no_toc(chunks, pages)
        return tree
    # Add other explicit strategy runners if needed
    return _legacy_build_tree(chunks or [])


def _strategy_toc_with_pages(toc_text: str, pages: list[dict]) -> tuple[dict, float]:
    sections = parse_toc_to_sections(toc_text)
    tree = _sections_to_tree(sections, pages)

    result = verify_tree(tree, pages)
    if result["incorrect_nodes"] and result["accuracy"] >= get_accuracy_threshold():
        tree = correct_nodes(tree, pages, result["incorrect_nodes"])
        result = verify_tree(tree, pages)

    _expand_large_sections(tree, pages)
    return tree, result["accuracy"]


def _strategy_toc_no_pages(toc_text: str, pages: list[dict]) -> tuple[dict, float]:
    sections = parse_toc_to_sections(toc_text)
    # Heuristic: distribute sections evenly across pages as starting point for verification/correction
    avg_len = len(pages) // max(1, len(sections))
    for i, sec in enumerate(sections):
        if not sec.get("page"):
            sec["page"] = i * avg_len + 1

    tree = _sections_to_tree(sections, pages)
    result = verify_tree(tree, pages)
    if result["incorrect_nodes"] and result["accuracy"] >= get_accuracy_threshold():
        tree = correct_nodes(tree, pages, result["incorrect_nodes"])
        result = verify_tree(tree, pages)

    _expand_large_sections(tree, pages)
    return tree, result["accuracy"]


def _strategy_no_toc(
    chunks: list[str] | None, pages: list[dict] | None
) -> tuple[dict, float]:
    if pages and settings.USE_PAGE_RANGES:
        batches = split_pages_with_overlap(
            pages, settings.PAGE_BATCH_SIZE, settings.PAGE_BATCH_OVERLAP
        )
        mini_trees = []
        for batch in batches:
            batch_text = [
                f"Page {p['page_number']}:\n{p['text'][:2000]}" for p in batch
            ]
            mini_tree = _legacy_build_tree(batch_text)
            for chap in mini_tree.get("chapters", []):
                for sec in chap.get("sections", []):
                    if batch:
                        sec["start_page"] = batch[0]["page_number"]
                        sec["end_page"] = batch[-1]["page_number"]
            mini_trees.append(mini_tree)
        tree = merge_overlapping_trees(mini_trees)
    else:
        tree = _legacy_build_tree(chunks or [])

    if pages:
        result = verify_tree(tree, pages)
        return tree, result["accuracy"]
    return tree, 1.0


def _sections_to_tree(sections: list[dict], pages: list[dict]) -> dict:
    tree = {
        "title": "Document",
        "summary": "Imported from Table of Contents",
        "keywords": [],
        "chapters": [],
    }
    current_chapter = None
    for sec in sections:
        level = sec.get("level", 1)
        node = {
            "heading": sec.get("title", "Untitled Section"),
            "summary": "Extracted from TOC",
            "keywords": [],
            "start_page": (sec.get("page") or 1),
            "end_page": (sec.get("page") or 1) + 1,  # initial guess
        }
        if level == 1:
            current_chapter = {
                "heading": node["heading"],
                "summary": node["summary"],
                "keywords": node["keywords"],
                "sections": [node],
            }
            tree["chapters"].append(current_chapter)
        else:
            if not current_chapter:
                current_chapter = {
                    "heading": "Chapter 1",
                    "summary": "",
                    "keywords": [],
                    "sections": [],
                }
                tree["chapters"].append(current_chapter)
            current_chapter["sections"].append(node)

    # Adjust end_pages based on next section's start_page
    all_sec_nodes = [s for c in tree["chapters"] for s in c["sections"]]
    for i in range(len(all_sec_nodes) - 1):
        all_sec_nodes[i]["end_page"] = max(
            all_sec_nodes[i]["start_page"], all_sec_nodes[i + 1]["start_page"] - 1
        )
    if all_sec_nodes:
        all_sec_nodes[-1]["end_page"] = len(pages)

    return tree


def _expand_large_sections(tree: dict, pages: list[dict]):
    for chapter in tree.get("chapters", []):
        for section in chapter.get("sections", []):
            if is_large_section(section, pages):
                section["sections"] = build_subtree(section, pages)


def _legacy_build_tree(chunks: list[str]) -> dict:
    """Uses the unified LLM client to form a hierarchical tree from chunks."""
    system_prompt = settings.TREE_SYSTEM_PROMPT.strip()

    # Format chunks to match system prompt examples
    chunk_strings = [
        f'chunk_index {idx}: "{chunk}"\n' for idx, chunk in enumerate(chunks)
    ]
    chunk_text = "".join(chunk_strings)

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chunk_text},
        ]
        raw_content = call_llm(
            "tree", messages, response_format={"type": "json_object"}
        )
        return json.loads(raw_content) if raw_content else {}

    except Exception as e:
        err_msg = str(e).lower()
        if any(
            keyword in err_msg
            for keyword in ["rate", "context limit", "too large", "maximum context"]
        ):
            raise Exception(
                "Document too large: The extracted chunk text exceeded the AI model's token context window. Ingestion failed."
            ) from e
        raise Exception(f"AI Model Connection Error during Tree Building: {e}") from e
