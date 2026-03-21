# Architecture

Query3AI is built around a **3-Agent pipeline** backed by a Neo4j graph database. Each agent is a specialised language model with a single, well-defined responsibility. Every agent is fully configurable — you can plug in any Ollama-compatible model that fits your hardware and quality requirements.

---

## High-Level Overview

```
                        ┌─────────────────────────────────────────────┐
                        │              USER (CLI / TUI)               │
                        └────────────────────┬────────────────────────┘
                                             │
                        ┌────────────────────▼────────────────────────┐
                        │                 main.py                     │
                        │           (Typer CLI Router)                │
                        └──────┬─────────────────────────┬────────────┘
                               │                         │
                    ┌──────────▼──────────┐   ┌──────────▼──────────┐
                    │   INGEST PIPELINE   │   │   QUERY PIPELINE    │
                    └──────────┬──────────┘   └──────────┬──────────┘
                               │                         │
          ┌────────────────────▼──────────┐              │
          │       Document Service        │              │
          │  extract_text() + chunk()     │              │
          └────────────────────┬──────────┘              │
                               │                         │
          ┌────────────────────▼──────────┐              │
          │    Agent 1 — Tree AI          │              │
          │    (Configurable Model)       │              │
          │    Builds hierarchical tree   │              │
          └────────────────────┬──────────┘              │
                               │                         │
          ┌────────────────────▼──────────┐   ┌──────────▼──────────┐
          │    Graph Service              │   │   Graph Service      │
          │    store_tree() → Neo4j       │   │   get_nodes()        │
          └───────────────────────────────┘   └──────────┬──────────┘
                                                         │
                                            ┌────────────▼──────────┐
                                            │  Agent 2 — Decision   │
                                            │  (Configurable Model) │
                                            │  Filters by relevance │
                                            └────────────┬──────────┘
                                                         │
                                            ┌────────────▼──────────┐
                                            │  Agent 3 — Reasoning  │
                                            │  (Configurable Model) │
                                            │  Generates answer     │
                                            └────────────┬──────────┘
                                                         │
                                            ┌────────────▼──────────┐
                                            │     CLI Output        │
                                            │  Answer + Sources     │
                                            └───────────────────────┘
```

---

## The Two Pipelines

### Ingest Pipeline

Triggered by: `python main.py ingest <file>`

```
File (.pdf / .docx / .txt)
        │
        ▼
DocumentService.extract_text()
        │  Raw text string
        ▼
DocumentService.chunk_text()
        │  List of ~500-word chunks
        ▼
Agent 1 — Tree AI (your configured model)
        │  Structured JSON tree
        │  {title, summary, keywords, sections[{heading, summary, keywords, chunks[...]}]}
        ▼
GraphService.store_tree()
        │
        ▼
Neo4j Graph Database
  (Document) ──HAS_SECTION──▶ (Section) ──HAS_CHUNK──▶ (Chunk)
```

### Query Pipeline

Triggered by: `python main.py ask "<question>"`

```
User Question
        │
        ▼
GraphService.get_nodes()
        │  All Section + Chunk nodes from Neo4j
        ▼
Agent 2 — Decision AI (your configured model)
        │  Reads section heading + summary only (not full text)
        │  Returns YES/NO per section
        ▼
Filtered relevant sections + their chunks
        │
        ▼
Agent 3 — Reasoning AI (your configured model)
        │  Receives only relevant context
        │  Reasons and generates answer
        ▼
CLI Output: Answer + Source sections
```

---

## The Three Agents

All three agents are independently configurable. You set the model for each agent in `config/settings.py`. Any model available in your local Ollama instance or any Ollama-compatible cloud model can be used.

---

### Agent 1 — Tree AI

| Property | Detail |
|---|---|
| **Configured via** | `TREE_MODEL` and `TREE_MODEL_CLOUD` in `settings.py` |
| **Trigger** | Once per document, at ingest time |
| **Input** | All raw text chunks from the document |
| **Output** | Structured JSON tree (title, sections, chunk mappings) |
| **Role** | Converts a flat list of chunks into a meaningful hierarchy |

The Tree AI is the most important agent in the system. It determines how well the document is understood. It reads all chunks, identifies logical groupings, assigns headings and summaries, and maps each chunk to its section. A good tree means fast, accurate queries later.

**What to look for in a model for this agent:**
- Must support structured JSON output reliably
- Needs a large context window — it receives the entire document's chunks at once
- The larger the context window of your chosen model, the larger the documents it can handle
- Strong instruction-following produces cleaner, more consistent trees

> **Document size ceiling:** This agent is the only size-sensitive step in the pipeline. The maximum document size Query3AI can handle is directly determined by the context window of the model you configure here. Choose accordingly.

---

### Agent 2 — Decision AI

| Property | Detail |
|---|---|
| **Configured via** | `DECISION_MODEL` and `DECISION_MODEL_CLOUD` in `settings.py` |
| **Trigger** | Every query, once per section |
| **Input** | Section heading + summary + user question |
| **Output** | `YES` or `NO` |
| **Role** | Guards the Reasoning AI from irrelevant context |

The Decision AI never reads the full chunk text. It only reads the section heading and the AI-generated summary — both very short. This means even a small, fast model can handle this role effectively.

**What to look for in a model for this agent:**
- Must reliably follow the YES/NO output instruction without extra text
- Speed matters more than reasoning depth — it runs once per section per query
- A smaller, faster model is often the better choice here
- Context window requirements are low — inputs are always short

The binary YES/NO output is intentional. Asking for a relevance score introduces variance and requires extra parsing. YES/NO is deterministic and token-efficient.

---

### Agent 3 — Reasoning AI

| Property | Detail |
|---|---|
| **Configured via** | `REASONING_MODEL` and `REASONING_MODEL_CLOUD` in `settings.py` |
| **Trigger** | Every query, once |
| **Input** | Filtered relevant chunks + user question |
| **Output** | Natural language answer |
| **Role** | Reads only pre-filtered, relevant content and generates the final answer |

The Reasoning AI is the quality ceiling of the system. Because Agents 1 and 2 do the structural and relevance work upfront, Agent 3 works with a clean, focused context — not the entire document.

**What to look for in a model for this agent:**
- Reasoning capability matters most — models with chain-of-thought or thinking mode produce more accurate, grounded answers
- Must follow the instruction to answer only from provided context (to avoid hallucination)
- Context window needs to hold the filtered chunks — but since Decision AI pre-filters, this is rarely a bottleneck
- This is the best place to invest in a more capable model if answer quality is the priority

---

## Model Configuration

All model settings live in `config/settings.py`. Query3AI supports **three model providers** — switch between them by changing a single line.

### The Three Providers

| Provider | Value | Description |
|---|---|---|
| **Ollama Local** | `"ollama_local"` | Runs on your machine via Ollama. Fully private, no internet needed |
| **Ollama Cloud** | `"ollama_cloud"` | Ollama-hosted cloud models. Faster, higher quality, requires internet |
| **Groq** | `"groq"` | Groq API inference. Fastest option, requires a Groq API key |

Set your active provider with one line:

```python
MODEL_PROVIDER: str = "ollama_local"  # "ollama_local" | "ollama_cloud" | "groq"
```

Query3AI automatically routes all three agents to the correct models for that provider — no other changes needed.

---

### Model Slots

Each agent has an independent model slot per provider. You can change any of them to any compatible model:

```python
# Ollama Local — runs on your machine
TREE_MODEL      = "any-ollama-local-model"
DECISION_MODEL  = "any-ollama-local-model"
REASONING_MODEL = "any-ollama-local-model"

# Ollama Cloud — hosted cloud inference via Ollama
CLOUD_TREE_MODEL      = "any-ollama-cloud-model"
CLOUD_DECISION_MODEL  = "any-ollama-cloud-model"
CLOUD_REASONING_MODEL = "any-ollama-cloud-model"

# Groq — API-based inference (requires GROQ_API_KEY)
GROQ_TREE_MODEL      = "any-groq-compatible-model"
GROQ_DECISION_MODEL  = "any-groq-compatible-model"
GROQ_REASONING_MODEL = "any-groq-compatible-model"
```

---

### Environment Variables

Sensitive values are loaded from a `.env` file and never hardcoded:

```bash
# .env
GROQ_API_KEY=your_groq_api_key_here
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
QUERY3AI_CHUNK_SIZE=500   # optional, default is 500
```

---

### How Provider Routing Works

The `settings.py` exposes three helper methods that return the active model for each agent based on the current `MODEL_PROVIDER` value:

```
get_active_tree_model()      → returns correct model for Agent 1
get_active_decision_model()  → returns correct model for Agent 2
get_active_reasoning_model() → returns correct model for Agent 3
```

Every service calls these methods — so swapping providers is always a one-line change in `MODEL_PROVIDER`.

---

### Choosing the Right Model for Each Agent

Regardless of which provider you use, the same priorities apply:

| Agent | What Matters Most | What Matters Least |
|---|---|---|
| **Tree AI** | JSON output reliability, large context window | Speed |
| **Decision AI** | Speed, strict YES/NO instruction following | Reasoning depth |
| **Reasoning AI** | Reasoning quality, instruction following | Speed |

### Provider Trade-offs

| | Ollama Local | Ollama Cloud | Groq |
|---|---|---|---|
| **Privacy** | ✅ Fully private | ⚠️ External server | ⚠️ External server |
| **Speed** | ❌ Slow (CPU-bound) | ✅ Fast | ✅ Fastest |
| **Cost** | ✅ Free | Varies | Free tier available |
| **Offline use** | ✅ Yes | ❌ No | ❌ No |
| **API key required** | ❌ No | ❌ No | ✅ Yes (`GROQ_API_KEY`) |
| **Model quality** | Depends on size | Generally high | Generally high |

---

## The Graph Database Schema

Every document is stored as a three-level node hierarchy in Neo4j:

```
(Document)
    │
    ├──[HAS_SECTION]──▶ (Section 1)
    │                        │
    │                        ├──[HAS_CHUNK]──▶ (Chunk 0)
    │                        └──[HAS_CHUNK]──▶ (Chunk 1)
    │
    └──[HAS_SECTION]──▶ (Section 2)
                             │
                             └──[HAS_CHUNK]──▶ (Chunk 2)
```

### Node Properties

Every node at every level carries these fields:

```
node_id       — unique identifier for this specific node
node_type     — "document" | "section" | "chunk"
doc_id        — parent document ID (present on ALL nodes)
parent_id     — immediate parent's node_id
summary       — 1-2 sentence AI-generated description
keywords      — list of 5-8 key terms
ingested_at   — timestamp
```

Additional per type:

**Document:** `title`, `filename`, `chunk_count`, `section_count`

**Section:** `heading`, `section_index`, `chunk_count`

**Chunk:** `chunk_index`, `text`, `token_count`

### Why Graph, Not Vector?

| | Vector DB (standard RAG) | Neo4j Graph (Query3AI) |
|---|---|---|
| **Structure** | Flat — all chunks equal | Hierarchical — Document → Section → Chunk |
| **Traversal** | Similarity search only | Relationship traversal (parent, children, siblings) |
| **Filtering** | Similarity threshold | Decision AI: semantic YES/NO per section |
| **Explainability** | "These chunks matched" | "These sections were relevant, here are their chunks" |
| **Deletion** | Delete by vector index | Cascade delete via graph relationships |
| **Multi-doc** | All chunks in one pool | Documents isolated, relationships explicit |

---

## Project Structure

```
query3ai/
│
├── cli/
│   └── commands.py          # Typer CLI commands (ingest, ask, list, inspect, delete)
│
├── services/
│   ├── document_service.py  # extract_text(), chunk_text()
│   ├── tree_service.py      # build_tree() — Agent 1
│   ├── graph_service.py     # store_tree(), get_nodes()
│   ├── decision_service.py  # filter_nodes() — Agent 2
│   └── reasoning_service.py # answer() — Agent 3
│
├── db/
│   └── neo4j_client.py      # Neo4j connection and Cypher queries
│
├── models/
│   └── schemas.py           # Pydantic models for node types
│
├── utils/
│   ├── file_handler.py      # File type detection
│   └── id_generator.py      # node_id / section_id / chunk_id generators
│
├── config/
│   └── settings.py          # All config: models, Neo4j URI, chunk size
│
└── main.py                  # Entry point
```

---

## Hardware Requirements

Requirements vary based on the models you choose. Larger models need more RAM and run slower on CPU.

| Component | Minimum | Recommended |
|---|---|---|
| **RAM** | 8 GB | 16 GB |
| **CPU** | 4 cores | 8 cores |
| **GPU** | Not required | Optional (significantly speeds up inference) |
| **Storage** | 10 GB free | 20 GB+ free (depends on model sizes) |
| **OS** | Windows 10 / macOS / Linux | Any |

### General RAM Guidelines by Model Size

| Model Size | Approx. RAM Usage | Approx. Speed (CPU, i5-class) |
|---|---|---|
| ~2B parameters | 1.5 – 2 GB | Fast (20–40 sec) |
| ~4B parameters | 3 – 4 GB | Moderate (1–2 min) |
| ~7B parameters | 4 – 5 GB | Moderate (3–5 min) |
| ~14B parameters | 8 – 10 GB | Slow (8–15 min) |
| ~30B+ parameters | 16 GB+ | Very slow on CPU — cloud recommended |

> The three agents run sequentially, not simultaneously. You need enough RAM for the largest single model you configure — not all three combined.
