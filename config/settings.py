import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    CHUNK_SIZE: int = int(os.getenv("QUERY3AI_CHUNK_SIZE", "500"))

    TREE_MODEL: str = "phi3.5:3.8b"
    DECISION_MODEL: str = "gemma2:2b"
    REASONING_MODEL: str = "deepseek-r1:7b"
    USE_CLOUD: bool = False

    CLOUD_TREE_MODEL: str = "qwen3.5:cloud"
    CLOUD_DECISION_MODEL: str = "kimi-k2.5:cloud"
    CLOUD_REASONING_MODEL: str = "glm-5:cloud"

    USE_GROQ: bool = True
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    GROQ_TREE_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_DECISION_MODEL: str = "moonshotai/kimi-k2-instruct"
    GROQ_REASONING_MODEL: str = "qwen/qwen3-32b"

    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

    # System Prompts for the 3 Agents
    TREE_SYSTEM_PROMPT: str = """
    You are a document structure extractor.
    Output ONLY valid JSON. No explanation. No markdown.

    Format:
    {"title":"...","summary":"1-2 sentence overview","keywords":["k1","k2","k3"],"sections":[{"heading":"...","summary":"1-2 sentences","keywords":["k1","k2"],"chunks":[{"chunk_index":0,"summary":"1 sentence","keywords":["k1","k2"]}]}]}

    Rules:
    - summary: factual, dense, no filler words
    - keywords: specific nouns/concepts only, no generic words like "document" or "section"
    - Every chunk must appear in exactly one section
    """

    DECISION_SYSTEM_PROMPT: str = """
    You are a relevance filter.
    Reply ONLY with YES or NO.
    YES if the section likely contains the answer or closely related details.
    NO if completely unrelated.
    """

    REASONING_SYSTEM_PROMPT: str = """
    You are a precise document assistant.
    Answer strictly from the provided context.
    If the answer is not in the context, say "Not found in document."
    Be concise. No preamble.
    """

    def get_active_tree_model(self) -> str:
        if self.USE_GROQ:
            return self.GROQ_TREE_MODEL
        return self.CLOUD_TREE_MODEL if self.USE_CLOUD else self.TREE_MODEL

    def get_active_decision_model(self) -> str:
        if self.USE_GROQ:
            return self.GROQ_DECISION_MODEL
        return self.CLOUD_DECISION_MODEL if self.USE_CLOUD else self.DECISION_MODEL

    def get_active_reasoning_model(self) -> str:
        if self.USE_GROQ:
            return self.GROQ_REASONING_MODEL
        return self.CLOUD_REASONING_MODEL if self.USE_CLOUD else self.REASONING_MODEL


settings = Settings()
