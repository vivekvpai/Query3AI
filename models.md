# LiteLLM Supported Models Examples

With LiteLLM, you can use models from any provider by prefixing the model string with the provider name. Because of the new Mix-and-Match Architecture, you use explicit Agent prefixes for your keys and bases (`TREE_`, `DECISION_`, `REASONING_`), allowing you to use different providers securely.

## Example: OpenAI Models

TREE_MODEL="openai/gpt-4o"
DECISION_MODEL="openai/gpt-4o-mini"
REASONING_MODEL="openai/o3-mini"
TREE_API_KEY="sk-..." (Repeat for DECISION and REASONING)

## Example: Groq Fast Models

TREE_MODEL="groq/llama-3.3-70b-versatile"
DECISION_MODEL="groq/llama-3.1-8b-instant"
REASONING_MODEL="groq/deepseek-r1-distill-llama-70b"
TREE_API_KEY="gsk_..." (Repeat for DECISION and REASONING)

## Example: Gemini Models

TREE_MODEL="gemini/gemini-2.5-flash"
DECISION_MODEL="gemini/gemini-2.5-flash"
REASONING_MODEL="gemini/gemini-2.5-pro"
TREE_API_KEY="AIza..." (Repeat for DECISION and REASONING)

## Example: Local Ollama Models

```bash
TREE_MODEL="ollama/llama3.2"
DECISION_MODEL="ollama/qwen2.5:7b"
REASONING_MODEL="ollama/deepseek-r1:14b"
# No API keys required for local Ollama
```

## Example: Remote/Cloud Ollama Models

If you have Ollama running on a remote server/cloud:

1. Set `REASONING_API_BASE="http://your-remote-ip:11434"` (or the appropriate agent) in your `.env` or `config.json`.
2. Use the `ollama/` prefix as usual.

```bash
TREE_MODEL="ollama/llama3.2"
DECISION_MODEL="ollama/qwen2.5:7b"
REASONING_MODEL="ollama/deepseek-r1:14b"
TREE_API_BASE="http://your-remote-ip:11434"
DECISION_API_BASE="http://your-remote-ip:11434"
REASONING_API_BASE="http://your-remote-ip:11434"
```
