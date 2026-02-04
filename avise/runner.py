"""
The test runner / execution engine for AVISE.

Runs tests that inherit from BasePipeline and implement the 5-phase pipeline:
initialize() -> execute() -> analyze() -> report() -> run()
"""
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Import to register different plugins and tests
from . import analyzers
from . import connectors
from . import tests

from .registry import connector_registry, test_registry
from .pipelines.base import BasePipeline, ReportFormat

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_REPORTS_DIR = "reports"

class TestRunner:

    def load_model_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load model configuration from JSON file.

        Args:
            config_path: Path to model configuration JSON

        Returns:
            Configuration dictionary with:
            - testable_model (required): Model name for testing
            - connector (optional): Connector type - "ollama" (default) or "openai"
            - api_url (optional): API base URL (required for ollama, optional for openai)
            - api_key (optional): API key for authentication
            - evaluation_model (optional): Model for ELM evaluation
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Model config not found: {config_path}")

        with open(path, 'r') as f:
            config = json.load(f)

        # Validate required fields
        if "testable_model" not in config:
            raise ValueError("Model config must contain 'testable_model'")

        return config

    def run_test(
        self,
        test_name: str,
        model_config_path: str,
        test_config_path: str,
        output_path: Optional[str] = None,
        report_format: ReportFormat = ReportFormat.JSON,
        reports_dir: str = DEFAULT_REPORTS_DIR,
        api_key: Optional[str] = None
    ) -> dict:
        """
        Run the 5-phase pipeline

        Args:
            test_name: Registered test name (e.g., "prompt_injection")
            model_config_path: Path to model configuration JSON
            test_config_path: Path to test configuration JSON
            output_path: Optional custom output path (overrides date-based)
            report_format: Report format (JSON, HTML, or MARKDOWN)
            reports_dir: Base directory for reports
            api_key: Optional API key

        Returns:
            Report dictionary
        """
        # Load model configuration
        model_config = self.load_model_config(model_config_path)
        testable_model = model_config["testable_model"]
        evaluation_model = model_config.get("evaluation_model")
        connector_type = model_config.get("connector", "ollama") #At this stage of development the default is set to ollama. Will be changed.
        api_url = model_config.get("api_url")

        usable_api_key = api_key or model_config.get("api_key")

        # Build connector kwargs based on connector type
        connector_kwargs = {"model": testable_model}
        if usable_api_key:
            connector_kwargs["api_key"] = usable_api_key
        if api_url:
            connector_kwargs["base_url"] = api_url

        # Create a connector for the target model
        connector = connector_registry.create(connector_type, **connector_kwargs)

        logger.info(f"Running health check for the target model and backend '{testable_model}'...")
        try:
            connector.health_check()
            logger.info("Testable model health check successful")
        except ConnectionError as e:
            raise RuntimeError(f"Backend connection failed with error: {e}")
        except ValueError as e:
            raise RuntimeError(f"Model not found: {e}")

        eval_connector = None
        if evaluation_model:
            eval_kwargs = {"model": evaluation_model}
            if usable_api_key:
                eval_kwargs["api_key"] = usable_api_key
            if api_url:
                eval_kwargs["base_url"] = api_url
            eval_connector = connector_registry.create(connector_type, **eval_kwargs)

            logger.info(f"Running health check for evaluation model and backend '{evaluation_model}'...")
            try:
                eval_connector.health_check()
                logger.info("Evaluation model health check successful")
            except ConnectionError as e:
                raise RuntimeError(f"Backend connection failed with error: {e}")
            except ValueError as e:
                raise RuntimeError(f"Evaluation model not found: {e}")

        test_type = test_registry.get(test_name)
        test_instance = test_type()

        if eval_connector:
            test_instance.evaluation_connector = eval_connector
            test_instance.evaluation_model_name = evaluation_model

        if not output_path:
            output_path = BasePipeline.build_output_path(
                base_dir=reports_dir,
                test_name=test_name,
                model_name=testable_model,
                report_format=report_format
            )

        return test_instance.run(
            connector,
            test_config_path,
            output_path,
            report_format,
            model_config_path=model_config_path
        )

    @staticmethod
    def list_available():
        
        print("\nAvailable Tests:")
        for test_name in test_registry.list():
            test_type = test_registry.get(test_name)
            print(f"  - {test_name}: {test_type.description}")

        print("\nAvailable Report Formats:")
        for format in ReportFormat:
            print(f"  - {format.value}")

        print("\n Available Connectors:")
        for connector_name in connector_registry.list():
            print(f"  - {connector_name}")
