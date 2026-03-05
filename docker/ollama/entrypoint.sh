#!/bin/bash
set -e

# Configuration
OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:11434}"
MODELS="${MODELS:-llama3.2:3b}"

echo "=========================================="
echo "AIVuT Ollama Container"
echo "=========================================="
echo "Host: $OLLAMA_HOST"
echo "Models to load: $MODELS"
echo "=========================================="

# Start Ollama server in background
echo "[*] Starting Ollama server..."
ollama serve &
OLLAMA_PID=$!

# Wait for server to be ready
echo "[*] Waiting for Ollama server to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "[!] ERROR: Ollama server failed to start after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "[*] Waiting for server... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "[+] Ollama server is ready"

# Pull required models
echo "[*] Pulling models..."
IFS=',' read -ra MODEL_ARRAY <<< "$MODELS"
for MODEL in "${MODEL_ARRAY[@]}"; do
    MODEL=$(echo "$MODEL" | xargs)  # Trim whitespace
    echo "[*] Pulling model: $MODEL"

    if ollama pull "$MODEL"; then
        echo "[+] Successfully pulled: $MODEL"
    else
        echo "[!] WARNING: Failed to pull model: $MODEL"
    fi
done

echo "=========================================="
echo "[+] Ollama container ready"
echo "[+] API available at http://localhost:11434"
echo "=========================================="

# List available models
echo "[*] Available models:"
ollama list

# Keep container running by waiting on Ollama process
wait $OLLAMA_PID