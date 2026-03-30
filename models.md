# LiteLLM Supported Models Examples

With LiteLLM, you can use models from any provider by prefixing the model string with the provider name.

## Example: OpenAI Models

TREE_MODEL="openai/gpt-4o"
DECISION_MODEL="openai/gpt-4o-mini"
REASONING_MODEL="openai/o3-mini"
LLM_API_KEY="sk-..." (Or OPENAI_API_KEY)

## Example: Groq Fast Models

TREE*MODEL="groq/llama-3.3-70b-versatile"
DECISION_MODEL="groq/llama-3.1-8b-instant"
REASONING_MODEL="groq/deepseek-r1-distill-llama-70b"
LLM_API_KEY="gsk*..." (Or GROQ_API_KEY)

## Example: Gemini Models

TREE_MODEL="gemini/gemini-2.5-flash"
DECISION_MODEL="gemini/gemini-2.5-flash"
REASONING_MODEL="gemini/gemini-2.5-pro"
LLM_API_KEY="AIza..." (Or GEMINI_API_KEY)

## Example: Local Ollama Models

TREE_MODEL="ollama/llama3.2"
DECISION_MODEL="ollama/qwen2.5:7b"
REASONING_MODEL="ollama/deepseek-r1:14b"

# No API key required for local Ollama

## Example: Remote/Cloud Ollama Models

If you have Ollama running on a remote server/cloud:

1. Set `API_BASE="http://your-remote-ip:11434"` in your `.env` or `config.json`.
2. Use the `ollama/` prefix as usual.

TREE_MODEL="ollama/llama3.2"
DECISION_MODEL="ollama/qwen2.5:7b"
REASONING_MODEL="ollama/deepseek-r1:14b"
"API_BASE": "`http://your-remote-ip:11434`"
