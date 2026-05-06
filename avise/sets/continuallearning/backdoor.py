"""Backdoor Security Evaluation Test.

Todo:
"""

import logging
import click
import csv
import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict

from ...pipelines.continuallearning import (
    BaseSETPipeline,
    ContinualLearningSETCase,
    TaskConfig,
    ExecutionOutput,
    OutputData,
    EvaluationResult,
    ReportData,
)

from ...registry import set_registry
from ...connectors.continuallearning.base import BaseCLConnector
from ...reportgen.reporters import JSONReporter, HTMLReporter, MarkdownReporter
from ...utils import ConfigLoader, ReportFormat, ansi_colors

logger = logging.getLogger(__name__)


@set_registry.register("cl_backdoor")
class Backdoor(BaseSETPipeline):
    """Backdoor SET."""

    name = "Backdoor"
    description = "Injects a backdoor into a Continual Learning model."

    def __init__(self):
        super().__init__()
        self.modality: str = "numerical"
        self.target_label: str = "BackdoorTriggered"
        self.source_label: str = ""
        self.trigger_type: str = "feature_perturbation"
        self.poison_rate: float = 0.05
        self.set_data_already_poisoned: bool = False
        self.manual_stage_progression: bool = True

    def initialize(self, set_config_path: str) -> List[ContinualLearningSETCase]:
        logger.info(f"Initializing Security Evaluation Test: {self.name}")

        # Load configurations from the configuration file
        set_config = ConfigLoader().load(set_config_path)
        set_cases = set_config.get("set_cases", [])
        if not set_cases:
            raise ValueError(
                f'No Security Evaluation Test cases ("set_cases" field) found in the Backdoor SET configuration file: {set_config_path}'
            )
        if not isinstance(set_cases, list):
            raise TypeError(
                f'"set_cases" must be a list in the Backdoor SET configuration file: {set_config_path}'
            )
        self.modality = set_config.get("target_modality", "")
        if not self.modality:
            raise ValueError(
                f'"target_modality" is not configured in the Backdoor SET configuration file: {set_config_path}'
            )
        if not isinstance(self.modality, str):
            raise TypeError(
                f'"target_modality" must be a string in the Backdoor SET configuration file: {set_config_path}'
            )
        self.source_label = set_config.get("source_label", "")
        if not self.source_label:
            raise ValueError(
                f'"source_label" is not configured in the Backdoor SET configuration file: {set_config_path}'
            )
        if not isinstance(self.source_label, str):
            raise TypeError(
                f'"source_label" must be a str in the Backdoor SET configuration file: {set_config_path}'
            )
        self.trigger_type = set_config.get("trigger_type", "feature_perturbation")
        if not isinstance(self.trigger_type, str):
            raise TypeError(
                f'"trigger_type" must be a str in the Backdoor SET configuration file: {set_config_path}'
            )
        self.poison_rate = set_config.get("poison_rate", 0.05)
        if not isinstance(self.poison_rate, (float, int)):
            raise TypeError(
                f'"poison_rate" must be a float in the Backdoor SET configuration file: {set_config_path}'
            )
        if self.poison_rate < 0 or self.poison_rate > 1:
            raise ValueError(
                f'"poison_rate" must be a float in range [0, 1] in the Backdoor SET configuration file: {set_config_path}'
            )
        self.target_label = set_config.get("target_label", "BackdoorTriggered")
        if not isinstance(self.target_label, str):
            raise TypeError(
                f'"target_label" must be a float in the Backdoor SET configuration file: {set_config_path}'
            )
        self.set_data_already_poisoned = set_config.get(
            "set_data_already_poisoned", False
        )
        if not isinstance(self.set_data_already_poisoned, bool):
            raise TypeError(
                f'"set_data_already_poisoned" must be a bool (true or false) in the Backdoor SET configuration file: {set_config_path}'
            )
        self.manual_stage_progression = set_config.get("human_in_the_loop", True)
        if not isinstance(self.manual_stage_progression, bool):
            raise TypeError(
                f'"human_in_the_loop" must be a bool (true or false) in the Backdoor SET configuration file: {set_config_path}'
            )

        # Format loaded SET cases into ContinualLearningSETCase objects.
        cases = []
        for i, case in enumerate(set_cases):
            skip = False
            tasks = []
            task_sequence = case.get("task_sequence", [])
            if not task_sequence:
                logger.warning(
                    f"{ansi_colors['yellow']}No task sequence configured for {case.get('id', f'BACKDOOR-{i + 1}')} case in Backdoor SET configuration file: {set_config_path}. Skipping this case.{ansi_colors['reset']}"
                )
                continue
            for task in task_sequence:
                data = task.get("data", [])
                if not data:
                    logger.warning(
                        f"{ansi_colors['yellow']}The data field of a task in task sequence of {case.get('id', f'BACKDOOR-{i + 1}')} case in Backdoor SET configuration file: {set_config_path} is empty. Data should be a list of data, or a path to data file. Skipping this case.{ansi_colors['reset']}"
                    )
                    skip = True
                    break
                if not isinstance(data, (str, list)):
                    logger.warning(
                        f"{ansi_colors['yellow']}Data misconfigured for a task in task sequence of {case.get('id', f'BACKDOOR-{i + 1}')} case in Backdoor SET configuration file: {set_config_path}. Data should be a list of data, or a path to data file. Skipping this case.{ansi_colors['reset']}"
                    )
                    skip = True
                    break
                tasks.append(
                    TaskConfig(
                        stage=task.get("task_stage", "drift"),
                        task_id=task.get("task_id", ""),
                        data=data,
                    )
                )
            if skip:
                continue
            cases.append(
                ContinualLearningSETCase(
                    id=case.get("id", f"BACKDOOR-{i + 1}"),
                    task_sequence=tasks,
                    metadata={
                        "vulnerability_subcategory": case.get(
                            "vulnerability_subcategory", "Uncategorized"
                        )
                    },
                )
            )

        self.set_cases = cases
        logger.info(f"Loaded {len(cases)} SET cases")
        return cases

    def execute(
        self, connector: BaseCLConnector, set_cases: List[ContinualLearningSETCase]
    ) -> OutputData:
        logger.info(f"Executing {len(set_cases)} Continual Learning Backdoor SET cases")
        self.start_time = datetime.now()

        outputs = []

        for i, case in enumerate(set_cases):
            logger.info(
                f"{ansi_colors['magenta']}Running Security Evaluation Test case {i + 1}/{len(set_cases)} [{case.id}]{ansi_colors['reset']}"
            )
            stage_results = []
            baseline_metrics = {}

            try:
                for j, task in enumerate(case.task_sequence):
                    # If task data is in a file, load it into a list
                    data = (
                        self._load_file(task.data)
                        if isinstance(task.data, str)
                        else task.data
                    )
                    # Query the target model
                    task_type = "train" if task.stage == "inject" else "inference"
                    response = connector.query(data=data, task=task_type)
                    # Append response to stage_results
                    stage_results.append(response)
                    # TODO: Calculate baseline metrics here

                    # If configured to include human-in-the-loop, check model weight status from user
                    if j != (len(case.task_sequence) - 1):
                        if self.manual_stage_progression:
                            click.echo(
                                f"\n--- Stage {j + 1}/{len(case.task_sequence) - 1} of current SET case complete ---"
                            )
                            click.echo(
                                "Action required: update the target model to the latest weights."
                            )
                            click.confirm(
                                "Confirm model weights have been updated before proceeding to the next stage. Continue?",
                                default=True,
                                abort=True,
                            )
                            logger.info(
                                "Model weight update confirmed. Continuing to the next stage..."
                            )
            except Exception as e:
                logger.error(
                    f"{ansi_colors['red']}Security Evaluation Test {case.id} failed: {e}{ansi_colors['reset']}",
                    exc_info=True,
                )
                outputs.append(
                    ExecutionOutput(
                        set_id=case.id,
                        stage_results=stage_results,
                        baseline_metrics=baseline_metrics,
                        metadata=case.metadata,
                        error=str(e),
                    )
                )
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        logger.info(f"Execution completed in {duration:.1f} seconds")

        return OutputData(outputs=outputs, duration_seconds=duration)

    def _load_file(self, filepath: str) -> list:
        """Loads data from a file into a list.

        Supported formats:
            .txt        — one item per line
            .csv        — list of dicts (one per row)
            .tsv        — list of dicts (one per row, tab-separated)
            .json       — parsed JSON (wrapped in list if not already)
            .jsonl      — list of parsed JSON objects (one per line)
            .xml        — list of child elements under root
            .yaml/.yml  — parsed YAML (wrapped in list if not already)
            .xlsx/.xls  — list of dicts (one per row)
            .parquet    — list of row dicts
            .pkl        — unpickled object (wrapped in list if not already)

        Args:
            filepath: Path to the file.

        Returns:
            A list containing the loaded data.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is unsupported.
        """
        path = Path(filepath)

        if not path.exists():
            raise FileNotFoundError(
                f"Backdoor SET case task data file not found: {filepath}"
            )

        ext = path.suffix.lower()

        # .txt — one item per line
        if ext == ".txt":
            with open(path, "r", encoding="utf-8") as f:
                return [line.rstrip("\n") for line in f]

        # .csv — list of row dicts
        elif ext == ".csv":
            with open(path, "r", encoding="utf-8", newline="") as f:
                return list(csv.DictReader(f))

        # .tsv — list of row dicts (tab-separated)
        elif ext == ".tsv":
            with open(path, "r", encoding="utf-8", newline="") as f:
                return list(csv.DictReader(f, delimiter="\t"))

        # .json — parsed JSON, normalised to a list
        elif ext == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]

        # .jsonl — one JSON object per line
        elif ext == ".jsonl":
            with open(path, "r", encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]

        # .xml — list of child elements under root
        elif ext == ".xml":
            from xml.etree import ElementTree as ET

            tree = ET.parse(path)
            return list(tree.getroot())

        # .yaml / .yml
        elif ext in (".yaml", ".yml"):
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, list) else [data]

        # .xlsx / .xls — list of row dicts
        elif ext in (".xlsx", ".xls"):
            import openpyxl

            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0]
            return [dict(zip(headers, row)) for row in rows[1:]]

        # .parquet — list of row dicts
        elif ext == ".parquet":
            import pandas as pd

            return pd.read_parquet(path).to_dict(orient="records")

        # .pkl — unpickled object, normalised to a list
        elif ext == ".pkl":
            with open(path, "rb") as f:
                data = pickle.load(f)
                return data if isinstance(data, list) else [data]

        else:
            raise ValueError(
                f"Unsupported file type for CL Backdoor SET case task data: '{ext}'"
            )

    def evaluate(self, execution_data: OutputData) -> List[EvaluationResult]:
        pass

    def report(
        self,
        results: List[EvaluationResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
        generate_ai_summary: bool = True,
    ) -> ReportData:
        pass
