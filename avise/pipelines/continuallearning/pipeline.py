"""Base class for all Continual Learning SETs.

All Continual Learning SETs inherit from BaseSETPipeline and must implement
the same 4-phase pipeline as BaseSETPipeline:

    initialize() -> execute() -> evaluate() -> report()

Extending this class
--------------------
Continual Learning SETs (e.g. BackdoorSET, ModelInversionSET) inherit from this class and
override the four abstract methods.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from math import sqrt

from .schema import (
    ContinualLearningSETCase,
    OutputData,
    EvaluationResult,
    ReportData,
)
from ...connectors.continuallearning.base import BaseCLConnector

from scipy.special import erfinv

logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Available report file formats."""

    JSON = "json"
    HTML = "html"
    MARKDOWN = "md"


class BaseSETPipeline(ABC):
    """Base Pipeline class for Continual Learning Security Evaluation Tests.


    Phase 1 - initialize(set_config_path) -> List[ContinualLearningSETCase]
        Load test scenarios from a configuration file.  Each ContinualLearningSETCase
        specifies the attack type, trigger, poison rate, and the task sequence to replay
        against the target.

    Phase 2 - execute(Connector, List[ContinualLearningSETCase]) -> OutputData
        Drive the attack against the target system through the connector.  For
        each ContinualLearningSETCase the orchestrator runs:
            1. Baseline measurement  (clean accuracy before any poisoning)
            2. Injection stage       (submit poisoned data for the target task)
            3. Drift stage           (submit benign tasks to simulate forgetting pressure)
            4. Query stage           (submit triggered samples and record predictions)
        Returns one ExecutionOutput per ContinualLearningSETCase.

    Phase 3 - evaluate(OutputData) -> List[EvaluationResult]
        Apply evaluators to the raw ExecutionOutputs and produce structured
        EvaluationResults, including aggregated metrics (e.g. clean accuracy
        drop, persistence curve) and a pass/fail verdict.

    Phase 4 - report(List[EvaluationResult], output_path, format) -> ReportData
        Serialise the evaluation results to the requested format and write the
        report to disk.
    """

    name: str = ""
    description: str = ""
    SUPPORTED_FORMATS = [ReportFormat.JSON, ReportFormat.HTML, ReportFormat.MARKDOWN]

    def __init__(self) -> None:
        self.set_cases: List[ContinualLearningSETCase] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.connector_config_path: Optional[str] = None
        self.set_config_path: Optional[str] = None
        # Name / metadata of the target system (populated from the connector)
        self.target_system_name: Optional[str] = None
        # Optional evaluation language model (re-used across calls when present)
        self.evaluation_model: Optional[Any] = None

    # ------------------------------------------------------------------
    # Abstract pipeline phases – must be implemented by every subclass
    # ------------------------------------------------------------------

    @abstractmethod
    def initialize(self, set_config_path: str) -> List[ContinualLearningSETCase]:
        """Load and return ContinualLearningSETCases from a configuration file.

        Args:
            set_config_path: Path to the SET configuration file (JSON / YAML).

        Returns:
            List[ContinualLearningSETCase]: All test case scenarios to be executed in this run.

        Requirements:
            - Each ContinualLearningSETCase must have a unique id and at
              least one TaskConfig in its task_sequence.
            - Additional SET case-level metadata (e.g. vulnerability_subcategory,
              description) should be stored in ContinualLearningSETCase.metadata
              so it is carried through to the final report unchanged.
        """
        pass

    @abstractmethod
    def execute(
        self,
        connector: BaseCLConnector,
        set_cases: List[ContinualLearningSETCase],
    ) -> OutputData:
        """Drive the attack stages against the target CL system.

        Args:
            connector: A connector instance that handles connection to the target
                       system by e.g., wrapping the target system's API.
            set_cases: List of ContinualLearningSETCases returned by initialize().

        Returns:
            OutputData: All per-case execution outputs plus the total duration.

        Requirements:
            - Must produce exactly one ExecutionOutput per ContinualLearningSETCase.
            - Each attack stage (e.g. baseline, inject, drift_N, query) must be
              recorded as a separate StageResult within the output.
            - Errors that affect only a single stage should be stored in
              StageResult.error; errors that abort the entire case should be
              stored in ExecutionOutput.error.
            - Metadata from ContinualLearningSETCase must be forwarded to ExecutionOutput so
              it is available in evaluate() and report().
        """
        pass

    @abstractmethod
    def evaluate(
        self,
        execution_data: OutputData,
    ) -> List[EvaluationResult]:
        """Evaluate execution outputs and produce structured results.

        Args:
            execution_data: OutputData returned by execute().

        Returns:
            List[EvaluationResult]: One result per ExecutionOutput.

        Requirements:
            - Must produce exactly one EvaluationResult per ExecutionOutput.
            - status must be one of: "passed", "failed", "error".
              "failed" means the target was susceptible to the attack.
              "passed" means the target withstood the attack.
              "error"  means execution or evaluation encountered an unrecoverable
                       error that prevents a meaningful verdict.
            - reason must explain the status in enough detail to be actionable.
            - SETcase-specific metrics (e.g. clean_accuracy_drop, persistence_curve)
              must be placed in EvaluationResult.metrics.
            - Evaluator-specific findings (e.g. anomaly scores, per-label
              breakdowns) must be placed in EvaluationResult.detections.
        """
        pass

    @abstractmethod
    def report(
        self,
        results: List[EvaluationResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
        generate_ai_summary: bool = True,
    ) -> ReportData:
        """Serialise evaluation results to a report file.

        Args:
            results:             List[EvaluationResult] from evaluate().
            output_path:         Destination path for the report file.
            report_format:       Desired output format (JSON by default).
            generate_ai_summary: Whether to append an AI-generated narrative.

        Returns:
            ReportData: The complete report structure.

        Requirements:
            - Must write a report in the requested format to output_path.
            - The report must include summary statistics from calculate_passrates()
              and calculate_mean_asr().
        """
        pass

    def run(
        self,
        connector: BaseCLConnector,
        set_config_path: str,
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
        connector_config_path: Optional[str] = None,
        generate_ai_summary: bool = True,
        runs: int = 1,
    ) -> ReportData:
        """Execute the full 4-phase pipeline.

        Called by the AVISE execution engine.  Multiple runs are supported to
        account for non-determinism in the target system (e.g. stochastic
        training) and to allow statistical aggregation across runs.

        Args:
            connector:             Connector instance wrapping the target system.
            set_config_path:       Path to the SET configuration file.
            output_path:           Path where the output report is written.
            report_format:         Desired output format.
            connector_config_path: Path to the connector configuration file (for report metadata).
            generate_ai_summary:   Whether to generate an AI narrative summary.
            runs:                  Number of full pipeline repetitions.

        Returns:
            ReportData: The final report covering all runs.
        """
        self.connector_config_path = connector_config_path
        self.set_config_path = set_config_path
        self.target_system_name = getattr(connector, "name", None)

        try:
            cases = self.initialize(set_config_path)

            results: List[EvaluationResult] = []

            for run_index in range(runs):
                logger.info(f"Starting CL SET run {run_index + 1}/{runs}.")

                execution_data = self.execute(connector, cases)
                results += self.evaluate(execution_data)

                logger.info(f"CL SET run {run_index + 1}/{runs} finished.")

            report_data = self.report(
                results, output_path, report_format, generate_ai_summary
            )
            return report_data

        finally:
            # Release any evaluation model held in memory
            if self.evaluation_model is not None:
                if hasattr(self.evaluation_model, "del_model"):
                    self.evaluation_model.del_model()
                self.evaluation_model = None

    def generate_ai_summary(
        self,
        results: List[EvaluationResult],
        summary_stats: Dict[str, Any],
        subcategory_runs: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate an AI narrative summary of the evaluation results.

        Optional helper that can be called during the report phase.  Follows the
        same pattern as BaseSETPipeline.generate_ai_summary for framework
        consistency.

        Args:
            results:          All EvaluationResults for this run.
            summary_stats:    Output of calculate_passrates() and calculate_mean_asr().
            subcategory_runs: Optional mapping of subcategory → number of runs.

        Returns:
            Dict with keys "issue_summary", "recommended_remediations", "notes",
            or None if summary generation failed.
        """
        try:
            from avise.reportgen.summarizers.ai_summarizer import AISummarizer

            model_to_use = self.evaluation_model
            if model_to_use is not None:
                logger.info("Reusing existing evaluation model for AI summary.")
            else:
                logger.info("Creating new model for AI summary.")

            summarizer = AISummarizer(reuse_model=model_to_use)
            results_dict = [r.to_dict() for r in results]
            ai_summary = summarizer.generate_summary(
                results_dict, summary_stats, subcategory_runs
            )
            summarizer.del_model()
            return {
                "issue_summary": ai_summary.issue_summary,
                "recommended_remediations": ai_summary.recommended_remediations,
                "notes": ai_summary.notes,
            }
        except Exception as e:
            logger.error(f"Failed to generate AI summary: {e}")
            return None

    # ------------------------------------------------------------------
    # Statistics helpers
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_passrates(
        results: List[EvaluationResult],
    ) -> Dict[str, Any]:
        """Calculate pass / fail / error rates from evaluation results.

        Args:
            results: All EvaluationResults for the run.

        Returns:
            Dict containing:
                total_set_cases, passed, failed, error,
                pass_rate (%), fail_rate (%),
                ci_lower_bound, ci_upper_bound  (Wilson 95% CI on the pass rate)
        """
        total = len(results)
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        errors = total - passed - failed

        pass_rate = round(passed / total * 100, 1) if total > 0 else 0.0
        fail_rate = round(failed / total * 100, 1) if total > 0 else 0.0

        _, ci_lower, ci_upper = BaseSETPipeline._calculate_confidence_interval(
            passed, failed
        )

        return {
            "total_set_cases": total,
            "passed": passed,
            "failed": failed,
            "error": errors,
            "pass_rate": pass_rate,
            "fail_rate": fail_rate,
            "ci_lower_bound": ci_lower,
            "ci_upper_bound": ci_upper,
        }

    @staticmethod
    def calculate_subcategory_runs(
        results: List[EvaluationResult],
        subcategory_field: str = "vulnerability_subcategory",
    ) -> Dict[str, int]:
        """Return a mapping of vulnerability subcategory → number of runs.

        Args:
            results:           All EvaluationResults for the run.
            subcategory_field: Metadata key for the subcategory label.

        Returns:
            Dict[str, int]: subcategory name → run count.
        """
        counts: Dict[str, int] = {}
        for result in results:
            key = result.metadata.get(subcategory_field, "Unknown")
            counts[key] = counts.get(key, 0) + 1
        return counts

    @staticmethod
    def _calculate_confidence_interval(
        passed: int,
        failed: int,
        confidence_level: float = 0.95,
    ) -> tuple:
        """Wilson score confidence interval for the pass rate.

        Args:
            passed:           Number of "passed" outcomes.
            failed:           Number of "failed" outcomes.
            confidence_level: Desired confidence level (default 0.95).

        Returns:
            Tuple of (proportion, lower_bound, upper_bound).
        """
        n = passed + failed
        if n == 0:
            return (0, 0.0, 0.0)

        p = passed / n
        z = 1.96 if confidence_level == 0.95 else sqrt(2) * erfinv(confidence_level)

        denominator = 1 + (z**2 / n)
        center = (p + (z**2 / (2 * n))) / denominator
        margin = (z / denominator) * sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))

        lower_bound = max(0.0, center - margin)
        upper_bound = min(1.0, center + margin)

        return (p, lower_bound, upper_bound)
