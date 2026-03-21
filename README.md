# Query3AI

> An intelligent, local-first document query system powered by a 3-Agent AI pipeline and Neo4j graph storage.

---

## What Is Query3AI?

Query3AI lets you ingest documents (PDF, DOCX, TXT, MD) and query them in natural language. It does not flatten your documents into a pile of text chunks like standard AI tools. It reads the structure, builds a knowledge graph, and reasons with three specialised AI agents — one to organise, one to filter, one to answer.

```bash
# Install once
pip install query3ai

# Initialize workspace (creates ~/.query3ai with config)
query3ai init

# Start Neo4j
query3ai start-db

# Ingest documents
query3ai ingest report.pdf

# Query with interactive chat
query3ai chat
```

No cloud required. No API keys needed for local models. Runs on a standard laptop.

---

## Installation

### From PyPI (Recommended)

```bash
pip install query3ai
```

### From Source

```bash
git clone https://github.com/vivekvpai/Query3AI.git
cd Query3AI
pip install -e .
```

---

## Quick Start

### 1. Initialize Query3AI

```bash
# Global workspace (default - stores config in ~/.query3ai)
query3ai init

# Or local workspace (creates config in current directory)
query3ai init --local
```

This creates:
- `~/.query3ai/docker-compose.yml` - Neo4j configuration
- `~/.query3ai/.env` - Environment variables
- `~/.query3ai/config.json` - Model configuration

### 2. Start Neo4j

```bash
query3ai start-db
```

Or manually with Docker:
```bash
docker run -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/query3ai \
  neo4j:latest
```

Default connection:
- URI: `bolt://localhost:7687`
- User: `neo4j`
- Password: `query3ai`

### 3. Start Ollama (Optional - for local models)

```bash
# Make sure Ollama is running
ollama serve

# Pull the three agent models
ollama pull phi3.5          # Tree Agent
ollama pull gemma2:2b       # Decision Agent
ollama pull deepseek-r1:7b  # Reasoning Agent
```

### 4. Ingest and Query

```bash
# Ingest a document
query3ai ingest path/to/document.pdf

# Start interactive chat
query3ai chat
```

---

## CLI Commands

| Command | Description |
|---|---|
| `query3ai init` | Initialize workspace in ~/.query3ai |
| `query3ai init --local` | Initialize workspace in current directory |
| `query3ai start-db` | Start Neo4j via docker-compose |
| `query3ai stop-db` | Stop Neo4j |
| `query3ai ingest <file>` | Ingest a PDF, DOCX, TXT, or MD file |
| `query3ai ask "<question>"` | Query all ingested documents |
| `query3ai ask "<question>" --cloud` | Query using cloud models |
| `query3ai list` | List all ingested documents |
| `query3ai inspect <doc_id>` | Inspect a document's tree structure |
| `query3ai delete <doc_id>` | Delete a document and all its nodes |
| `query3ai chat` | Start interactive TUI chat |

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

Edit `~/.query3ai/config.json` to customize models:

```json
{
  "MODEL_PROVIDER": "groq",
  "TREE_MODEL": "phi3.5:3.8b",
  "DECISION_MODEL": "gemma2:2b",
  "REASONING_MODEL": "deepseek-r1:7b"
}
```

| Provider | Description | Privacy | Speed | Cost |
|---|---|---|---|---|
| `ollama_local` | Local Ollama models | ✅ Fully private | ❌ Slow (CPU) | ✅ Free |
| `ollama_cloud` | Cloud Ollama models | ⚠️ External | ✅ Fast | Varies |
| `groq` | Groq API (recommended) | ⚠️ External | ✅ Fastest | Free tier |

For Groq, add your API key to `~/.query3ai/.env`:

```bash
GROQ_API_KEY=your_groq_api_key_here
```

---

## Interactive Chat

Start the TUI chat interface:

```bash
query3ai chat
```

### Slash Commands

| Command | Action |
|---|---|
| `/about` | Learn about Query3AI |
| `/help` | Display all available commands |
| `/ingest <path>` | Ingest a new document |
| `/listdocs` | List all indexed documents |
| `/list` | Show total sections and chunks |
| `/deletedoc` | Remove a document from database |
| `/cleanupdocs` | Delete all documents |
| `/cleanupresorce` | Clean up temporary files |
| `/clear` | Clear terminal |
| `/exit` | Exit chat |

---

## Requirements

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB |
| CPU | 4 cores | 8 cores |
| GPU | Not required | Optional |
| Python | 3.8+ | 3.10+ |
| Storage | 10 GB free | 20 GB free |

---

## Tech Stack

| Layer | Technology |
|---|---|
| CLI | Typer + Rich |
| AI Inference | Ollama, Groq |
| Local Models | phi3.5, gemma2:2b, deepseek-r1:7b |
| Cloud Models | qwen3.5:cloud, kimi-k2.5:cloud, glm-5:cloud |
| Graph Database | Neo4j |
| Document Parsing | PyMuPDF, python-docx |

---

## License

MIT
