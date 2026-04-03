from query3ai.db.neo4j_client import neo4j_client
import datetime
import uuid
from query3ai.config.settings import settings

def store_tree(
    tree: dict,
    doc_id: str,
    chunks: list[str] | None = None,
    pages: list[dict] | None = None,
    strategy: str = "legacy",
    accuracy: float = 1.0,
):
    """Saves tree nodes to Neo4j with relationships Document -> Chapter -> Section -> Chunk."""
    ingested_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc_node_id = f"doc_{uuid.uuid4().hex[:8]}"

    doc_node = neo4j_client.create_node(
        "Document",
        {
            "node_id": doc_node_id,
            "node_type": "document",
            "doc_id": doc_id,
            "parent_id": None,
            "title": tree.get("title", "Untitled Document"),
            "filename": doc_id,
            "summary": tree.get("summary", ""),
            "keywords": tree.get("keywords", []),
            "chunk_count": len(chunks) if chunks else 0,
            "page_count": len(pages) if pages else 0,
            "chapter_count": len(tree.get("chapters", [])),
            "ingest_strategy": strategy,
            "ingest_accuracy": accuracy,
            "ingest_quality": "low" if accuracy < settings.VERIFICATION_ACCURACY_THRESHOLD else "high",
            "ingested_at": ingested_at,
        },
    )

    chapters = tree.get("chapters", [])
    for chap_idx, chapter in enumerate(chapters):
        chap_node_id = f"chap_{uuid.uuid4().hex[:8]}"

        chap_node = neo4j_client.create_node(
            "Chapter",
            {
                "node_id": chap_node_id,
                "node_type": "chapter",
                "doc_id": doc_id,
                "parent_id": doc_node_id,
                "heading": chapter.get("heading", "Untitled Chapter"),
                "summary": chapter.get("summary", ""),
                "keywords": chapter.get("keywords", []),
                "chapter_index": chap_idx,
                "section_count": len(chapter.get("sections", [])),
                "ingested_at": ingested_at,
            },
        )

        neo4j_client.execute_query(
            "MATCH (d:Document {node_id: $doc_id}), (ch:Chapter {node_id: $chap_id}) CREATE (d)-[:HAS_CHAPTER]->(ch)",
            {"doc_id": doc_node_id, "chap_id": chap_node_id},
        )

        sections = chapter.get("sections", [])
        _store_sections(sections, chap_node_id, doc_id, ingested_at, chunks, pages)


def _store_sections(sections, parent_id, doc_id, ingested_at, chunks, pages):
    for sec_idx, section in enumerate(sections):
        sec_node_id = f"sec_{uuid.uuid4().hex[:8]}"
        section_chunks_meta = section.get("chunks", [])

        sec_props = {
            "node_id": sec_node_id,
            "node_type": "section",
            "doc_id": doc_id,
            "parent_id": parent_id,
            "heading": section.get("heading", "Untitled Section"),
            "summary": section.get("summary", ""),
            "keywords": section.get("keywords", []),
            "section_index": sec_idx,
            "ingested_at": ingested_at,
        }

        # Add page range if exists
        if "start_page" in section:
            sec_props["start_page"] = section["start_page"]
            sec_props["end_page"] = section["end_page"]

        sec_node = neo4j_client.create_node("Section", sec_props)

        # Relationship to parent (can be Chapter or Section)
        neo4j_client.execute_query(
            "MATCH (p {node_id: $parent_id}), (s:Section {node_id: $sec_id}) "
            "CREATE (p)-[:HAS_SECTION]->(s)",
            {"parent_id": parent_id, "sec_id": sec_node_id},
        )

        # Handle Chunks (Legacy or Strategy 3 fallback)
        if section_chunks_meta and chunks:
            for chunk_data in section_chunks_meta:
                chunk_idx = chunk_data.get("chunk_index")
                if isinstance(chunk_idx, int) and chunk_idx < len(chunks):
                    _create_chunk_node(
                        sec_node_id, doc_id, chunk_idx, chunks[chunk_idx], chunk_data, ingested_at
                    )
        
        # Handle Page Range Chunks (Strategy 1 & 2)
        elif "start_page" in section and pages:
            start = section["start_page"]
            end = section["end_page"]
            for p in pages:
                p_num = p.get("page_number")
                if p_num and start <= p_num <= end:
                    chunk_data = {
                        "summary": f"Page {p_num} of section {section.get('heading')}",
                        "keywords": []
                    }
                    _create_chunk_node(
                        sec_node_id, doc_id, p_num, p["text"], chunk_data, ingested_at
                    )

        # Handle Recursive Sections
        sub_sections = section.get("sections", [])
        if sub_sections:
            _store_sections(sub_sections, sec_node_id, doc_id, ingested_at, chunks, pages)


def _create_chunk_node(sec_id, doc_id, index, text, meta, ingested_at):
    chk_node_id = f"chk_{uuid.uuid4().hex[:8]}"
    neo4j_client.create_node(
        "Chunk",
        {
            "node_id": chk_node_id,
            "node_type": "chunk",
            "doc_id": doc_id,
            "parent_id": sec_id,
            "chunk_index": index,
            "summary": meta.get("summary", ""),
            "keywords": meta.get("keywords", []),
            "text": text,
            "token_count": len(text.split()),
            "ingested_at": ingested_at,
        },
    )

    neo4j_client.execute_query(
        "MATCH (s:Section {node_id: $sec_id}), (c:Chunk {node_id: $chunk_id}) CREATE (s)-[:HAS_CHUNK]->(c)",
        {"sec_id": sec_id, "chunk_id": chk_node_id},
    )

def get_nodes(doc_id: str) -> dict:
    """Retrieves all nodes for a document as a structured graph dictionary.

    Returns:
        A dict with keys 'document', 'chapters', and 'sections'.
        The 'sections' key is a flat list of all section dicts (used by the LangGraph pipeline).
    """
    query = """
    MATCH (d:Document {doc_id: $doc_id})-[:HAS_CHAPTER]->(ch:Chapter)
    OPTIONAL MATCH (ch)-[:HAS_SECTION]->(s:Section)
    OPTIONAL MATCH (s)-[:HAS_CHUNK]->(c:Chunk)
    RETURN d, ch, s, collect(c) as chunks
    ORDER BY ch.chapter_index, s.section_index
    """
    results = neo4j_client.execute_query(query, {"doc_id": doc_id})

    doc_data = None
    chapters_map: dict[str, dict] = {}
    all_sections: list[dict] = []

    for record in results:
        d = record["d"]
        ch = record["ch"]
        s = record["s"]
        chunks = record["chunks"]

        if not doc_data:
            doc_data = {"doc_id": d["doc_id"], "title": d.get("title", "")}

        chap_id = ch["node_id"]
        if chap_id not in chapters_map:
            chapters_map[chap_id] = {
                "node_id": chap_id,
                "heading": ch.get("heading", ""),
                "summary": ch.get("summary", ""),
                "sections": [],
            }

        if s:
            sec_data = {
                "node_id": s.get("node_id"),
                "heading": s.get("heading", ""),
                "summary": s.get("summary", ""),
                "keywords": s.get("keywords", []),
                "doc_id": d["doc_id"],
                "doc_title": d.get("title", ""),
                "chunks": [
                    {"index": c.get("chunk_index"), "text": c.get("text", "")}
                    for c in chunks
                    if isinstance(c, dict)
                ],
            }
            chapters_map[chap_id]["sections"].append(sec_data)
            all_sections.append(sec_data)

    if doc_data:
        return {
            "document": doc_data,
            "chapters": list(chapters_map.values()),
            "sections": all_sections,
        }
    return {}

def get_all_nodes() -> list[dict]:
    """Retrieves all section nodes across all documents (used by global search)."""
    query = """
    MATCH (d:Document)-[:HAS_CHAPTER]->(ch:Chapter)-[:HAS_SECTION]->(s:Section)
    OPTIONAL MATCH (s)-[:HAS_CHUNK]->(c:Chunk)
    RETURN d, ch, s, collect(c) as chunks
    """
    results = neo4j_client.execute_query(query)
    sections: list[dict] = []
    for record in results:
        d = record["d"]
        ch = record["ch"]
        s = record["s"]
        chunks = record["chunks"]
        sections.append({
            "node_id": s["node_id"],
            "heading": s.get("heading", ""),
            "summary": s.get("summary", ""),
            "keywords": s.get("keywords", []),
            "parent_chapter": ch.get("heading", ""),
            "doc_id": d["doc_id"],
            "doc_title": d.get("title", ""),
            "chunks": [
                {"index": c.get("chunk_index"), "text": c.get("text", "")}
                for c in chunks
                if isinstance(c, dict)
            ],
        })
    return sections

def delete_document(doc_id: str):
    """Deletes a document and its entire subtree (chapters, sections, sub-sections, chunks).

    Uses variable-length path traversal to handle recursive Section → Section relationships.
    Raises ValueError if the document is not found.
    """
    check_query = "MATCH (d:Document {doc_id: $doc_id}) RETURN d LIMIT 1"
    results = neo4j_client.execute_query(check_query, {"doc_id": doc_id})

    if not results:
        raise ValueError(f"Document '{doc_id}' was not found in the database. Please check the ID and try again.")

    # Variable-length path catches recursive sub-sections that the old fixed-depth query missed
    delete_query = """
    MATCH (d:Document {doc_id: $doc_id})
    OPTIONAL MATCH (d)-[*]->(child)
    DETACH DELETE d, child
    """
    neo4j_client.execute_query(delete_query, {"doc_id": doc_id})
