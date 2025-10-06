#!/bin/bash

#Just examples, choose your own
TESTABLE_MODEL="llama3:8b"
EVALUATOR_MODEL="phi3:mini"

echo "Starting Ollama server in the background..."
/bin/ollama serve &

# Record the Process ID of the Ollama server
OLLAMA_PID=$!

echo "⏳ Waiting 5 seconds for Ollama server to initialize..."
sleep 5

# Function to check if the server is running
check_server() {
    curl -s http://localhost:11434/api/tags > /dev/null
    return $?
}

# Wait until the Ollama API is responsive
MAX_ATTEMPTS=50
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if check_server; then
        echo "Ollama API is active."
        break
    fi
    echo "Waiting for Ollama API (Attempt $((ATTEMPT + 1))/$MAX_ATTEMPTS)..."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "Failed to start Ollama API. Exiting..."
    exit 1
fi

# Pull the Testable Model
echo "Pulling Testable Model: $TESTABLE_MODEL"
ollama pull $TESTABLE_MODEL

# Pull the Evaluator Model
echo "Pulling Evaluator Model: $EVALUATOR_MODEL"
ollama pull $EVALUATOR_MODEL

echo "Ollama setup complete. Server remains running..."

wait $OLLAMA_PID