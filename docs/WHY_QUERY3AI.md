# Why Query3AI?

> *"Most AI document tools treat your files like a search engine. Query3AI treats them like a thinking partner."*

---

## The Problem

Every organisation — from solo developers to large enterprises — is drowning in documents. PDFs, reports, contracts, research papers, internal wikis, resumes. The information is there. Getting to it reliably is the hard part.

Existing approaches all have the same fundamental flaw:

| Approach | What It Does | Why It Falls Short |
|---|---|---|
| **Ctrl+F / Search** | Finds exact keywords | Misses context, synonyms, implicit meaning |
| **ChatGPT file upload** | Reads file, answers question | No memory, no structure, halluccinates, cloud-only |
| **Vector databases (RAG)** | Embeds chunks, finds similar ones | Treats all chunks equally, loses document hierarchy |
| **Manual reading** | Human reads and answers | Doesn't scale, slow, inconsistent |

The core issue with standard RAG (Retrieval-Augmented Generation) is that it **flattens your document**. It breaks everything into equally-weighted chunks, embeds them as vectors, and finds the "closest" ones to your question. It has no concept of structure — it doesn't know that a chunk belongs to a section, that a section belongs to a chapter, or that some sections are completely irrelevant to your question.

This leads to two common failures:
- **Too much context** — the model gets flooded with irrelevant chunks and loses focus
- **Too little context** — the "closest" vector match misses the actual answer sitting nearby

---

## The Query3AI Approach

Query3AI is built on a different belief: **documents have structure, and that structure is meaningful**.

A well-written document isn't a flat list of sentences. It has a hierarchy — topics, subtopics, supporting details. Query3AI preserves and exploits that hierarchy by converting every document into a **graph of interconnected nodes** stored in Neo4j.

Instead of asking "which chunks are most similar to this question?", Query3AI asks:

1. **What is this document's structure?** *(Tree AI)*
2. **Which sections of that structure are actually relevant to this question?** *(Decision AI)*
3. **Given only those relevant sections, what is the precise answer?** *(Reasoning AI)*

This three-step pipeline means the Reasoning AI never sees irrelevant content. It works with a focused, structured, hierarchically-aware context — and produces answers that are grounded, specific, and traceable to their source.

---

## Who Built This and Why

Query3AI was designed for developers and knowledge workers who:

- Work with **large or complex documents** regularly
- Need answers that are **traceable** — not just "here's an answer" but "here's the section it came from"
- Want to run AI **locally** without sending sensitive documents to the cloud
- Need a system that **remembers** ingested documents across sessions (unlike ChatGPT uploads)
- Want to build on top of a **programmable CLI** rather than a locked-down UI

The goal was to prove that you don't need GPT-4 or a cloud subscription to build an intelligent document system. A well-architected pipeline of small, specialised local models can outperform a single large model on structured document tasks — and do it privately, offline, and for free.

---

## What Query3AI Is Not

To set accurate expectations:

- It is **not a general chatbot** — it only answers based on documents you have ingested
- It is **not a real-time system** — ingestion takes time (tree building is AI-assisted)
- It is **not a replacement for a search engine** — it works on your private document corpus, not the web
- It is **not a vector database** — it uses a graph database with explicit structural relationships

---

## The Vision

Query3AI is a foundation. The current system handles ingestion, structuring, and querying. The roadmap points toward:

- Multi-document reasoning (answer questions that span multiple files)
- Answer storage as graph nodes (your Q&A history becomes part of the knowledge graph)
- A tagging and annotation layer
- An optional web UI for non-technical users

The underlying philosophy remains constant: **structure first, then reason**.
