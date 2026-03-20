# Query3AI

Query3AI is an intelligent document query system operating through a tailored 3-Agent architecture. It orchestrates document ingestion, semantic chunk tree generation, node relevance evaluation, and final answer reasoning, backed natively by Neo4j graph storage.

## 🚀 Quick Start Guide

### 1. Install Project Dependencies
Open your terminal and navigate to the project directory. First, create and activate a Python virtual environment:

**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

Next, install the required packages:
```bash
pip install -r requirements.txt
```

### 2. Start and Configure Neo4j
The system needs Neo4j to store the extracted node trees.
- Run your local Neo4j desktop application or spin it up via Docker.
- By default, `settings.py` looks for:
  - **URI**: `bolt://localhost:7687`
  - **User**: `neo4j`
  - **Password**: `password`
- *(If your credentials differ, simply update them inside `config/settings.py`!)*

### 3. Start Ollama and Pull Models
Our 3-agent offline pipeline requires three specific models downloaded to your local Ollama instance:
1. Make sure Ollama is running in the background (`ollama serve` or open the Ollama app).
2. Pull the necessary local models one by one in your terminal:
   ```bash
   ollama pull phi3.5         # Tree Agent (Tree Builder)
   ollama pull gemma2:2b      # Decision Agent (Decision Filter)
   ```
## 🚀 Using the Dedicated App Interface

If you want a dedicated Graphical User Interface mapping completely avoiding the standard raw command logs, double-click the `start_chat.bat` (Windows) or execute `start_chat.sh` (Mac/Linux)!

These scripts will securely generate a bespoke isolated terminal execution instance parsing custom functionality natively through standard chat limits natively!

### 🔮 Interactive TUI `/Slash` Commands
Once inside the running continuous Chat interface, inputting standard `/` strings will explicitly prevent AI LLM consumption logically executing UI changes instantaneously!

- `/about`: Details the exact pipeline parameters spanning Query3AI processing layers natively.
- `/help`: Print exactly all functional UI slash bindings beautifully rendering formatting Tables natively.
- `/listdocs`: Trigger the global CLI node iteration loop implicitly surfacing active documents in Neo4j.
- `/list`: Explicitly evaluate granular total sections scaling explicitly mapping entire neo4j structural chunk depths securely.
- `/delete`: Trigger an explicit interactive protection block removing specific documents exactly erasing matching Nodes globally!
- `/clear`: Refreshes and aggressively clears active OS level application log buffers implicitly matching clean terminal execution constraints globally!
- `/exit`: Stop running executable terminal cleanly!

## Testing / Execution Examples
   ```bash
   ollama pull deepseek-r1:7b # Reasoning Agent (Reasoning Engine)
   ```

### 4. Environment Variables Configs
Modify variables globally via `config/settings.py` if needed:
- **TREE_MODEL**: Document structure interpretation (default `phi3.5`)
- **DECISION_MODEL**: Chunk relevance parsing (default `gemma2:2b`)
- **REASONING_MODEL**: Semantic reasoning engine (default `deepseek-r1:7b`)

---

## 🛠️ CLI Commands

Query3AI uses Typer to execute unified terminal commands:

- **Ingest a document:**
  ```bash
  python main.py ingest "path/to/your/document.docx"
  ```
  Query3AI natively supports **PDF**, **DOCX**, and **TXT** files. It extracts contents locally, chunking, tree generation with Tree Agent, and inserts nodes mapping connected Neo4j instance.
  
- **List ingested documents:**
  ```bash
  python main.py list
  ```
  Returns a comprehensive table summarizing all uploaded files spanning across Document nodes.

- **Inspect a specific document tree:**
  ```bash
  python main.py inspect <doc_id>
  ```
  Explores the exact mapped branch layout `Document -> Sections -> Chunks` directly extracted from the graph space.

- **Ask questions:**
  ```bash
  python main.py ask "Can you summarize the main points?" [--cloud]
  ```
  Initializes Neo4j bulk lookup → Decision Agent filters contextual scope per relevance rules → Reasoning Agent derives logic against remaining blocks and serves dynamic answers.
  Enable cloud equivalent inference routing strictly via the `--cloud` option.

- **Delete an ingested document:**
  ```bash
  python main.py delete <doc_id>
  ```
  Cascades and gently removes the complete Document layout scope permanently along with related sections/chunks. (User confirmation required).

---

## ☁️ Cloud Configuration Guide
Toggle settings inside `config/settings.py` natively or just use the `--cloud` flag.
Cloud instances trigger substitution maps internally if invoked: 
- `qwen3.5:cloud`
- `kimi-k2.5:cloud`
- `glm-5:cloud`
