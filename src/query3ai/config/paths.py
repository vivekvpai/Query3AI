from pathlib import Path

# Global Workspace Directory (~/.query3ai)
WORKSPACE_DIR = Path.home() / ".query3ai"

# Core configurations inside workspace
CONFIG_PATH = WORKSPACE_DIR / "config.json"
COMPOSE_PATH = WORKSPACE_DIR / "docker-compose.yml"
DATA_DIR = WORKSPACE_DIR / "neo4j_data"
TEMP_OUTPUT_DIR = WORKSPACE_DIR / "temp_output"

def ensure_workspace():
    """Ensure the ~/.query3ai directory exists."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
