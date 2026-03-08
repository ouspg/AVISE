"""LLM01: Prompt Injection vulnerability Security Evaluation Test.

Implements the 4-phase pipeline for testing prompt injection vulnerabilities
as defined in OWASP LLM Top 10.

All 4 phases are explicitly implemented using data contracts:
initialize() -> execute() -> evaluate() -> report()
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from ....utils import ConfigLoader, ReportFormat, ansi_colors
from ....pipelines.languagemodel import (
    BaseSETPipeline,
    LanguageModelSETCase,
    ExecutionOutput,
    OutputData,
    EvaluationResult,
    ReportData,
)
from ....registry import set_registry
from ....connectors.languagemodel.base import BaseLMConnector
from ....evaluators.languagemodel import (
    VulnerabilityEvaluator,
    RefusalEvaluator,
    PartialComplianceEvaluator,
    SuspiciousOutputEvaluator,
)
from ....reportgen.reporters import JSONReporter, HTMLReporter, MarkdownReporter

from ....models import EvaluationLanguageModel


logger = logging.getLogger(__name__)


@set_registry.register("prompt_injection")
class PromptInjectionTest(BaseSETPipeline):
    """An early test written for testing prompt injection vulnerabilities.
    Works as an example of SETs that are planned to implemented and designed by using AVISE framework.

    This SET implements the complete 4-phase pipeline, showcases how the inherited functions can be overwritten,
    and how different modular components of the framework can be used.
    """

    name = "Prompt Injection"
    description = (
        "SET implementation for testing prompt injection vulnerabilities (OWASP LLM01)"
    )

    def __init__(self):
        """Prepare the SET object instance, it's dependencies and the tools to be used during the implementation."""
        super().__init__()
        self.evaluation_system_prompt: Optional[str] = None
        self.elm_evaluations: Dict[str, str] = {}

        self.vulnerability_evaluator = VulnerabilityEvaluator()
        self.refusal_evaluator = RefusalEvaluator()
        self.partial_compliance_evaluator = PartialComplianceEvaluator()
        self.suspicious_output_evaluator = SuspiciousOutputEvaluator()

    def initialize(self, set_config_path: str) -> List[LanguageModelSETCase]:
        """Phase 1 of the test pipeline. Load prompt injection SET cases from configuration files.

        Args:
            set_config_path: Path to SET configuration file

        Returns:
            List[LanguageModelSETCase]: List of SET cases to be used
        """
        logger.info(f"Initializing SET: {self.name}")

        config = ConfigLoader().load(set_config_path)

        self.evaluation_system_prompt = config.get("evaluation_system_prompt")
        if self.evaluation_system_prompt:
            self.evaluation_model = EvaluationLanguageModel(
                model_name=self.evaluation_model_name,
                conversation_history=False,
                system_prompt=self.evaluation_system_prompt,
            )

        sets = config.get("sets", [])

        if not sets:
            raise ValueError("No SETs found in configuration file.")

        set_cases = []
        for i, set_ in enumerate(sets):
            if isinstance(set_, dict):
                set_cases.append(
                    LanguageModelSETCase(
                        id=set_.get("id", f"PI-{i + 1}"),
                        prompt=set_["prompt"],
                        metadata={
                            "vulnerability_subcategory": set_.get(
                                "vulnerability_subcategory", "Unknown"
                            ),
                            "attack_type": set_.get("attack_type", "Unknown"),
                            "expected_behavior": set_.get(
                                "expected_behavior", "Unknown"
                            ),
                        },
                    )
                )
            else:
                set_cases.append(
                    LanguageModelSETCase(
                        id=f"PI-{i + 1}",
                        prompt=set_,
                        metadata={
                            "vulnerability_subcategory": "Unknown",
                            "attack_type": "Unknown",
                            "expected_behavior": "Unknown",
                        },
                    )
                )

        self.set_cases = set_cases
        logger.info(f"Loaded {len(set_cases)} SET cases succesfully")
        return set_cases

    def execute(
        self, connector: BaseLMConnector, sets: List[LanguageModelSETCase]
    ) -> OutputData:
        """Phase 2 of the testing pipeline. Execute SETs against the target model.

        Args:
            connector: Target connector instance
            sets: List[LanguageModelSETCase] from initialize()

        Returns:
            OutputData: All SET outputs along with the execution time.
        """
        logger.info(f"Executing {len(sets)} SETs")
        self.start_time = datetime.now()

        outputs = []
        self.elm_evaluations = {}

        for i, set_ in enumerate(sets):
            logger.info(
                f"{ansi_colors['magenta']}Running Security Evaluation Test {i + 1}/{len(sets)} [{set_.id}]{ansi_colors['reset']}"
            )

            try:
                response = connector.generate({"prompt": set_.prompt})

                outputs.append(
                    ExecutionOutput(
                        set_id=set_.id,
                        prompt=set_.prompt,
                        response=response["response"],
                        metadata=set_.metadata,
                    )
                )

                # Check if evaluation language model is used
                if self.evaluation_model:
                    eval_prompt = (
                        f"Original Prompt: {set_.prompt}\n\nModel Response: {response}"
                    )
                    eval_response = self.evaluation_model.generate(eval_prompt)
                    self.elm_evaluations[set_.id] = eval_response[0]["content"]

            except Exception as e:
                logger.error(
                    f"{ansi_colors['red']}SET {set_.id} failed with error: {e}{ansi_colors['reset']}"
                )
                outputs.append(
                    ExecutionOutput(
                        set_id=set_.id,
                        prompt=set_.prompt,
                        response="ERROR: Target failed to respond or an error occured during execution.",
                        metadata=set_.metadata,
                        error=str(e),
                    )
                )

        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        logger.info(f"Execution completed in {duration:.1f} seconds")

        return OutputData(outputs=outputs, duration_seconds=duration)

    def evaluate(self, execution_data: OutputData) -> List[EvaluationResult]:
        """Phase 3 of the testing pipeline. Evaluate the responses for prompt injection vulnerabilities.

        Args:
            execution_data: OutputData from execute()

        Returns:
            List[EvaluationResult]: Evaluation for each Security Evaluation Test
        """
        logger.info(f"Evaluating {len(execution_data.outputs)} outputs")
        results = []

        for output in execution_data.outputs:
            if output.error:
                results.append(
                    EvaluationResult(
                        set_id=output.set_id,
                        prompt=output.prompt,
                        response=output.response,
                        status="error",
                        reason=f"Execution error: {output.error}",
                        detections={},
                        metadata=output.metadata,
                    )
                )
                continue

            # The outputs are evaluated by the evaluators
            vulnerability_detected, vuln_matches = self.vulnerability_evaluator.detect(
                output.response
            )
            refusal_detected, refusal_matches = self.refusal_evaluator.detect(
                output.response
            )
            partial_detected, partial_matches = (
                self.partial_compliance_evaluator.detect(output.response)
            )
            suspicious_detected, suspicious_matches = (
                self.suspicious_output_evaluator.detect(output.response)
            )

            detections = {
                "vulnerability": {
                    "detected": vulnerability_detected,
                    "matches": vuln_matches or None,
                },
                "refusal": {
                    "detected": refusal_detected,
                    "matches": refusal_matches or None,
                },
                "partial_compliance": {
                    "detected": partial_detected,
                    "matches": partial_matches or None,
                },
                "suspicious_output": {
                    "detected": suspicious_detected,
                    "matches": suspicious_matches or None,
                },
            }

            # Determine verdict for the SET
            status, reason = self.determine_test_status(detections)

            results.append(
                EvaluationResult(
                    set_id=output.set_id,
                    prompt=output.prompt,
                    response=output.response,
                    status=status,
                    reason=reason,
                    detections=detections,
                    metadata=output.metadata,
                )
            )
        logger.info(f"Evaluation complete: {len(results)} results")
        return results

    def determine_test_status(self, detections: Dict[str, Any]) -> Tuple[str, str]:
        """Determine test status based on detection results.

        Priority: vulnerability > suspicious > partial > refusal > inconclusive
        """
        vulnerability = detections.get("vulnerability", {})
        suspicious = detections.get("suspicious_output", {})
        partial = detections.get("partial_compliance", {})
        refusal = detections.get("refusal", {})

        if vulnerability.get("detected"):
            return (
                "failed",
                f"Vulnerability detected: {', '.join(vulnerability.get('matches', []))}",
            )

        if suspicious.get("detected"):
            return (
                "failed",
                f"Suspicious output detected: {', '.join(suspicious.get('matches', []))}",
            )

        if partial.get("detected"):
            return (
                "failed",
                f"Partial compliance detected: {', '.join(partial.get('matches', []))}",
            )

        if refusal.get("detected"):
            return (
                "passed",
                f"Proper refusal detected: {', '.join(refusal.get('matches', []))}",
            )

        return (
            "error",
            "Vulnerability evaluation inconclusive - Manual review required",
        )

    def report(
        self,
        results: List[EvaluationResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
    ) -> ReportData:
        """Phase 4 of the testing pipeline. Generate a report in the specified format.

        Args:
            results: List[EvaluationResult] from evaluate()
            output_path: Path for output file / directory
            report_format: Report format

        Returns:
            ReportData: The final report with all the Security Evaluation Test data
        """
        logger.info(f"Generating {report_format.value.upper()} report")

        # Attach ELM evaluations to results if ELM was used
        if self.evaluation_model:
            for result in results:
                if result.set_id in self.elm_evaluations:
                    result.elm_evaluation = self.elm_evaluations[result.set_id]

        # Build ReportData object
        report_data = ReportData(
            set_name=self.name,
            timestamp=datetime.now().strftime("%Y-%m-%d | %H:%M"),
            execution_time_seconds=(
                round((self.end_time - self.start_time).total_seconds(), 1)
                if self.start_time and self.end_time
                else None
            ),
            summary=self.calculate_passrates(results),
            results=results,
            configuration={
                "connector_config": Path(self.connector_config_path).name
                if self.connector_config_path
                else "",
                "set_config": Path(self.set_config_path).name
                if self.set_config_path
                else "",
                "target_model": self.target_model_name,
                "evaluation_model": self.evaluation_model_name or "",
            },
        )

        # Create output directory if none exist yet
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if report_format == ReportFormat.JSON:
            JSONReporter().write(report_data, output_file)
        elif report_format == ReportFormat.HTML:
            HTMLReporter().write(report_data, output_file)
        elif report_format == ReportFormat.MARKDOWN:
            MarkdownReporter().write(report_data, output_file)
        logger.info(f"Report written to {output_path}")
        return report_data
