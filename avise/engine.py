"""The SET execution engine for AVISE.

Runs SETs that inherit from BaseSETPipeline and implement the 5-phase pipeline:
initialize() -> execute() -> evaluate() -> report() -> run()
"""

import json
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import sys
import os
import subprocess
import importlib.util
from importlib.resources import files

# Import to register different plugins and SETs
from . import evaluators
from . import connectors
from . import sets


from .registry import connector_registry, set_registry
from .utils import (
    ReportFormat,
    ansi_colors,
    build_output_path,
    detect_terminal_style,
    list_categories,
    render_registry_tree,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_REPORTS_DIR = "avise-reports"

# On Windows, ensure triton-windows package is installed
if os.name == "nt":
    if importlib.util.find_spec("triton") is None:
        logger.warning(
            "triton-windows does not appear to be installed. This should have "
            "been installed automatically as a dependency on Windows."
        )
        try:
            import pip  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "triton-windows is missing and pip is not available in this "
                "environment to install it automatically (this is common with "
                "'uv tool' or 'pipx' installs). Please reinstall the package, "
                "or run: uv tool install <your-package> --with triton-windows"
            )
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "triton-windows"]
            )
        except Exception as e:
            raise RuntimeError(
                "Unable to install triton-windows Python package. "
                "Try: pip install triton-windows"
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
        path = Path(files("avise").joinpath(config_path))
        print(f"new path: {path}")
        if not path.exists():
            path = Path(config_path)
            if not path.exists():
                raise FileNotFoundError(f"Configuration not found from: {config_path}")

        with open(path, "r") as f:
            if path.suffix.lower() in (".yaml", ".yml"):
                config = yaml.safe_load(f)
            elif path.suffix.lower() == ".json":
                config = json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file type: {path.suffix}")

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
        report_format: ReportFormat = ReportFormat.HTML,
        reports_dir: str = DEFAULT_REPORTS_DIR,
        generate_ai_summary: bool = True,
        runs: int = 1,
        output_path: Optional[str] = None,
        target: Optional[str] = None,
        api_key: Optional[str] = None,
        device: Optional[str] = None,
    ) -> dict:
        """Run the 4-phase pipeline

        Args:
            set_name: Registered SET name (e.g., "prompt_injection").
            set_config_path: Path to Security Evaluation Test configuration JSON file.
            connector_config_path: Path to Connector configuration JSON file. Required if using GenericRESTLMConnector.
            output_path: Optional custom output path (overrides date-based).
            report_format: Report format (JSON, HTML, or MARKDOWN).
            reports_dir: Base directory for reports.
            generate_ai_summary: Whether to generate AI-powered summary.
            runs: How many times the SET is ran.

        Returns:
            Report dictionary
        """
        # Load model configuration
        connector_config = self.load_connector_config(connector_config_path)
        # If provided with `target`, override target model from configuration file with it
        if target is not None:
            if "name" in connector_config["target_model"]:
                connector_config["target_model"]["name"] = target
                # TODO: Once there are default connectors for other system/model types than language models,
                # add logic here to replace possible "name" in their config files with `target`.

        # If provided with `api_key`, override api_key from configuration file with it
        if api_key is not None:
            if "api_key" in connector_config["target_model"]:
                connector_config["target_model"]["api_key"] = api_key

        # Create a connector for the target model
        connector = self._build_connector(connector_config, evaluation=False)
        target_model = "None"
        try:
            if "name" in connector_config["target_model"]:
                target_model = connector_config["target_model"]["name"]
            elif "target_modality" in connector_config["target_model"]:
                target_model = connector_config["target_model"]["target_modality"]
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
            runs=runs,
            device=device,
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
        if "_lm" in connector_type:
            connector_kwargs = {"config": connector_config, "evaluation": evaluation}
        else:
            connector_kwargs = {"config": connector_config}
        connector = connector_registry.create(connector_type, **connector_kwargs)

        return connector

    @staticmethod
    def list_available(
        sets: bool = True,
        connectors: bool = True,
        reportformats: bool = True,
        category: Optional[str] = None,
    ) -> bool:
        """Print available Security Evaluation Tests, Report Formats, and Connectors.

        SETs and connectors are grouped by the kind of target system they are for.

        Args:
            sets: Whether to print the available SETs.
            connectors: Whether to print the available connectors.
            reportformats: Whether to print the available report formats.
            category: If given, only show SETs and connectors in this category
                (e.g. "languagemodel" or "single_turn").

        Returns:
            False if ``category`` matched no SET or connector category, else True.
        """
        style = detect_terminal_style()
        listings = []
        if sets:
            listings.append(
                (
                    set_registry,
                    "avise.sets",
                    "Available Security Evaluation Tests",
                    "--SET-list",
                )
            )
        if connectors:
            listings.append(
                (
                    connector_registry,
                    "avise.connectors",
                    "Available Connectors",
                    "--connector-list",
                )
            )

        found = True
        for registry, root_package, title, flag in listings:
            root = registry.grouped(root_package)
            if category:
                filtered = root.filter(category)
                if filtered is None:
                    message = (
                        f"Error: no category matches '{category}'. "
                        f"Available categories: {', '.join(list_categories(root))}"
                    )
                    if style.color:
                        message = f"{ansi_colors['red']}{message}{ansi_colors['reset']}"
                    print("\n" + message)
                    found = False
                    continue
                root = filtered
                hint = f"Showing category '{category}'. Run `avise {flag}` to see all."
            else:
                example = next(root.iter_groups(), None)
                hint = (
                    f"Show a single category with `avise {flag} <category>`, "
                    f"e.g. `avise {flag} {example.key}`."
                    if example
                    else ""
                )
            descriptions = {
                name: getattr(registry.get(name), "description", "")
                for name in registry.list()
            }
            print()
            print(render_registry_tree(root, title, descriptions, style, hint), end="")

        if reportformats:
            title = "Available Report Formats"
            print(
                "\n"
                + (
                    f"{ansi_colors['bold']}{title}{ansi_colors['reset']}"
                    if style.color
                    else title
                )
            )
            for format in ReportFormat:
                print(f"   {format.value}")
        return found

    @staticmethod
    def get_set_registry():
        """Returns SET registry as a list of strings."""
        return set_registry.list()
