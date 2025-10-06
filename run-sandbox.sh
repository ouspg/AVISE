#!/bin/bash

#Script to building the Ollama Sandbox environment and running the Python test program.

# --- Configuration ---
IMAGE_NAME="ollama-sandbox"
CONTAINER_NAME="AI-testing-environment"
OLLAMA_PORT="11434"

#REMOVE THIS AND RUNTIMEFLAG FROM THE docker run -command IF YOU ARE NOT RUNNING gVisor
#------------------------------------------------------------------------
# Set gVisor as the fixed, default runtime for mandatory isolation
RUNTIME="gVisor"
RUNTIME_FLAGS="--runtime=runsc"

echo ""
echo "=================================================="
echo "             Checking gVisor status"
echo "=================================================="
echo ""

if ! docker info 2> /dev/null | grep -q runsc; then
  echo "Error: gVisor (runsc) not detected. Install per guide."
  exit 1
fi

echo "=================================================="
echo "        Running gVisor for enhanced isolation."
echo "=================================================="
echo ""
#------------------------------------------------------------------------

# Function to build the Docker image
build_image() {
    echo "=================================================="
    echo "       Building Docker Image: $IMAGE_NAME"
    echo "=================================================="
    echo ""
    docker build -t $IMAGE_NAME .
    if [ $? -ne 0 ]; then
        echo "Docker build failed. Exiting..."
        exit 1
    fi
}

# Function for running the container with arguments
run_container() {
    echo ""
    echo "=================================================="
    echo "  Starting Container: $CONTAINER_NAME (Runtime: $RUNTIME)"
    echo "=================================================="
    echo ""
    
    # Stop and remove any existing containers with the same name
    echo "Stopping and removing previous containers..."
    docker stop $CONTAINER_NAME 2> /dev/null
    docker rm $CONTAINER_NAME 2> /dev/null

# Function to wait for the models to finish downloading inside the container
wait_for_models() {
    MAX_WAIT_TIME=1800 # 30 minutes max wait in case of slow internet connection when loading models
    INTERVAL=5
    ELAPSED=0

    echo "Waiting for setup completion (up to 30 minutes)..."

    while [ $ELAPSED -lt $MAX_WAIT_TIME ]; do
        # Check for the completion message from entrypoint.sh
        if docker logs $CONTAINER_NAME 2>&1 | grep -q "Ollama setup complete. Server remains running."; then
            echo ""
            echo "Models are loaded and the Ollama server is ready."
            return 0
        fi

        # If the container has stopped unexpectedly
        CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' $CONTAINER_NAME 2> /dev/null)
        if [ "$CONTAINER_STATUS" != "running" ]; then
            echo ""
            echo "Container stopped unexpectedly."
            echo "Please check logs for details: 'docker logs $CONTAINER_NAME'"
            exit 1
        fi

        echo -n "."
        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
    done

    echo ""
    echo "Model download timed out. Check logs for more information."
    exit 1
}

    # Run the Docker container. Remove $RUNTIME_FLAG IF NOT RUNNING gVisor
    docker run -d \
      $RUNTIME_FLAG \
      --gpus all \
      --name $CONTAINER_NAME \
      -p $OLLAMA_PORT:$OLLAMA_PORT \
      -v ollama-data:/root/.ollama \
      $IMAGE_NAME

    # Check the status of the docker run command
    if [ $? -ne 0 ]; then
        echo "Docker run failed. Exiting..."
        exit 1
    fi

    echo "Container started. Waiting for models to download..."
    wait_for_models
}

# Function to execute the Python client
run_client() {
    echo ""
    echo "=================================================="
    echo "       Executing Python Testing Program"
    echo "=================================================="
    echo ""
    
    # Ensure Python dependencies are installed (optional, but good practice)
    if [ -f requirements.txt ]; then
        echo "Installing Python dependencies from requirements.txt..."
        pip install -q -r requirements.txt
    fi
    
    python3 -m src.run_tests
    if [ $? -ne 0 ]; then
        echo "Python client failed to execute."
    fi
}

# --- Main Execution ---

build_image
run_container
run_client

echo "=================================================="
echo ""
echo "✅ Test Cycle Completed."
echo "To stop the container later: docker stop $CONTAINER_NAME"
echo "To remove the container and model data: docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME"
echo ""
echo "=================================================="