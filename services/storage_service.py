import uuid

# In-memory storage for chunks. Will be replaced by Neo4j later.
_storage = []

def save_chunks(chunks: list[str], source_file: str):
    """Saves a list of chunk texts along with their source file."""
    for chunk in chunks:
        _storage.append({
            "id": str(uuid.uuid4()),
            "text": chunk,
            "source_file": source_file
        })

def get_all_chunks() -> list[dict]:
    """Retrieves all stored chunks."""
    return _storage
