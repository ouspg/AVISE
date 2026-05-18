"""Dataclasses for avise/pipelines/continuallearning/pipeline.py

Key differences from other pipeline schemas:
- ContinualLearningSETCase carries an attack configuration and a task sequence.
- ExecutionOutput records per-stage results (inject / drift / query), because CL
  attacks unfold across multiple interaction rounds.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------------------------
# Phase 1 output / Phase 2 input
# ---------------------------------------------------------------------------


@dataclass
class TaskConfig:
    """Configuration for a single task in the CL system's task sequence.

    A task sequence is used both during the injection phase (the task that
    receives poisoned data) and during the drift phase (subsequent benign
    tasks that simulate the model continuing to learn after injection).

    Attributes:
        stage:      "inject" for the poisoned task, "drift" for subsequent benign
                    tasks used to simulate forgetting pressure.
        task_id:    Identifier for the task as recognised by the target system.
        data_path:  Path or URI to the dataset for this task.
        metadata:   Additional task-level parameters forwarded to the connector
                    (e.g. number of epochs, learning rate override).
    """

    stage: str  # e.g. "inject" or "drift"
    task_id: str
    data: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "task_id": self.task_id,
            "data": self.data,
            "metadata": self.metadata,
        }


@dataclass
class ContinualLearningSETCase:
    """Contract: Output of initialize(), input to execute().

    Represents one CL Security Evaluation Test case scenario.

    Attributes:
        id:            Unique identifier for this test case.
        task_sequence: Ordered list of tasks (e.g. inject + drift steps) that will
                       be replayed against the target system.
        metadata:      Arbitrary extra fields (e.g. vulnerability_subcategory)
                       carried through to the final report.
    """

    id: str
    task_sequence: List[TaskConfig] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_sequence": [t.to_dict() for t in self.task_sequence],
            **self.metadata,
        }


# ---------------------------------------------------------------------------
# Phase 2 output / Phase 3 input
# ---------------------------------------------------------------------------


@dataclass
class StageResult:
    """Result of a single stage within the attack execution.

    CL attacks are multi-step (e.g. baseline → inject → drift x N → query), so the
    execution output is structured as an ordered list of StageResults.

    Attributes:
        stage_name:     Human-readable label, e.g. "baseline", "inject", "drift_1",
                        "query".
        stage_index:    Integer index within the execution sequence (0-based).
        metrics:        Dict of numeric measurements captured during this phase,
                        e.g. {"clean_accuracy": 0.91}.
        raw_responses:  Raw API response(s) from the connector, preserved for
                        debugging and auditing.
        error:          Error message if this phase failed; None otherwise.
    """

    stage_name: str
    stage_index: int
    metrics: Dict[str, Any] = field(default_factory=dict)
    raw_responses: List[dict, Any] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "stage_name": self.stage_name,
            "stage_index": self.stage_index,
            "metrics": self.metrics,
            "raw_responses": self.raw_responses,
        }
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class ExecutionOutput:
    """Execution record for a single ContinualLearningSETCase.

    Produced by BaseSETPipeline.execute() for each test case.

    Attributes:
        set_id:          Matches ContinualLearningSETCase.id.
        stage_results:   Ordered list of StageResults covering all execution stages.
        baseline_metrics: Clean accuracy and any other pre-attack measurements captured
                          before any poisoning or such occurs.
        metadata:        Metadata forwarded from ContinualLearningSETCase.
        error:           Top-level error message if the entire execution failed.
    """

    set_id: str
    stage_results: List[StageResult] = field(default_factory=list)
    baseline_metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "set_id": self.set_id,
            "baseline_metrics": self.baseline_metrics,
            "phase_results": [p.to_dict() for p in self.stage_results],
            "metadata": self.metadata,
        }
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class OutputData:
    """Output of execute(), input to evaluate().

    Attributes:
        outputs:          One ExecutionOutput per ContinualLearningSETCase.
        duration_seconds: Wall-clock time for the entire execute() phase.
    """

    outputs: List[ExecutionOutput]
    duration_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outputs": [o.to_dict() for o in self.outputs],
            "duration_seconds": self.duration_seconds,
        }


# ---------------------------------------------------------------------------
# Phase 3 output / Phase 4 input
# ---------------------------------------------------------------------------


@dataclass
class EvaluationResult:
    """Evaluation result for a single test case.

    Produced by BaseSETPipeline.evaluate() for each ExecutionOutput.

    Attributes:
        set_id:              Matches ContinualLearningSETCase.id.
        attack_type:         Copied from ExecutionOutput for quick access.
        status:              "passed"  - target withstood the attack.
                             "failed"  - target was susceptible to the attack.
                             "error"   - execution or evaluation encountered an error.
        reason:              Human-readable explanation for the status.
        detections:          Structured findings produced by individual evaluators.
        baseline_metrics:    Pre-attack metrics forwarded from ExecutionOutput.
        metadata:            Metadata forwarded from ContinualLearningSETCase.
    """

    set_id: str
    attack_type: str
    status: str  # "passed" | "failed" | "error"
    reason: str
    detections: Dict[str, Any] = field(default_factory=dict)
    baseline_metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "set_id": self.set_id,
            "attack_type": self.attack_type,
            "status": self.status,
            "reason": self.reason,
            "detections": self.detections,
            "baseline_metrics": self.baseline_metrics,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Phase 4 output
# ---------------------------------------------------------------------------


@dataclass
class ReportData:
    """Output of the report phase.

    The final report structure that is serialised to the requested format.

    Attributes:
        set_name:               Human-readable name of the SET.
        timestamp:              ISO-8601 UTC timestamp of report generation.
        execution_time_seconds: Duration of the execute() phase.
        summary:                Aggregate statistics (passed & failed cases, pass rate, confidence interval, etc.).
        results:                All EvaluationResults.
        configuration:          Serialised test configuration (connector + SET configs).
        ai_summary:             Optional AI-generated summary.
        group_results:          When True, results are grouped by vulnerability_subcategory
                                in the serialised output.
    """

    set_name: str
    timestamp: str
    execution_time_seconds: Optional[float]
    summary: Dict[str, Any]
    results: List[EvaluationResult]
    configuration: Dict[str, Any] = field(default_factory=dict)
    ai_summary: Optional[Dict[str, Any]] = field(default_factory=dict)
    group_results: bool = True

    def group_by_vulnerability(self) -> Dict[str, List[EvaluationResult]]:
        """Group results by the vulnerability_subcategory metadata field.

        Returns:
            Dict mapping subcategory name to list of EvaluationResults.
        """
        grouped: Dict[str, List[EvaluationResult]] = {}
        for result in self.results:
            group_name = result.metadata.get(
                "vulnerability_subcategory", "Uncategorized"
            )
            grouped.setdefault(group_name, []).append(result)
        return grouped

    def to_dict(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "set_name": self.set_name,
            "timestamp": self.timestamp,
            "execution_time_seconds": self.execution_time_seconds,
            "configuration": self.configuration,
            "summary": self.summary,
        }

        if self.group_results:
            grouped = self.group_by_vulnerability()
            report["set_category"] = {
                group: [r.to_dict() for r in results]
                for group, results in grouped.items()
            }
        else:
            report["results"] = [r.to_dict() for r in self.results]

        if self.ai_summary:
            report["ai_summary"] = self.ai_summary

        return report
