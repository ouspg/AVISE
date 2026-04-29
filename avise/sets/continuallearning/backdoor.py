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


@set_registry.register("red_queen")
class Backdoor(BaseSETPipeline):
    """Backdoor SET."""

    name = "Backdoor"
    description = "TODO:"

    def __init__(self):
        super().__init__()


# In the execution phase, allow user to configure if manual continuing of the execution is
# required or not (e.g. Press y to continue after a stage has executed).
