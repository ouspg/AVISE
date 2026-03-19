"""The SET execution engine for AVISE.

Runs SETs that inherit from BaseSETPipeline and implement the 5-phase pipeline:
initialize() -> execute() -> evaluate() -> report() -> run()
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import sys
import os
import subprocess
import importlib.util

# Import to register different plugins and SETs
from . import evaluators
from . import connectors
from . import sets


from .registry import connector_registry, set_registry
from .utils import ReportFormat, build_output_path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_REPORTS_DIR = "reports"

# On Windows, ensure triton-windows package is installed
if os.name == "nt":
    if importlib.util.find_spec("triton-windows") is None:
        logger.info(
            "The current Operating System seems to be Windows. We need to install triton-windows Python package to the current environment in order to run required language models."
        )
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "triton-windows"]
            )
            logger.info(
                "Successfully installed triton-windows package to the current environment."
            )
        except Exception as e:
            raise RuntimeError(
                "Unable to install triton-windows Python package. Cannot run required language models on Windows without it. Try pip install triton-windows"
            ) from e


class ExecutionEngine:
    """Execution Engine."""

    def load_connector_config(self, config_path: str) -> Dict[dict, Any]:
        """Load Connector configuration from JSON file.

        Args:
            config_path: Path to Connector configuration JSON

        Returns:
            Configuration dictionary with contents loaded from the Connector configuration JSON file:
            - target_model (dict):
                - type (str): Type of the target model. E.g. "language_model"
                - name (str): Name of the target model
                - api_url (str): URL of the target model's API endpoint.
                - api_key (str): API authentication key if required by the target API.
            - eval_model (dict): Optional dict with configurations for the evaluation model
                - type (str): Type of the evaluation model. E.g. "language_model"
                - name (str): Name of the evaluation model
                - api_url (str): URL of the the evaluation model's API endpoint.
                - api_key (str): API authentication key if required by the evaluation API.

        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Connector configuration file not found: {config_path}"
            )

        with open(path, "r") as f:
            config = json.load(f)

        # Validate required fields
        if "target_model" not in config:
            raise ValueError("Connector configuration file must contain 'target_model'")

        return config

    def run_test(
        self,
        set_name: str,
        set_config_path: str,
        connector_config_path: str,
        evaluation_model_name: str,
        output_path: Optional[str] = None,
        report_format: ReportFormat = ReportFormat.JSON,
        reports_dir: str = DEFAULT_REPORTS_DIR,
        generate_ai_summary: bool = False,
    ) -> dict:
        """Run the 4-phase pipeline

        Args:
            set_name: Registered SET name (e.g., "prompt_injection")
            set_config_path: Path to Security Evaluation Test configuration JSON file.
            connector_config_path: Path to Connector configuration JSON file. Required if using GenericRESTLMConnector.
            output_path: Optional custom output path (overrides date-based)
            report_format: Report format (JSON, HTML, or MARKDOWN)
            reports_dir: Base directory for reports
            generate_ai_summary: Whether to generate AI-powered summary

        Returns:
            Report dictionary
        """
        # Load model configuration
        connector_config = self.load_connector_config(connector_config_path)

        # Create a connector for the target model
        connector = self._build_connector(connector_config, evaluation=False)

        try:
            target_model = connector_config["target_model"].get("name")
        except AttributeError as e:
            raise RuntimeError(
                'Provided connector configuration file is missing a "target_model" field.'
            ) from e

        logger.info(
            f"Running status check for the target model and API '{target_model}'..."
        )
        try:
            connector.status_check()
            logger.info("Target model status check successful.")
        except ConnectionError as e:
            raise RuntimeError(f"API connection failed with error: {e}") from e
        except ValueError as e:
            raise RuntimeError(f"Model not found: {e}") from e

        set_type = set_registry.get(set_name)
        set_instance = set_type()

        if evaluation_model_name:
            set_instance.evaluation_model_name = evaluation_model_name

        if not output_path:
            output_path = build_output_path(
                base_dir=reports_dir,
                set_name=set_name,
                model_name=target_model,
                report_format=report_format,
            )

        return set_instance.run(
            connector,
            set_config_path,
            output_path,
            report_format,
            connector_config_path=connector_config_path,
            generate_ai_summary=generate_ai_summary,
        )

    def _build_connector(self, connector_config: dict, evaluation: bool = False) -> Any:
        """Helper fundtion to handle building a connector.

        Arguments:
            connector_config: Connector configuration file contents.
            evaluation: if True, build a connector for the evaluation model. If False, build a connector
                  for target model.

        Returns:
            connector: Built connector.
        """
        # Load model configuration
        if evaluation:
            connector_type = connector_config["eval_model"].get(
                "connector", "ollama_lm"
            )
        else:
            connector_type = connector_config["target_model"].get(
                "connector", "ollama_lm"
            )
        connector_kwargs = {"config": connector_config, "evaluation": evaluation}
        connector = connector_registry.create(connector_type, **connector_kwargs)

        return connector

    @staticmethod
    def list_available(
        sets: bool = True, connectors: bool = True, reportformats: bool = True
    ):
        """Print available Security Evaluation Tests, Report Formats, and Connectors.

        Args:
            sets: Boolean flag indicating is available SETs will be printed. Default True.
            connectors: Boolean flag indicating is available Connectors will be printed. Default True.
            reportformats: Boolean flag indicating is available Report Formats will be printed. Default True.
        """
        if sets:
            print("\nAvailable SETs:\n")
            for set_name in set_registry.list():
                set_type = set_registry.get(set_name)
                print(f"   \033[1m{set_name}:\033[0m {set_type.description}\n")
        if reportformats:
            print("\nAvailable Report Formats:")
            for format in ReportFormat:
                print(f"   {format.value}")
        if connectors:
            print("\n Available Connectors:")
            for connector_name in connector_registry.list():
                print(f"   \033[1m{connector_name}\033[0m")
