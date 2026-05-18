"""Base class for Continual Learning evaluators.

Each evaluator is responsible for one focused measurement (e.g. accuracy drop,
trigger stealth, attack success) and returns a structured findings dict alongside
a boolean susceptibility verdict, so multiple evaluators can be composed inside
the evaluate() phase of any BaseCLSETPipeline subclass.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ...pipelines.continuallearning import ExecutionOutput, StageResult

logger = logging.getLogger(__name__)


class BaseCLEvaluator(ABC):
    """Abstract base class for Continual Learning security evaluators.

    Attributes:
        name:        Unique identifier for the evaluator.
        description: Human-readable description of what the evaluator measures.
        threshold:   Primary decision threshold used to determine susceptibility.
                     Subclasses document the exact meaning of this value.
    """

    name: str = ""
    description: str = ""
    threshold: float = 0.0

    @abstractmethod
    def evaluate(
        self,
        execution_output: ExecutionOutput,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Evaluate a single ExecutionOutput and return a susceptibility verdict.

        Args:
            execution_output: The ExecutionOutput produced by execute() for one
                              ContinualLearningSETCase.  Contains baseline_metrics and an ordered
                              list of StageResults (baseline, inject, drift_N, eval).

        Returns:
            Tuple containing:
            - susceptible (bool): True  → the target showed a vulnerability on this
                                          metric.
                                  False → the target was not susceptible, or
                                          insufficient data was available.
            - findings (Dict[str, Any]): Structured measurements and intermediate
                                         values that explain the verdict.  Always
                                         includes an "evaluator" key with self.name
                                         so findings from multiple evaluators can be
                                         merged into EvaluationResult.detections
                                         without collisions.
        """
        pass

    # ------------------------------------------------------------------
    # Shared helper methods
    # ------------------------------------------------------------------

    def _get_stage(
        self,
        execution_output: ExecutionOutput,
        stage_name: str,
    ) -> Optional[StageResult]:
        """Return the first StageResult whose stage_name matches exactly.

        Args:
            execution_output: Output to search.
            stage_name:       Exact name to match (e.g. "baseline", "inject",
                              "eval").

        Returns:
            The matching StageResult, or None if not found.
        """
        for stage in execution_output.stage_results:
            if stage.stage_name == stage_name:
                return stage
        return None

    def _get_drift_stages(
        self,
        execution_output: ExecutionOutput,
    ) -> List[StageResult]:
        """Return all StageResults whose names start with "drift", in index order.

        Args:
            execution_output: Output to search.

        Returns:
            List of drift StageResults sorted by stage_index.
        """
        drift_stages = [
            s
            for s in execution_output.stage_results
            if s.stage_name.startswith("drift")
        ]
        return sorted(drift_stages, key=lambda s: s.stage_index)

    def _get_metric(
        self,
        stage: Optional[StageResult],
        key: str,
        default: Optional[float] = None,
    ) -> Optional[float]:
        """Safely extract a numeric metric from a StageResult.

        Args:
            stage:   StageResult to read from (may be None).
            key:     Metric key within StageResult.metrics.
            default: Value to return when stage is None or key is absent.

        Returns:
            The metric value as a float, or default.
        """
        if stage is None:
            return default
        value = stage.metrics.get(key, default)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.warning(
                f"[{self.name}] Could not convert metric '{key}' value "
                f"'{value}' to float. Returning default."
            )
            return default
