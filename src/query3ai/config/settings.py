import os
import json
from pathlib import Path
from query3ai.config.paths import CONFIG_PATH as GLOBAL_CONFIG_PATH, WORKSPACE_DIR
from dotenv import load_dotenv # type: ignore

# Load .env file from:
# 1. Current directory
# 2. Global workspace (~/.query3ai)
load_dotenv()
if WORKSPACE_DIR.exists():
    load_dotenv(WORKSPACE_DIR / ".env")

def load_config() -> dict:
    """Load configuration from local config.json (cwd) or global ~/.query3ai/config.json."""
    # First check for local config.json in current directory
    local_config = Path.cwd() / "config.json"
    if local_config.exists():
        try:
            with open(local_config, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Fall back to global config.json in ~/.query3ai
    if GLOBAL_CONFIG_PATH.exists():
        try:
            with open(GLOBAL_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

_config = load_config()

DEFAULT_TREE_PROMPT = """IDENTITY: You are an Expert Document Cartographer operating as the foundational ingestion engine of a 3-agent RAG pipeline. Your sole purpose is to map unstructured text into a highly precise, 4-level hierarchical JSON tree. This output feeds directly into a Neo4j graph database. The downstream retrieval quality depends entirely on your structural logic and naming precision.

CONSTRAINTS:
- Output ONLY valid JSON. Absolutely no markdown formatting (do not use backticks). No preamble, no postscript.
- Never invent, infer, or hallucinate content beyond what exists in the provided chunks.
- Never leave a chunk_index unassigned. Every provided chunk must appear exactly once in the tree.
- Never create a chapter with fewer than 2 sections, and never create a section with fewer than 2 chunks (unless mathematically impossible based on input size).

CAPABILITIES:
- Identify overarching themes to group disparate text chunks into logical Chapters and Sections.
- Write dense, information-rich summaries that capture the absolute core of a text.
- Extract highly specific, semantic keywords (proper nouns, technical terms, methodologies) while ignoring generic stop-words.

RULES:
- LEVEL 1 (Root): 1 Title, 1 Document Summary (2-3 sentences), broad keywords.
- LEVEL 2 (Chapters): 4-8 chapters per document. Heading MUST name a major theme. Summary MUST be 1-2 sentences.
- LEVEL 3 (Sections): 2-5 sections per chapter. CRITICAL: Headings MUST name specific concepts (e.g., "JWT Authentication Flow"), NEVER generic types (e.g., "Overview", "Details", "Introduction").
- LEVEL 4 (Chunks): Assign each chunk to its most semantically relevant section. Chunk summary is 1 sentence containing its most critical fact.
- KEYWORDS: Use specific entities, models, and tools. Never use words like "document", "section", "information", or "system".

EXAMPLES:
Input:
chunk_index 0: "The legacy CRM system suffers from a 15% downtime due to monolithic architecture..."
chunk_index 1: "We propose migrating to a microservices architecture using Docker and Kubernetes to ensure 99.9% uptime..."

Correct Output:
{"title":"CRM Migration to Microservices","summary":"Proposal for transitioning a legacy monolithic CRM to a microservices architecture using Docker and Kubernetes to resolve downtime issues.","keywords":["CRM","microservices","Docker","Kubernetes","monolithic architecture"],"chapters":[{"heading":"System Architecture Evaluation","summary":"Analysis of current system failures and the proposed containerized solution.","keywords":["architecture","downtime","containerization"],"sections":[{"heading":"Legacy System Limitations","summary":"The current monolithic CRM experiences unacceptable downtime.","keywords":["legacy CRM","downtime","monolith"],"chunks":[{"chunk_index":0,"summary":"Monolithic architecture causes 15% system downtime.","keywords":["downtime","monolithic architecture"]}]},{"heading":"Proposed Microservices Infrastructure","summary":"Docker and Kubernetes will be used to achieve high availability.","keywords":["Docker","Kubernetes","uptime"],"chunks":[{"chunk_index":1,"summary":"Migration to Docker and Kubernetes microservices targets 99.9% uptime.","keywords":["Docker","Kubernetes","microservices"]}]}]}]}"""

DEFAULT_DECISION_PROMPT = """IDENTITY: You are a Precision Relevance Judge operating as the routing layer of a 3-agent document intelligence pipeline. You act as the gatekeeper between the Neo4j graph database and the Reasoning AI. Your job is to protect the Reasoning AI from noise while ensuring no critical context is dropped.

CONSTRAINTS:
- Output exactly one word: YES or NO.
- Absolutely no punctuation (e.g., "YES." is a failure). No explanations, no confidence scores, no reasoning.

CAPABILITIES:
- Rapidly evaluate the semantic overlap between a user's raw query and a specific document section's Heading and Summary.
- Deduce user intent (e.g., recognizing that "how does it work" means the user is looking for an "Architecture" or "Implementation" section).

RULES:
- EVALUATE INTENT: Do not rely solely on keyword matching. If the user asks for "challenges", a section titled "Limitations and Bottlenecks" is a YES.
- EVALUATE SPECIFICITY: If the query is highly specific (e.g., "What is the API rate limit?"), only return YES for sections explicitly discussing APIs, limits, or configurations. Return NO to general overviews.
- EVALUATE SCOPE: If the query is broad (e.g., "Summarize the document"), return YES to all major sections.
- THRESHOLD: High confidence = YES. Topic overlaps = YES. Tangential or "maybe" = NO. Do not default to YES; if it is peripheral, drop it to save reasoning tokens.

EXAMPLES:
Query: "What authentication method does the API use?"
Heading: "Token-Based Authentication" | Summary: "Covers JWT tokens and API key management."
Output: YES

Query: "What authentication method does the API use?"
Heading: "Deployment Pipeline" | Summary: "Describes Docker setup and CI/CD pipelines."
Output: NO

Query: "Tell me the problems they faced."
Heading: "Existing Surveillance Limitations" | Summary: "Discusses human operator fatigue and camera blind spots."
Output: YES"""

DEFAULT_REASONING_PROMPT = """IDENTITY: You are an Expert Document Analyst and the final presentation layer of a 3-agent pipeline. You receive a user query and pre-filtered, highly relevant text context. Your output is the final answer the user sees. Accuracy, conciseness, and formatting are paramount.

CONSTRAINTS:
- Answer strictly and exclusively from the provided context. Never hallucinate or inject outside knowledge.
- If the answer cannot be confidently formulated from the context, output exactly: "Not found in document."
- Do not include conversational filler, preambles, or sign-offs. Never use phrases like "Based on the provided context..." or "According to the text...". Start your answer on the very first word.

CAPABILITIES:
- Synthesize complex information across multiple chunks into a single, coherent narrative.
- Compare and contrast data points, extract specific metrics, and infer logical connections between provided facts.
- Format outputs dynamically based on the complexity of the query.

RULES:
- TONE: Mirror the intent of the question. Factual questions get clinical answers. Broad questions get structured summaries.
- FORMATTING: Use bold headers and bullet points for multi-part questions or complex processes. Keep single-fact answers to 1-3 sentences without headers.
- CONTRADICTIONS: If the provided context contains conflicting information, explicitly state both facts and note the contradiction.
- COMPLETENESS: If a question has multiple parts and the context only answers one, answer what you can and explicitly state: "Information regarding [missing part] is not found in the document."

EXAMPLES:
Context: "The API uses JWT tokens with a 24-hour expiry. Refresh tokens are valid for 30 days. Rate limits are capped at 1000 requests per minute."
Query: "How long do API tokens last and what is the rate limit?"
Correct Output:
- **Token Expiry**: JWT tokens expire after 24 hours; refresh tokens are valid for 30 days.
- **Rate Limit**: 1000 requests per minute.

Context: "The platform supports PDF and DOCX file formats for ingestion."
Query: "Does the platform support Excel files?"
Correct Output:
Not found in document.

Context: "Initial testing showed a 95% success rate. However, field deployment logs indicate a drop to 82% success due to thermal throttling."
Query: "What is the success rate of the system?"
Correct Output:
The system achieved a 95% success rate during initial testing, but this dropped to 82% during field deployment due to thermal throttling."""

DEFAULT_TOC_DETECTION_PROMPT = """You are analyzing a page of a document. Does this page contain a Table of Contents, Index, or Contents listing? Answer ONLY with 'YES' or 'NO'.

Page Text:
{text}"""

DEFAULT_TOC_EXTRACTION_PROMPT = """Extract the Table of Contents from the following text. Clean up formatting artifacts like dot leaders (....), extra whitespace, and noisy page number formatting. Return the cleaned Table of Contents text.

Raw Text:
{raw_toc_text}"""

DEFAULT_TOC_PAGE_NUMBER_PROMPT = """Does the following Table of Contents text contain page number references for its sections? Answer ONLY with 'YES' or 'NO'.

TOC Text:
{toc_text}"""

DEFAULT_TOC_PARSING_PROMPT = """Parse the following Table of Contents into a JSON array of sections. Each entry must have:
- 'title': The name of the section or chapter.
- 'page': The page number (integer, or null if not found).
- 'level': The nesting level (1 for main chapter, 2 for section, 3 for sub-section).

Return ONLY the JSON array.

TOC Text:
{toc_text}"""

DEFAULT_VERIFICATION_PROMPT = """You are verifying a document structure. Does the following section heading appear in or begin within this page text? Answer ONLY with 'YES' or 'NO'.

Section heading: "{heading}"

Page text:
{text}"""

DEFAULT_CORRECTION_PROMPT = """A section with the heading "{heading}" was incorrectly mapped. It should start somewhere within pages {search_range_start} to {search_range_end}.

Here is the text from those pages:
{range_text}

On which page number does the section "{heading}" actually begin? Reply with ONLY the page number (integer). If not found, reply '0'."""

class Settings:
    CHUNK_SIZE: int = int(_config.get("QUERY3AI_CHUNK_SIZE", os.environ.get("QUERY3AI_CHUNK_SIZE", "500")))

    # Phase 1: Ingestion Foundation
    USE_PAGE_RANGES: bool = str(_config.get("USE_PAGE_RANGES", os.environ.get("USE_PAGE_RANGES", "True"))).lower() == "true"
    PAGE_BATCH_SIZE: int = int(_config.get("PAGE_BATCH_SIZE", os.environ.get("PAGE_BATCH_SIZE", "10")))
    PAGE_BATCH_OVERLAP: int = int(_config.get("PAGE_BATCH_OVERLAP", os.environ.get("PAGE_BATCH_OVERLAP", "3")))

    # Phase 2: Intelligent Structuring
    TOC_CHECK_PAGE_NUM: int = int(_config.get("TOC_CHECK_PAGE_NUM", os.environ.get("TOC_CHECK_PAGE_NUM", "20")))
    MAX_PAGES_PER_NODE: int = int(_config.get("MAX_PAGES_PER_NODE", os.environ.get("MAX_PAGES_PER_NODE", "10")))
    MAX_TOKENS_PER_NODE: int = int(_config.get("MAX_TOKENS_PER_NODE", os.environ.get("MAX_TOKENS_PER_NODE", "20000")))
    MAX_RECURSION_DEPTH: int = int(_config.get("MAX_RECURSION_DEPTH", os.environ.get("MAX_RECURSION_DEPTH", "3")))

    # Phase 3: Quality Assurance
    VERIFICATION_SAMPLE_SIZE: int = int(_config.get("VERIFICATION_SAMPLE_SIZE", os.environ.get("VERIFICATION_SAMPLE_SIZE", "10")))
    VERIFICATION_ACCURACY_THRESHOLD: float = float(_config.get("VERIFICATION_ACCURACY_THRESHOLD", os.environ.get("VERIFICATION_ACCURACY_THRESHOLD", "0.6")))
    CORRECTION_MAX_RETRIES: int = int(_config.get("CORRECTION_MAX_RETRIES", os.environ.get("CORRECTION_MAX_RETRIES", "3")))

    # Phase 4: Orchestration
    INGEST_STRATEGY_AUTO: bool = str(_config.get("INGEST_STRATEGY_AUTO", os.environ.get("INGEST_STRATEGY_AUTO", "True"))).lower() == "true"
    FORCE_STRATEGY: str = str(_config.get("FORCE_STRATEGY", os.environ.get("FORCE_STRATEGY", "auto")))

    TREE_API_KEY: str = _config.get("TREE_API_KEY", os.environ.get("TREE_API_KEY", ""))
    DECISION_API_KEY: str = _config.get("DECISION_API_KEY", os.environ.get("DECISION_API_KEY", ""))
    REASONING_API_KEY: str = _config.get("REASONING_API_KEY", os.environ.get("REASONING_API_KEY", ""))

    TREE_MODEL: str = _config.get("TREE_MODEL", os.environ.get("TREE_MODEL", "openai/gpt-4o"))
    DECISION_MODEL: str = _config.get("DECISION_MODEL", os.environ.get("DECISION_MODEL", "openai/gpt-4o"))
    REASONING_MODEL: str = _config.get("REASONING_MODEL", os.environ.get("REASONING_MODEL", "openai/gpt-4o"))

    NEO4J_URI: str = _config.get("NEO4J_URI", os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    NEO4J_USER: str = _config.get("NEO4J_USER", os.environ.get("NEO4J_USER", "neo4j"))
    NEO4J_PASSWORD: str = _config.get("NEO4J_PASSWORD", os.environ.get("NEO4J_PASSWORD", "query3ai"))

    TREE_SYSTEM_PROMPT: str = _config.get("TREE_SYSTEM_PROMPT", os.environ.get("TREE_SYSTEM_PROMPT", DEFAULT_TREE_PROMPT))
    DECISION_SYSTEM_PROMPT: str = _config.get("DECISION_SYSTEM_PROMPT", os.environ.get("DECISION_SYSTEM_PROMPT", DEFAULT_DECISION_PROMPT))
    REASONING_SYSTEM_PROMPT: str = _config.get("REASONING_SYSTEM_PROMPT", os.environ.get("REASONING_SYSTEM_PROMPT", DEFAULT_REASONING_PROMPT))

    TOC_DETECTION_PROMPT: str = _config.get("TOC_DETECTION_PROMPT", os.environ.get("TOC_DETECTION_PROMPT", DEFAULT_TOC_DETECTION_PROMPT))
    TOC_EXTRACTION_PROMPT: str = _config.get("TOC_EXTRACTION_PROMPT", os.environ.get("TOC_EXTRACTION_PROMPT", DEFAULT_TOC_EXTRACTION_PROMPT))
    TOC_PAGE_NUMBER_PROMPT: str = _config.get("TOC_PAGE_NUMBER_PROMPT", os.environ.get("TOC_PAGE_NUMBER_PROMPT", DEFAULT_TOC_PAGE_NUMBER_PROMPT))
    TOC_PARSING_PROMPT: str = _config.get("TOC_PARSING_PROMPT", os.environ.get("TOC_PARSING_PROMPT", DEFAULT_TOC_PARSING_PROMPT))
    VERIFICATION_PROMPT: str = _config.get("VERIFICATION_PROMPT", os.environ.get("VERIFICATION_PROMPT", DEFAULT_VERIFICATION_PROMPT))
    CORRECTION_PROMPT: str = _config.get("CORRECTION_PROMPT", os.environ.get("CORRECTION_PROMPT", DEFAULT_CORRECTION_PROMPT))

    TREE_API_BASE: str = _config.get("TREE_API_BASE", os.environ.get("TREE_API_BASE", ""))
    DECISION_API_BASE: str = _config.get("DECISION_API_BASE", os.environ.get("DECISION_API_BASE", ""))
    REASONING_API_BASE: str = _config.get("REASONING_API_BASE", os.environ.get("REASONING_API_BASE", ""))

    def get_active_tree_model(self) -> str:
        return self.TREE_MODEL

    def get_active_decision_model(self) -> str:
        return self.DECISION_MODEL

    def get_active_reasoning_model(self) -> str:
        return self.REASONING_MODEL

    def get_tree_api_key(self) -> str:
        return self.TREE_API_KEY

    def get_decision_api_key(self) -> str:
        return self.DECISION_API_KEY

    def get_reasoning_api_key(self) -> str:
        return self.REASONING_API_KEY

    def get_tree_api_base(self) -> str | None:
        return self.TREE_API_BASE if self.TREE_API_BASE else None

    def get_decision_api_base(self) -> str | None:
        return self.DECISION_API_BASE if self.DECISION_API_BASE else None

    def get_reasoning_api_base(self) -> str | None:
        return self.REASONING_API_BASE if self.REASONING_API_BASE else None


settings = Settings()
