### Prerequisites

- Python 3.10+
- Docker (for running models backend)
- pip

### 1. Clone the Repository

```bash
git clone <repository-url>
cd AI-Testing-Platform
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv myenv

source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Up by using Ollama Backend with Docker

**GPU Version:**
```bash
docker-compose -f docker/ollama/docker-compose.yml up -d
```

**CPU-only Version:**
```bash
docker-compose -f docker/ollama/docker-compose-cpu.yml up -d
```

### 4. Pull Models

After Ollama is running, pull the models you want to test:

```bash
# Pull models for testing and for evaluation
docker exec -it ollama ollama pull <model_name>
```

### 5. Configure Models

Edit `src/configs/model.json`:

```json
{
  "testable_model": "X",
  "evaluation_model": "Y",
  "api_url": "http://localhost:11434" #Ollama default
}
```

## Usage

```bash
python -m src.runner -test <test_name> -modelconf <path> -testconf <path> [options]
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `-test` | Test to run (e.g., `prompt_injection`, `context_test`) |
| `-modelconf` | Path to model configuration JSON |
| `-testconf` | Path to test configuration JSON |

### Optional Arguments

| Argument | Description |
|----------|-------------|
| `-format` | Report format: `json`, `html`, `md` |
| `-output` | Custom output file path |
| `-reports-dir` | Base directory for reports (default: `reports/`) |
| `-apikey` | API key for authenticated APIs |
| `-list` | List available tests and formats |
| `-v` | Enable verbose logging |
