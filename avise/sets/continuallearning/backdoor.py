"""Backdoor Security Evaluation Test.

Todo:
"""

import logging
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
        self.set_data_already_poisoned = set_config.get("set_data_already_poisoned", False)
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
                    f"{ansi_colors['yellow']}No task sequence configured for {case.get("id", f"BACKDOOR-{i + 1}")} case in Backdoor SET configuration file: {set_config_path}. Skipping this case.{ansi_colors['reset']}"
                )
                continue
            for task in task_sequence:
                data = task.get("data", [])
                if not data:
                    logger.warning(
                        f"{ansi_colors['yellow']}The data field of a task in task sequence of {case.get("id", f"BACKDOOR-{i + 1}")} case in Backdoor SET configuration file: {set_config_path} is empty. Data should be a list of data, or a path to data file. Skipping this case.{ansi_colors['reset']}"
                    )
                    skip = True
                    break
                if not isinstance(data, (str, list)):
                    logger.warning(
                        f"{ansi_colors['yellow']}Data misconfigured for a task in task sequence of {case.get("id", f"BACKDOOR-{i + 1}")} case in Backdoor SET configuration file: {set_config_path}. Data should be a list of data, or a path to data file. Skipping this case.{ansi_colors['reset']}"
                    )
                    skip = True
                    break
                tasks.append(TaskConfig(stage=task.get("task_stage", "drift"), id=task.get("task_id", ""), data=data))
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

    def execute(self, connector: BaseCLConnector, set_cases: List[ContinualLearningSETCase]) -> OutputData:
        # In the execution phase, allow user to configure if manual continuing of the execution is
        # required or not (e.g. Press y to continue after a stage has executed).

        # if task data is path, load the data from a file
        # if task is a list, use as is

        pass
    def evaluate(self, execution_data: OutputData) -> List[EvaluationResult]:
        pass
    def report(self, results: List[EvaluationResult]) -> ReportData:


