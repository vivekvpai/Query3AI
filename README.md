# Query3AI

> An intelligent, local-first document query system powered by a 3-Agent AI pipeline and Neo4j graph storage.

---

## What Is Query3AI?

Query3AI lets you ingest documents (PDF, DOCX, TXT) and query them in natural language through a CLI. It does not flatten your documents into a pile of text chunks like standard AI tools. It reads the structure, builds a knowledge graph, and reasons with three specialised AI agents — one to organise, one to filter, one to answer.

```bash
python main.py ingest report.pdf
python main.py ask "What were the key findings in section 3?"

# Answer:
# The key findings relate to...
#
# Sources:
# - Section 3: Market Analysis Summary
```

No cloud required. No API keys. Runs on a standard laptop.

---

## Documentation

| Document | Description |
|---|---|
| [Why Query3AI?](docs/WHY_QUERY3AI.md) | The problem it solves, the philosophy behind it, and what it is not |
| [Architecture](docs/ARCHITECTURE.md) | The 3-Agent pipeline, graph schema, project structure, and model details |
| [Use Cases & Case Studies](docs/USE_CASES.md) | Real-world scenarios: legal review, resume screening, developer docs, research |
| [Advantages & Comparisons](docs/ADVANTAGES.md) | Honest pros/cons and comparison vs RAG, ChatGPT, LlamaIndex |

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Start Neo4j

Run Neo4j locally (Desktop or Docker):

```bash
docker run -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest
```

Default connection in `config/settings.py`:
- URI: `bolt://localhost:7687`
- User: `neo4j`
- Password: `password`

### 3. Start Ollama and pull models

```bash
# Make sure Ollama is running
ollama serve

# Pull the three agent models
ollama pull phi3.5          # Tree Agent
ollama pull gemma2:2b       # Decision Agent
ollama pull deepseek-r1:7b  # Reasoning Agent
```

### 4. Ingest and query

```bash
python main.py ingest path/to/document.pdf
python main.py ask "Your question here"
```

---

## CLI Commands

| Command | Description |
|---|---|
| `python main.py ingest <file>` | Ingest a PDF, DOCX, or TXT file |
| `python main.py ask "<question>"` | Query all ingested documents |
| `python main.py ask "<question>" --cloud` | Query using cloud models |
| `python main.py list` | List all ingested documents |
| `python main.py inspect <doc_id>` | Inspect a document's tree structure |
| `python main.py delete <doc_id>` | Delete a document and all its nodes |

---

## The 3-Agent Pipeline

```
Document
    │
    ▼
[Agent 1 — Tree AI]      phi3.5 / qwen3.5:cloud
Builds hierarchical tree: Document → Sections → Chunks
    │
    ▼
Neo4j Graph Database
    │
    ▼
[Agent 2 — Decision AI]  gemma2:2b / kimi-k2.5:cloud
Filters sections by relevance to the query (YES/NO)
    │
    ▼
[Agent 3 — Reasoning AI] deepseek-r1:7b / glm-5:cloud
Generates final answer from filtered context only
    │
    ▼
Answer + Source Sections
```

---

## Model Configuration

All models are configured in `config/settings.py`:

```python
# Local models (default)
TREE_MODEL      = "phi3.5"
DECISION_MODEL  = "gemma2:2b"
REASONING_MODEL = "deepseek-r1:7b"

# Cloud models (--cloud flag or USE_CLOUD = True)
TREE_MODEL_CLOUD      = "qwen3.5:cloud"
DECISION_MODEL_CLOUD  = "kimi-k2.5:cloud"
REASONING_MODEL_CLOUD = "glm-5:cloud"
```

---

## TUI / Chat Interface

For a conversational interface instead of raw CLI commands:

```bash
# Windows
start_chat.bat

# macOS / Linux
./start_chat.sh
```

### Slash Commands

| Command | Action |
|---|---|
| `/about` | Learn about Query3AI Interactive Chat |
| `/help` | Display usage and all available commands |
| `/ingest` | Ingest a new document from a specified file path |
| `/listdocs` | List all indexed documents |
| `/list` | List available assets |
| `/deletedoc` | Remove a specific document from the database |
| `/cleanupdocs` | Delete all documents from the database |
| `/cleanupresorce` | Clean up temporary logs and JSON files |
| `/clear` | Clear chat history |
| `/exit` | Exit the interactive session |

---

## Requirements

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB |
| CPU | 4 cores | 8 cores |
| GPU | Not required | Optional |
| Python | 3.10+ | 3.11+ |
| Storage | 10 GB free | 20 GB free |

---

## Tech Stack

| Layer | Technology |
|---|---|
| CLI | Typer + Rich |
| AI Inference | Ollama |
| Local Models | phi3.5, gemma2:2b, deepseek-r1:7b |
| Cloud Models | qwen3.5:cloud, kimi-k2.5:cloud, glm-5:cloud |
| Graph Database | Neo4j |
| Document Parsing | PyMuPDF, python-docx, pandas |
| Data Validation | Pydantic |

---

## License

MIT
