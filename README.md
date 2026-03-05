
![AVISE logo](/docs/assets/avise_logo.png)

# AVISE - AI Vulnerability Identification & Security Evaluation

A framework for identifying vulnerabilities in and evaluating the security of AI systems.

#### Full Documentations: https://avise.readthedocs.io


### Prerequisites

- Python 3.10+
- Docker (for running models backend)
- pip

### 1. Clone the Repository

```bash
git clone https://github.com/ouspg/AVISE.git
cd AVISE
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

source venv/bin/activate # Or venv/Scripts/Activate on Windows

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
docker exec -it avise-ollama ollama pull <model_name>
```

### 5. Configure Connectors

Edit `avise/configs/connector/ollama.json`:

```json
{
    "target_model": {
        "connector": "ollama-lm",
        "type": "language_model",
        "name": "<NAME_OF_TARGET_MODEL>",
        "api_url": "http://localhost:11434", #Ollama default
        "api_key": null
    }
}
```

## Usage

### Basic usage

```bash
python -m avise --SET <SET_name> --connectorconf <connector_name> [options]
```

For example, you can run the `prompt_injection` Security Evaluation Test on a target model running locally via Ollama with:

```bash
python -m avise --SET prompt_injection --connectorconf ollama
```

### Advanced usage

If you want to use custom configuration files for SETs and/or Connectors, you can do so by giving the paths to the configuration files with `--SETconf` and `--connectorconf` arguments:

```bash
python -m avise --SET prompt_injection --SETconf avise/configs/SET/languagemodel/single_turn/prompt_injection_mini.json --connectorconf avise/configs/connector/ollama.json
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `--SET` | Security Evaluation Test to run (e.g., `prompt_injection`, `context_test`) |
| `--connectorconf` | Path to Connector configuration JSON (Accepts preconfigured connector configuration paths: `ollama`, `openai`, `genericrest`)|


### Optional Arguments

| Argument | Description |
|----------|-------------|
| `--SETconf` | Path to SET configuration JSON file. If not given, uses preconfigured paths for SET config JSON files. |
| `--format`, `-f` | Report format: `json`, `html`, `md` |
| `--output` | Custom output file path |
| `--reports-dir` | Base directory for reports (default: `reports/`) |
| `--list` | List available tests and formats |
| `-verbose` | Enable verbose logging |
| `-version` | Print version  |
