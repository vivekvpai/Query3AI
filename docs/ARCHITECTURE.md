# Architecture

Query3AI is built around a **3-Agent pipeline** backed by a Neo4j graph database. Each agent is a specialised language model with a single, well-defined responsibility.

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
          │    Model: phi3.5 / qwen3.5    │              │
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
                                            │  Model: gemma2:2b     │
                                            │  Filters by relevance │
                                            └────────────┬──────────┘
                                                         │
                                            ┌────────────▼──────────┐
                                            │  Agent 3 — Reasoning  │
                                            │  Model: deepseek-r1   │
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
Agent 1 — Tree AI (phi3.5)
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
Agent 2 — Decision AI (gemma2:2b)
        │  Reads section heading + summary only (not full text)
        │  Returns YES/NO per section
        ▼
Filtered relevant sections + their chunks
        │
        ▼
Agent 3 — Reasoning AI (deepseek-r1:7b)
        │  Receives only relevant context
        │  Reasons and generates answer
        ▼
CLI Output: Answer + Source sections
```

---

## The Three Agents

### Agent 1 — Tree AI

| Property | Value |
|---|---|
| **Local Model** | `phi3.5` |
| **Cloud Model** | `qwen3.5:cloud` |
| **Trigger** | Once per document, at ingest time |
| **Input** | Raw text chunks |
| **Output** | Structured JSON tree (title, sections, chunk mappings) |
| **Role** | Converts a flat list of chunks into a meaningful hierarchy |

The Tree AI is the most important agent in the system. It determines how well the document is understood. It reads all chunks, identifies logical groupings, assigns headings and summaries, and maps each chunk to its section. A good tree = fast, accurate queries later.

**Why phi3.5 locally?** Microsoft's Phi models are disproportionately strong at structured JSON output for their size. At ~4GB RAM, phi3.5 reliably returns valid JSON trees even on CPU-only hardware.

---

### Agent 2 — Decision AI

| Property | Value |
|---|---|
| **Local Model** | `gemma2:2b` |
| **Cloud Model** | `kimi-k2.5:cloud` |
| **Trigger** | Every query, once per section |
| **Input** | Section heading + summary + user question |
| **Output** | `YES` or `NO` |
| **Role** | Guards the Reasoning AI from irrelevant context |

The Decision AI never reads the full chunk text. It only reads the section heading and AI-generated summary — both very short. This makes it extremely fast and cheap. On an i5 CPU, gemma2:2b evaluates a section's relevance in under 40 seconds.

The binary YES/NO output is intentional. Asking for a relevance score (0-10) introduces variance and requires a parsing step. YES/NO is deterministic and token-efficient.

---

### Agent 3 — Reasoning AI

| Property | Value |
|---|---|
| **Local Model** | `deepseek-r1:7b` |
| **Cloud Model** | `glm-5:cloud` |
| **Trigger** | Every query, once |
| **Input** | Filtered relevant chunks + user question |
| **Output** | Natural language answer |
| **Role** | Reads only pre-filtered, relevant content and generates the final answer |

The Reasoning AI is the quality ceiling of the system. Because Agents 1 and 2 do the structural and relevance work upfront, Agent 3 works with a clean, focused context. This is why a 7B model can outperform a much larger model given unstructured context.

DeepSeek-R1 was chosen for its native chain-of-thought reasoning — it thinks before it answers, which produces more accurate, grounded responses especially on complex document questions.

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

## Model Configuration

All model settings live in `config/settings.py`:

```python
# Local models (default)
TREE_MODEL      = "phi3.5"
DECISION_MODEL  = "gemma2:2b"
REASONING_MODEL = "deepseek-r1:7b"

# Cloud models (activated via --cloud flag or USE_CLOUD = True)
TREE_MODEL_CLOUD      = "qwen3.5:cloud"
DECISION_MODEL_CLOUD  = "kimi-k2.5:cloud"
REASONING_MODEL_CLOUD = "glm-5:cloud"

USE_CLOUD = False
```

Switching between local and cloud requires no code changes — toggle `USE_CLOUD` or pass `--cloud` at query time.

---

## Hardware Requirements

### Minimum (Local, CPU-only)

| Component | Minimum | Recommended |
|---|---|---|
| **RAM** | 8 GB | 16 GB |
| **CPU** | 4 cores | 8 cores |
| **GPU** | Not required | Optional (speeds up inference) |
| **Storage** | 10 GB free | 20 GB free |
| **OS** | Windows 10 / macOS / Linux | Any |

### Local Model RAM Usage

| Model | Agent | RAM | Approx. Response Time (i5 CPU) |
|---|---|---|---|
| `gemma2:2b` | Decision | ~1.7 GB | 20–40 sec |
| `phi3.5` | Tree | ~4 GB | 1–2 min |
| `deepseek-r1:7b` | Reasoning | ~4.5 GB | 3–5 min |

> All three models together use ~10 GB peak RAM. On a 16 GB system this is comfortable.
