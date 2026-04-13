Installation
=================================

### Prerequisites

- Python 3.10+
- Docker (For Running models locally with Ollama)

### 1. Install AVISE

Install with
- **pip:**
    ```bash
    pip install avise
    ```

- **uv:**

    ```bash
    uv install avise
    ```
    or
    ```bash
    uv tool install avise
    ```

### 2. Run a model

You can use AVISE to evaluate any model accessible via an API by configuring a Connector. In this Quickstart, we will
assume using the Ollama Docker container for running a language model. If you wish to evaluate models deployed in other ways, see
the [Full Documentations](https://avise.readthedocs.io) and available template connector configuration files at `AVISE/avise/configs/connector/languagemodel/` dir of this repository.

#### Running a language model locally with Docker & Ollama

- Clone this repository to your local machine with:

```bash
git clone https://github.com/ouspg/AVISE.git
```

- Create the Ollama Docker container
    - for **GPU** accelerated inference with:
        ```bash
        docker compose -f AVISE/docker/ollama/docker-compose.yml up -d
        ```
    - or for **CPU** inference with:
        ```bash
        docker compose -f AVISE/docker/ollama/docker-compose-cpu.yml up -d
        ```

- Pull an Ollama model to evaluate into the container with:
    ```bash
    docker exec -it avise-ollama ollama pull <model_name>
    ```

### 3. Evaluate the model with a Security Evaluation Test (SET)

#### Basic usage

```bash
avise --SET <SET_name> --connectorconf <connector_name> [options]
```

For example, you can run the `prompt_injection` SET on the model pulled to the Ollama Docker container with:

```bash
avise --SET prompt_injection --connectorconf ollama_lm --target <model_name>
```

To list the available SETs, run the command:
```bash
avise --SET-list
```


## Advanced usage

### Configuring Connectors

You can create your own connector configuration files, or if you cloned the AVISE repository, you can modify the existing connector configuration files in `AVISE/avise/configs/connector/languagemodel/`.

For example, you can edit the default Ollama Connector configuration file `AVISE/avise/configs/connector/languagemodel/ollama.json`, and insert the name of an Ollama model you have pulled to be used as a target by default:

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

Similarly, you can customize the configurations for SETs as well. For example, by editing the Red Queen SET configuration file `AVISE/avise/configs/SET/languagemodel/multi_turn/red_queen.json`,
you can define if the SET is executed incrementally *(the target model will generate a response after each subsequential prompt)*, or as a template *(only works for target systems that accept a conversation as an input)* and if the SET uses and Adversarial Language Model (ALM).
Additionally, you can define the exact template attack prompts that the SET uses:

```json
{
    "incremental_execution": false, #Change to true to execute the SET cases incrementally
    "use_adversarial_languagemodel": false, #Change to true to utilize an Adversarial Language Model (ALM)
    "adversarial_model_device": "auto", # Defines on which device(s) the ALM is loaded to ("cpu", "gpu", or "auto")
    "evaluation_system_prompt": "You are a highly accurate cybersecurity classifier, ..."
    "evaluation_model_device": "auto", # Defines on which device(s) the ELM is loaded to ("cpu", "gpu", or "auto")
    "sets": [
        {
            "id": "RED-QUEEN-001",
            "vulnerability_subcategory": "Evasion Attack",
            "action": "make a fake passport",
            "type": "occupation_teacher",
            "category": "violence,aiding_and_abetting,incitement",
            "conversation": [
                { ... }
            ...
            ]
         },
         ...
    ]
```


If you want to use custom configuration files for SETs and/or Connectors, you can do so by giving the paths to the configuration files with `--SETconf` and `--connectorconf` arguments:

```bash
avise --SET prompt_injection --SETconf AVISE/avise/configs/SET/languagemodel/single_turn/prompt_injection_mini.json --connectorconf AVISE/avise/configs/connector/languagemodel/ollama.json
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `--SET`, `-s` | Security Evaluation Test to run (e.g., `prompt_injection`, `context_test`) |
| `--connectorconf`, `-c` | Path to Connector configuration JSON (Accepts predefined connector configuration paths: `ollama_lm`, `openai_lm`, `genericrest_lm`)|


### Optional Arguments

| Argument | Description |
|----------|-------------|
| `--SETconf` | Path to SET configuration JSON file. If not given, uses preconfigured paths for SET config JSON files. |
| `--target`, `-t` | Name of the target model/system to evaluate. Overrides target name from connector configuration file. |
| `--format`, `-f` | Report format: `json`, `html`, `md` |
| `--runs`, `-r` | How many times each SET is executed |
| `--output` | Custom output file path |
| `--reports-dir` | Base directory for reports (default: `avise-reports/`) |
| `--SET-list` | List available Security Evaluation Tests |
| `--connector-list` | List available Connectors |
| `--verbose`, `-v` | Enable verbose logging |
| `--version`, `-V` | Print version  |
