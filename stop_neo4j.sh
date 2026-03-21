#!/bin/bash
echo "[INFO] Stopping Neo4j Docker container..."
if command -v docker-compose &> /dev/null; then
    docker-compose down
elif docker compose version &> /dev/null; then
    docker compose down
else
    echo "[WARNING] Docker or Docker Compose not found."
fi
