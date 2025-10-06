FROM ollama/ollama:latest

# Set environment variable to enable serving on all interfaces inside the container
ENV OLL#AMA_HOST=0.0.0.0
ENV OLLAMA_MODELS=/root/.ollama/models

# Expose the default port for the Ollama API
EXPOSE 11434

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy the entrypoint script
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# The entrypoint script will handle starting Ollama and pulling the models
ENTRYPOINT ["./entrypoint.sh"]
