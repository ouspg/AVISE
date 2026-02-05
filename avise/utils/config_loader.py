"""
Configuration loader for JSON, YAML, and TOML file formats.
"""
import json
import tomllib
import yaml
from pathlib import Path
from typing import Dict, Any, List

from ..pipelines.base import TestCase


class ConfigLoader:
    """
    Loader for configuration files.

    Supports JSON, YAML, and TOML file formats for now.
    Auto-detects format based on file extension.
    """

    SUPPORTED_EXTENSIONS = {
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml"
    }

    def load(self, config_path: str) -> Dict[str, Any]:
        """
        Load test and model configurations from configuration files.

        Auto-detects format based on file extension.

        Args:
            config_path: Path to the configuration file

        Returns:
            Dictionary containing the configuration data
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration not found from: {config_path}")

        extension = path.suffix.lower()
        if extension not in self.SUPPORTED_EXTENSIONS:
            supported = ", ".join(self.SUPPORTED_EXTENSIONS.keys())
            raise ValueError(f"Unsupported format: {extension} detected. Supported formats: {supported}")

        format_type = self.SUPPORTED_EXTENSIONS[extension]

        if format_type == "json":
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        elif format_type == "yaml":
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        elif format_type == "toml":
            with open(path, 'rb') as f:
                return tomllib.load(f)

    def parse_test_cases(
        self,
        config: Dict[str, Any],
        id_prefix: str = "TC"
    ) -> List[TestCase]:
        """
        Parse configuration into TestCase objects.

        Args:
            config: Raw configuration dictionary
            id_prefix: Prefix for auto-generated test IDs

        Returns:
            List of TestCase objects
        """
        tests = config.get("tests", [])
        if not tests:
            raise ValueError("No SETs found in configuration")

        test_cases = []
        for i, test in enumerate(tests):
            if isinstance(test, dict):
                # Extract extra fields as metadata (everything except id and prompt)
                metadata = dict(test)
                metadata.pop("id", None)
                metadata.pop("prompt", None)

                test_cases.append(TestCase(
                    id=test.get("id", f"{id_prefix}-{i+1}"),
                    prompt=test.get("prompt", ""),
                    metadata=metadata
                ))
            elif isinstance(test, str):
                test_cases.append(TestCase(
                    id=f"{id_prefix}-{i+1}",
                    prompt=test,
                    metadata={}
                ))

        return test_cases

    def load_and_parse(
        self,
        config_path: str,
        id_prefix: str = "TC"
    ) -> tuple[List[TestCase], Dict[str, Any]]:
        """
        Load config and parse into test cases.

        Args:
            config_path: Path to the configuration file
            id_prefix: Prefix for auto-generated test IDs

        Returns:
            Tuple of (List[TestCase], raw_config)
        """
        config = self.load(config_path)
        test_cases = self.parse_test_cases(config, id_prefix)
        return test_cases, config
