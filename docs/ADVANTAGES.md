# Advantages, Disadvantages & Comparisons

An honest assessment of what Query3AI does well, where it struggles, and how it compares to alternative approaches.

---

## Advantages

### 1. Fully Local and Private
Query3AI runs entirely on your machine. No document content is ever sent to an external server unless you explicitly enable the `--cloud` flag. This makes it suitable for sensitive documents — legal contracts, medical records, internal financials, proprietary research — where cloud AI services are not an option.

### 2. Persistent Document Memory
Unlike ChatGPT file uploads or Claude's document analysis, Query3AI remembers every document you ingest. Ingest a file once, query it hundreds of times across multiple sessions. The knowledge graph in Neo4j persists until you explicitly delete it.

### 3. Structured Reasoning, Not Just Similarity
Standard RAG treats all chunks equally and retrieves by vector similarity. Query3AI builds a hierarchical tree of your document and reasons about structure. This produces answers that are more contextually accurate, especially in documents where the location of information matters (e.g. "what does Section 4 say about X?").

### 4. Source Traceability
Every answer comes with the section it was drawn from. You can verify answers, audit the reasoning, and build trust in the system — a property most black-box AI tools lack.

### 5. Specialised Agents Outperform Generalists
Using three small, specialised models (phi3.5 for structure, gemma2:2b for filtering, deepseek-r1:7b for reasoning) each tuned to a specific task consistently outperforms feeding everything into one large general model. Each agent does less, but does it better.

### 6. Hardware Accessible
The full local pipeline runs on a standard laptop with 16GB RAM and no GPU. This is a deliberate design choice — most AI tooling assumes powerful hardware. Query3AI proves that a well-architected pipeline beats raw compute.

### 7. Cloud Escape Hatch
When local inference is too slow or you need higher quality, every agent has a cloud equivalent accessible via `--cloud`. The switch is seamless and requires no code changes.

### 8. Programmable and Extensible
Query3AI is a CLI tool backed by modular Python services. Every component is independently replaceable — swap the database, change the models, add new file type support, or build a web API on top. It is a foundation, not a finished product.

---

## Disadvantages

### 1. Slow Local Inference
On CPU-only hardware (no GPU), inference is slow. Ingesting a 20-page document may take 5–15 minutes. A query response takes 3–8 minutes end-to-end. This is a fundamental hardware constraint, not a code issue.

**Mitigation:** Use `--cloud` for faster responses during development or production. Cloud models respond in seconds.

### 2. Tree Quality Depends on Model Quality
The entire system's accuracy depends heavily on how well the Tree AI structures the document at ingest time. If phi3.5 produces a poor tree (wrong section groupings, weak summaries), subsequent agents work with flawed foundations.

**Mitigation:** Use `qwen3.5:cloud` as the Tree AI for important documents. The cloud model produces significantly better trees.

### 3. Document Size Is Bounded by Your Tree AI Model

This is the most important limitation to understand. Query3AI's ability to handle large documents **entirely depends on which Tree AI model you are using**. The Tree AI receives all document chunks in a single prompt — if that exceeds the model's context window, the ingestion will either fail or silently produce an incomplete tree.

| Tree AI Model | Context Window | Approx. Max Document Size | Safe For |
|---|---|---|---|
| `phi3.5` (local, default) | 128K tokens | ~150–180 pages | Most business documents |
| `qwen3.5:cloud` (cloud) | 32K tokens | ~35–40 pages | Short to medium documents |

**The counterintuitive reality:** your local model (`phi3.5`) actually handles *larger* documents than the cloud Tree AI (`qwen3.5`) because it has a 4x bigger context window. For very large documents, local is the better choice.

**Mitigation (current):** Split very large documents into logical parts (e.g. by chapter) and ingest each part separately.

**Mitigation (planned):** Batched tree building — the Tree AI will process chunks in batches and merge the resulting trees. This will remove the size ceiling entirely and is on the roadmap.

> The Decision AI and Reasoning AI are **not** affected by document size — Decision AI only reads short summaries, and Reasoning AI only receives pre-filtered chunks. Size is exclusively a Tree AI concern.

### 3. No OCR Support
Query3AI cannot read scanned PDFs or image-based documents. It requires documents with a machine-readable text layer. A scanned contract or photographed whiteboard will produce empty or garbage output.

**Mitigation:** Pre-process scanned documents with an OCR tool (e.g. Tesseract) before ingesting.

### 4. Neo4j Dependency
The system requires a running Neo4j instance. This adds infrastructure complexity compared to tools that use a simple file-based vector store. Setting up Neo4j correctly (credentials, URI, version) creates friction for new users.

**Mitigation:** Docker makes this one command: `docker run -p 7687:7687 neo4j`.

### 5. No Real-Time Updates
Documents are static snapshots. If a contract is amended or a report is updated, the old version must be deleted and the new version re-ingested. There is no automatic sync or update mechanism.

### 6. Single Language (English-Centric)
The local models (phi3.5, gemma2:2b, deepseek-r1) are primarily English-trained. Performance on non-English documents degrades significantly.

**Mitigation:** `glm-5:cloud` and `qwen3.5:cloud` have stronger multilingual support.

---

## Comparison Table

### Query3AI vs Alternative Approaches

| Feature | Query3AI | Standard RAG | ChatGPT Upload | Manual Reading |
|---|:---:|:---:|:---:|:---:|
| **Runs locally** | ✅ | ✅ | ❌ | ✅ |
| **Private (no cloud)** | ✅ | ✅ | ❌ | ✅ |
| **Persistent memory** | ✅ | ✅ | ❌ | ❌ |
| **Document structure aware** | ✅ | ❌ | Partial | ✅ |
| **Source traceability** | ✅ | Partial | ❌ | ✅ |
| **Multi-document queries** | ✅ | ✅ | ❌ | ❌ |
| **No GPU required** | ✅ | ✅ | N/A | N/A |
| **Fast responses** | ❌ (local) | ✅ | ✅ | ❌ |
| **Free to use** | ✅ | Depends | ❌ | ✅ |
| **Programmable / API** | ✅ | ✅ | Limited | ❌ |
| **OCR / scanned docs** | ❌ | Depends | Partial | ✅ |
| **Handles large docs well** | ⚠️ Model-dependent | Partial | ❌ (token limit) | ❌ |

---

### Query3AI vs LlamaIndex / LangChain RAG

| | Query3AI | LlamaIndex / LangChain |
|---|---|---|
| **Complexity** | Lower — focused scope | Higher — general purpose framework |
| **Storage** | Neo4j graph (structured) | Vector DB (flat similarity) |
| **Document structure** | Explicit hierarchy | Flat chunks |
| **Agent specialisation** | 3 purpose-built agents | Single LLM with tools |
| **Transparency** | High — every node is inspectable | Medium — vector space is opaque |
| **Customisability** | Moderate | Very high |
| **Learning curve** | Low | High |

**When to choose LlamaIndex/LangChain instead:** You need maximum flexibility, custom retrieval strategies, embedding-based semantic search, or integration with a wide ecosystem of tools and data sources.

**When to choose Query3AI instead:** You want a focused, understandable pipeline for document Q&A with structural awareness, source traceability, and local-first privacy.

---

## Honest Summary

Query3AI makes a specific trade-off: **depth over breadth**.

It does one thing — intelligent document querying — and it does it with a level of structural understanding that general RAG pipelines don't achieve. The cost is speed (local inference is slow) and setup complexity (Neo4j + Ollama + three models).

For anyone working regularly with complex private documents who values accuracy, traceability, and privacy over convenience, Query3AI is a compelling choice. For anyone wanting a quick, plug-and-play document chatbot, simpler tools may be a better fit.

The local-first, graph-backed, multi-agent architecture is not the easiest path. It is the most principled one.
