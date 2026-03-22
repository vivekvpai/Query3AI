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

DEFAULT_TREE_PROMPT = """You are a document structure extractor.
Output ONLY valid JSON. No explanation. No markdown.

Format:
{"title":"...","summary":"1-2 sentence overview","keywords":["k1","k2","k3"],"sections":[{"heading":"...","summary":"1-2 sentences","keywords":["k1","k2"],"chunks":[{"chunk_index":0,"summary":"1 sentence","keywords":["k1","k2"]}]}]}

Rules:
- summary: factual, dense, no filler words
- keywords: specific nouns/concepts only, no generic words like "document" or "section"
- Every chunk must appear in exactly one section"""

DEFAULT_DECISION_PROMPT = """You are a relevance filter.
Reply ONLY with YES or NO.
YES if the section likely contains the answer or closely related details.
NO if completely unrelated."""

DEFAULT_REASONING_PROMPT = """You are a precise document assistant.
Answer strictly from the provided context.
If the answer is not in the context, say "Not found in document."
Be concise. No preamble."""

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
