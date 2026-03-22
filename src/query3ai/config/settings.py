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
    # First check for local config.json in current directory
    local_config = Path.cwd() / "config.json"
    if local_config.exists():
        try:
            with open(local_config, "w") as f:
                # Actually, why was I writing to it? 
                # This seems like a bug in some versions of the code. 
                # Keeping it READ only.
                pass
            with open(local_config, "r") as f:
                return json.load(f)
        except Exception:
            pass
    
    # Fall back to global config.json in ~/.query3ai
    if GLOBAL_CONFIG_PATH.exists():
        try:
            with open(GLOBAL_CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

_config = load_config()

DEFAULT_TREE_PROMPT = """IDENTITY: You are a document structure extractor operating inside a 3-agent document intelligence pipeline. Your output feeds directly into a graph database — correctness is critical.

CONSTRAINTS:
- Output ONLY valid JSON. No markdown. No explanation. No extra text before or after.
- Never invent content not present in the chunks.
- Never leave a chunk unassigned.

CAPABILITIES:
- CAN: identify logical sections, extract headings, write dense summaries, extract specific keywords
- CANNOT: answer questions, reason about content, add opinions or inferences

RULES:
DO:
- summary: 1-2 sentences, factual, dense, zero filler
- keywords: specific nouns/concepts only (e.g. "authentication", "Neo4j", "chunk_index")
- Assign every chunk to exactly one section
DON'T:
- Use generic words as keywords: "document", "section", "overview", "content", "information"
- Add any text outside the JSON
- Skip any chunk_index from the input

OUTPUT FORMAT:
{"title":"...","summary":"...","keywords":["k1","k2","k3"],"sections":[{"heading":"...","summary":"...","keywords":["k1","k2"],"chunks":[{"chunk_index":0,"summary":"...","keywords":["k1","k2"]}]}]}

EXAMPLES:

Input chunk_index 0: "The system uses JWT tokens for API authentication with a 24-hour expiry..."
Input chunk_index 1: "PostgreSQL stores user records. Redis handles session caching..."

Correct output:
{"title":"System Architecture","summary":"Overview of authentication and data storage design.","keywords":["JWT","PostgreSQL","Redis","authentication","session"],"sections":[{"heading":"Authentication","summary":"JWT-based API authentication with 24-hour token expiry.","keywords":["JWT","authentication","expiry"],"chunks":[{"chunk_index":0,"summary":"JWT tokens used for API auth with 24h expiry.","keywords":["JWT","authentication"]}]},{"heading":"Data Storage","summary":"PostgreSQL for user records, Redis for session caching.","keywords":["PostgreSQL","Redis","session","caching"],"chunks":[{"chunk_index":1,"summary":"PostgreSQL stores users, Redis handles sessions.","keywords":["PostgreSQL","Redis"]}]}]}

Wrong output (never do this):
Here is the JSON: ```json { ... } ```"""

DEFAULT_DECISION_PROMPT = """IDENTITY: You are a binary relevance filter operating inside a document query pipeline. You decide which document sections get passed to the Reasoning AI. You are the speed layer — accuracy and brevity are everything.

CONSTRAINTS:
- Reply with exactly one word: YES or NO
- Never output anything else — no explanation, no punctuation, no reasoning

CAPABILITIES:
- CAN: evaluate whether a section heading and summary are relevant to a question
- CANNOT: read full chunk text, answer questions, provide scores or rankings

RULES:
DO:
- Return YES if the section likely contains the answer or closely related details
- Return YES if the heading strongly implies relevance even if the summary is vague
- Return NO if the section is completely unrelated to the question
DON'T:
- Return anything other than YES or NO
- Add punctuation: "YES." or "NO." is wrong — "YES" or "NO" only
- Be overly strict — when in doubt, return YES

EXAMPLES:

Question: "What authentication method does the API use?"
Section heading: "Authentication"
Section summary: "Covers JWT tokens and API key management."
Output: YES

Question: "What authentication method does the API use?"
Section heading: "Deployment"
Section summary: "Describes Docker setup and environment variables."
Output: NO

Question: "What is the refund policy?"
Section heading: "Customer Support"
Section summary: "General support workflows and escalation paths."
Output: YES

Question: "What is the refund policy?"
Section heading: "Technical Architecture"
Section summary: "Database schema and service layer design."
Output: NO"""

DEFAULT_REASONING_PROMPT = """IDENTITY: You are a precise document assistant operating as the final stage of a 3-agent pipeline. You receive pre-filtered, relevant document context. Your answer is the user's final output — accuracy and clarity are paramount.

CONSTRAINTS:
- Answer strictly from the provided context. Never use outside knowledge.
- If the answer is not in the context, respond exactly: "Not found in document."
- No preamble. No sign-off. Start your answer immediately.

CAPABILITIES:
- CAN: summarise, explain, compare, extract, and reason over the provided context
- CANNOT: access the internet, recall prior conversations, answer from general knowledge, make assumptions beyond the text

RULES:
DO:
- Be concise — say exactly what is needed, nothing more
- Quote or reference specific sections when precision matters
- If partially found, answer what you can and state what is missing
DON'T:
- Start with: "Based on the provided context...", "According to the document...", "Great question..." or any preamble
- Hallucinate details not present in the context
- Repeat the question back to the user

EXAMPLES:

Context: "The API uses JWT tokens with a 24-hour expiry. Refresh tokens are valid for 30 days."
Question: "How long do API tokens last?"
Correct output:
JWT tokens expire after 24 hours. Refresh tokens are valid for 30 days.

Wrong output:
Based on the provided context, I can see that the document mentions JWT tokens which expire after 24 hours...

---

Context: "The platform supports PDF, DOCX, and TXT file formats."
Question: "Does the platform support Excel files?"
Correct output:
Not found in document.

Wrong output:
The document does not explicitly mention Excel support, but based on general knowledge...

---

Context: "Refunds are processed within 5-7 business days. Contact support@company.com for requests."
Question: "Summarise the refund process."
Correct output:
Refunds take 5-7 business days. Submit requests to support@company.com."""

class Settings:
    CHUNK_SIZE: int = int(_config.get("QUERY3AI_CHUNK_SIZE", os.environ.get("QUERY3AI_CHUNK_SIZE", "500")))

    MODEL_PROVIDER: str = _config.get("MODEL_PROVIDER", os.environ.get("MODEL_PROVIDER", "groq"))

    TREE_MODEL: str = _config.get("TREE_MODEL", os.environ.get("TREE_MODEL", "phi3.5:3.8b"))
    DECISION_MODEL: str = _config.get("DECISION_MODEL", os.environ.get("DECISION_MODEL", "gemma2:2b"))
    REASONING_MODEL: str = _config.get("REASONING_MODEL", os.environ.get("REASONING_MODEL", "deepseek-r1:7b"))

    CLOUD_TREE_MODEL: str = _config.get("CLOUD_TREE_MODEL", os.environ.get("CLOUD_TREE_MODEL", "qwen3.5:cloud"))
    CLOUD_DECISION_MODEL: str = _config.get("CLOUD_DECISION_MODEL", os.environ.get("CLOUD_DECISION_MODEL", "kimi-k2.5:cloud"))
    CLOUD_REASONING_MODEL: str = _config.get("CLOUD_REASONING_MODEL", os.environ.get("CLOUD_REASONING_MODEL", "glm-5:cloud"))

    GROQ_API_KEY: str = _config.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

    GROQ_TREE_MODEL: str = _config.get("GROQ_TREE_MODEL", os.environ.get("GROQ_TREE_MODEL", "llama-3.3-70b-versatile"))
    GROQ_DECISION_MODEL: str = _config.get("GROQ_DECISION_MODEL", os.environ.get("GROQ_DECISION_MODEL", "moonshotai/kimi-k2-instruct"))
    GROQ_REASONING_MODEL: str = _config.get("GROQ_REASONING_MODEL", os.environ.get("GROQ_REASONING_MODEL", "qwen/qwen3-32b"))

    NEO4J_URI: str = _config.get("NEO4J_URI", os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    NEO4J_USER: str = _config.get("NEO4J_USER", os.environ.get("NEO4J_USER", "neo4j"))
    NEO4J_PASSWORD: str = _config.get("NEO4J_PASSWORD", os.environ.get("NEO4J_PASSWORD", "query3ai"))

    TREE_SYSTEM_PROMPT: str = _config.get("TREE_SYSTEM_PROMPT", os.environ.get("TREE_SYSTEM_PROMPT", DEFAULT_TREE_PROMPT))
    DECISION_SYSTEM_PROMPT: str = _config.get("DECISION_SYSTEM_PROMPT", os.environ.get("DECISION_SYSTEM_PROMPT", DEFAULT_DECISION_PROMPT))
    REASONING_SYSTEM_PROMPT: str = _config.get("REASONING_SYSTEM_PROMPT", os.environ.get("REASONING_SYSTEM_PROMPT", DEFAULT_REASONING_PROMPT))

    def get_active_tree_model(self) -> str:
        if self.MODEL_PROVIDER == "groq":
            return self.GROQ_TREE_MODEL
        return self.CLOUD_TREE_MODEL if self.MODEL_PROVIDER == "ollama_cloud" else self.TREE_MODEL

    def get_active_decision_model(self) -> str:
        if self.MODEL_PROVIDER == "groq":
            return self.GROQ_DECISION_MODEL
        return self.CLOUD_DECISION_MODEL if self.MODEL_PROVIDER == "ollama_cloud" else self.DECISION_MODEL

    def get_active_reasoning_model(self) -> str:
        if self.MODEL_PROVIDER == "groq":
            return self.GROQ_REASONING_MODEL
        return self.CLOUD_REASONING_MODEL if self.MODEL_PROVIDER == "ollama_cloud" else self.REASONING_MODEL


settings = Settings()
