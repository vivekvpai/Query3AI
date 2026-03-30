from query3ai.db.neo4j_client import neo4j_client
from typing import List
import datetime
import uuid

def store_tree(tree: dict, doc_id: str, chunks: List[str]):
    """Saves tree nodes to Neo4j with relationships Document -> Chapter -> Section -> Chunk."""
    ingested_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_hex = str(uuid.uuid4().hex)
    doc_node_id = f"doc_{full_hex[:8]}"

    doc_node = neo4j_client.create_node("Document", {
        "node_id": doc_node_id,
        "node_type": "document",
        "doc_id": doc_id,
        "parent_id": None,
        "title": tree.get("title", "Untitled Document"),
        "filename": doc_id,
        "summary": tree.get("summary", ""),
        "keywords": tree.get("keywords", []),
        "chunk_count": len(chunks),
        "chapter_count": len(tree.get("chapters", [])),
        "ingested_at": ingested_at
    })
    
    chapters = tree.get("chapters", [])
    for chap_idx, chapter in enumerate(chapters):
        chap_hex = str(uuid.uuid4().hex)
        chap_node_id = f"chap_{chap_hex[:8]}"
        
        chap_node = neo4j_client.create_node("Chapter", {
            "node_id": chap_node_id,
            "node_type": "chapter",
            "doc_id": doc_id,
            "parent_id": doc_node_id,
            "heading": chapter.get("heading", "Untitled Chapter"),
            "summary": chapter.get("summary", ""),
            "keywords": chapter.get("keywords", []),
            "chapter_index": chap_idx,
            "section_count": len(chapter.get("sections", [])),
            "ingested_at": ingested_at
        })
        
        neo4j_client.execute_query(
            "MATCH (d:Document {node_id: $doc_id}), (ch:Chapter {node_id: $chap_id}) CREATE (d)-[:HAS_CHAPTER]->(ch)",
            {"doc_id": doc_node_id, "chap_id": chap_node_id}
        )
        
        sections = chapter.get("sections", [])
        for sec_idx, section in enumerate(sections):
            sec_hex = str(uuid.uuid4().hex)
            sec_node_id = f"sec_{sec_hex[:8]}"
            section_chunks = section.get("chunks", [])
            
            sec_node = neo4j_client.create_node("Section", {
                "node_id": sec_node_id,
                "node_type": "section",
                "doc_id": doc_id,
                "parent_id": chap_node_id,
                "heading": section.get("heading", "Untitled Section"),
                "summary": section.get("summary", ""),
                "keywords": section.get("keywords", []),
                "section_index": sec_idx,
                "chunk_count": len(section_chunks),
                "ingested_at": ingested_at
            })
            
            neo4j_client.execute_query(
                "MATCH (ch:Chapter {node_id: $chap_id}), (s:Section {node_id: $sec_id}) CREATE (ch)-[:HAS_SECTION]->(s)",
                {"chap_id": chap_node_id, "sec_id": sec_node_id}
            )
            
            for chunk_data in section_chunks:
                chunk_idx = chunk_data.get("chunk_index")
                if isinstance(chunk_idx, int) and chunk_idx < len(chunks):
                    chk_hex = str(uuid.uuid4().hex)
                    chk_node_id = f"chk_{chk_hex[:8]}"
                    text = chunks[chunk_idx]
                    chunk_node = neo4j_client.create_node("Chunk", {
                        "node_id": chk_node_id,
                        "node_type": "chunk",
                        "doc_id": doc_id,
                        "parent_id": sec_node_id,
                        "chunk_index": chunk_idx,
                        "summary": chunk_data.get("summary", ""),
                        "keywords": chunk_data.get("keywords", []),
                        "text": text,
                        "token_count": len(text.split()),
                        "ingested_at": ingested_at
                    })
                    
                    neo4j_client.execute_query(
                        "MATCH (s:Section {node_id: $sec_id}), (c:Chunk {node_id: $chunk_id}) CREATE (s)-[:HAS_CHUNK]->(c)",
                        {"sec_id": sec_node_id, "chunk_id": chk_node_id}
                    )

def get_nodes(doc_id: str) -> dict:
    """Retrieves all nodes for a document as a structured graph dictionary."""
    query = """
    MATCH (d:Document {doc_id: $doc_id})-[:HAS_CHAPTER]->(ch:Chapter)
    OPTIONAL MATCH (ch)-[:HAS_SECTION]->(s:Section)
    OPTIONAL MATCH (s)-[:HAS_CHUNK]->(c:Chunk)
    RETURN d, ch, s, collect(c) as chunks
    ORDER BY ch.chapter_index, s.section_index
    """
    results = neo4j_client.execute_query(query, {"doc_id": doc_id})
    
    doc_data = None
    chapters_map = {}
    
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
                "sections": []
            }
            
        if s:
            sec_data = {
                "node_id": s.get("node_id"),
                "heading": s.get("heading", ""),
                "summary": s.get("summary", ""),
                "doc_id": d["doc_id"],
                "doc_title": d.get("title", ""),
                "chunks": [{"index": c.get("chunk_index"), "text": c.get("text", "")} for c in chunks if getattr(c, 'get', None)]
            }
            chapters_map[chap_id]["sections"].append(sec_data)
        
    if doc_data:
        return {
            "document": doc_data, 
            "chapters": list(chapters_map.values())
        }
    return {}

def get_all_nodes() -> list[dict]:
    """Retrieves all section nodes across all documents. (Used by reasoning API)"""
    query = """
    MATCH (d:Document)-[:HAS_CHAPTER]->(ch:Chapter)-[:HAS_SECTION]->(s:Section)
    OPTIONAL MATCH (s)-[:HAS_CHUNK]->(c:Chunk)
    RETURN d, ch, s, collect(c) as chunks
    """
    results = neo4j_client.execute_query(query)
    sections = []
    for record in results:
        d = record["d"]
        ch = record["ch"]
        s = record["s"]
        chunks = record["chunks"]
        sections.append({
            "node_id": s["node_id"],
            "heading": s.get("heading", ""),
            "summary": s.get("summary", ""),
            "parent_chapter": ch.get("heading", ""),
            "doc_id": d["doc_id"],
            "doc_title": d.get("title", ""),
            "chunks": [{"index": c.get("chunk_index"), "text": c.get("text", "")} for c in chunks if getattr(c, 'get', None)]
        })
    return sections

def delete_document(doc_id: str):
    """Deletes a document and its chapter / section / chunk tree. Raises ValueError if not found."""
    check_query = "MATCH (d:Document {doc_id: $doc_id}) RETURN d LIMIT 1"
    results = neo4j_client.execute_query(check_query, {"doc_id": doc_id})
    
    if not results:
        raise ValueError(f"Document '{doc_id}' was not found in the database. Please check the ID and try again.")
    
    delete_query = """
    MATCH (d:Document {doc_id: $doc_id})
    OPTIONAL MATCH (d)-[:HAS_CHAPTER]->(ch:Chapter)
    OPTIONAL MATCH (ch)-[:HAS_SECTION]->(s:Section)
    OPTIONAL MATCH (s)-[:HAS_CHUNK]->(c:Chunk)
    DETACH DELETE d, ch, s, c
    """
    neo4j_client.execute_query(delete_query, {"doc_id": doc_id})
