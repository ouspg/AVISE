"""
Configuration loader for JSON, YAML, and TOML file formats.
"""
import json
import tomllib
import yaml
from pathlib import Path
from typing import Dict, Any, List

from ..pipelines.languagemodel import LanguageModelSETCase


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

    def parse_set_cases(
        self,
        config: Dict[str, Any],
        id_prefix: str = "TC"
    ) -> List[LanguageModelSETCase]:
        """
        Parse configuration into LanguageModelSETCase objects.

        Args:
            config: Raw configuration dictionary
            id_prefix: Prefix for auto-generated SET IDs

        Returns:
            List of LanguageModelSETCase objects
        """
        sets = config.get("sets", [])
        if not sets:
            raise ValueError("No SETs found in configuration")

        set_cases = []
        for i, set_ in enumerate(sets):
            if isinstance(set_, dict):
                # Extract extra fields as metadata (everything except id and prompt)
                metadata = dict(set_)
                metadata.pop("id", None)
                metadata.pop("prompt", None)

                set_cases.append(LanguageModelSETCase(
                    id=set_.get("id", f"{id_prefix}-{i+1}"),
                    prompt=set_.get("prompt", ""),
                    metadata=metadata
                ))
            elif isinstance(set_, str):
                set_cases.append(LanguageModelSETCase(
                    id=f"{id_prefix}-{i+1}",
                    prompt=set_,
                    metadata={}
                ))

        return set_cases

    def load_and_parse(
        self,
        config_path: str,
        id_prefix: str = "LM-SETCase"
    ) -> tuple[List[LanguageModelSETCase], Dict[str, Any]]:
        """
        Load config and parse into test cases.

        Args:
            config_path: Path to the configuration file
            id_prefix: PrefiExecutionOutx for auto-generated test IDs

        Returns:
            Tuple of (List[LanguageModelSETCase], raw_config)
        """
        config = self.load(config_path)
        set_cases = self.parse_set_cases(config, id_prefix)
        return set_cases, config
