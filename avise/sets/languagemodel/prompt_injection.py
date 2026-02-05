"""
LLM01: Prompt Injection vulnerability Security Evaluation Test.

Implements the 5-phase pipeline for testing prompt injection vulnerabilities
as defined in OWASP LLM Top 10.

All 5 phases are explicitly implemented using data contracts:
initialize() -> execute() -> analyze() -> report() -> run()
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from ...pipelines.base import (
    BasePipeline,
    ReportFormat,
    TestCase,
    ExecutionOutput,
    OutputData,
    AnalysisResult,
    ReportData
)
from ...registry import set_registry
from ...connectors.base import BaseConnector
from ...evaluators.languagemodel import (
    VulnerabilityEvaluator,
    RefusalEvaluator,
    PartialComplianceEvaluator,
    SuspiciousOutputEvaluator
)
from ...reportgen.reporters import JSONReporter, HTMLReporter, MarkdownReporter
from ...utils import ConfigLoader

logger = logging.getLogger(__name__)


@set_registry.register("prompt_injection")
class PromptInjectionTest(BasePipeline):
    """
    An early test written for testing prompt injection vulnerabilities.
    Works as an example of tests that are planned to implemented and designed by using this framework.

    This test implements the complete 5-phase pipeline, showcases how the inherited functions can be overwritten,
    and how different modular components of the framework can be used.
    """

    name = "Prompt Injection"
    description = "Test implementation for testing prompt injection vulnerabilities (OWASP LLM01)"

    def __init__(self):
        """
        Prepare the test object instance, it's dependencies and the tools to be used during the implementation.
        """
        super().__init__()
        self.evaluation_connector: Optional[BaseConnector] = None
        self.evaluation_system_prompt: Optional[str] = None
        self.elm_evaluations: Dict[str, str] = {}

        self.vulnerability_evaluator = VulnerabilityEvaluator()
        self.refusal_evaluator = RefusalEvaluator()
        self.partial_compliance_evaluator = PartialComplianceEvaluator()
        self.suspicious_output_evaluator = SuspiciousOutputEvaluator()

    def initialize(self, config_path: str) -> List[TestCase]:
        """
        Phase 1 of the test pipeline. Load prompt injection test cases from configuration files.

        Args:
            config_path: Path to test configuration file

        Returns:
            List[TestCase]: List of test cases to be used
        """

        logger.info(f"Initializing test: {self.name}")

        config = ConfigLoader().load(config_path)

        self.evaluation_system_prompt = config.get("evaluation_system_prompt")

        tests = config.get("tests", [])
        
        if not tests:
            raise ValueError("No tests found in configuration file.")

        test_cases = []
        for i, test in enumerate(tests):
            if isinstance(test, dict):
                test_cases.append(TestCase(
                    id=test.get("id", f"PI-{i+1}"),
                    prompt=test["prompt"],
                    metadata={
                        "vulnerability_subcategory": test.get("vulnerability_subcategory", "Unknown"),
                        "attack_type": test.get("attack_type", "Unknown"),
                        "expected_behavior": test.get("expected_behavior", "Unknown"),
                    }
                ))
            else:
                test_cases.append(TestCase(
                    id=f"PI-{i+1}",
                    prompt=test,
                    metadata={
                        "vulnerability_subcategory": "Unknown",
                        "attack_type": "Unknown",
                        "expected_behavior": "Unknown",
                    }
                ))

        self.test_cases = test_cases
        logger.info(f"Loaded {len(test_cases)} test cases succesfully")
        return test_cases

    def execute(
        self,
        connector: BaseConnector,
        tests: List[TestCase]
    ) -> OutputData:
        """
        Phase 2 of the testing pipeline. Execute tests against the target model.

        Args:
            connector: Target connector instance
            tests: List[TestCase] from initialize()

        Returns:
            OutputData: All test outputs along with the execution time.
        """
        logger.info(f"Executing {len(tests)} tests")
        self.start_time = datetime.now()

        outputs = []
        self.elm_evaluations = {}

        for i, test in enumerate(tests):
            logger.info(f"Running test {i + 1}/{len(tests)} - [{test.id}]")

            try:
                response = connector.single_turn(test.prompt)

                outputs.append(ExecutionOutput(
                    test_id=test.id,
                    prompt=test.prompt,
                    response=response,
                    metadata=test.metadata
                ))

                # Check if evaluation language model is used
                if self.evaluation_connector and self.evaluation_system_prompt:
                    eval_prompt = f"Original Prompt: {test.prompt}\n\nModel Response: {response}"
                    eval_response = self.evaluation_connector.single_turn_with_system_prompt(
                        eval_prompt,
                        self.evaluation_system_prompt
                    )
                    self.elm_evaluations[test.id] = eval_response

            except Exception as e:
                logger.error(f"Test {test.id} failed with error: {e}")
                outputs.append(ExecutionOutput(
                    test_id=test.id,
                    prompt=test.prompt,
                    response="ERROR: Target failed to respond or an error occured during execution.",
                    metadata=test.metadata,
                    error=str(e)
                ))

        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        # TODO: Use lazy formatting
        logger.info(f"Execution completed in {duration:.1f} seconds")

        return OutputData(
            outputs=outputs,
            duration_seconds=duration
        )

    def analyze(self, execution_data: OutputData) -> List[AnalysisResult]:
        """
        Phase 3 of the testing pipeline. Analyze the responses for prompt injection vulnerabilities.

        Args:
            execution_data: OutputData from execute()

        Returns:
            List[AnalysisResult]: Analysis for each test
        """
        # TODO: Use lazy formatting
        logger.info(f"Analyzing {len(execution_data.outputs)} outputs")
        results = []

        for output in execution_data.outputs:
            if output.error:
                results.append(AnalysisResult(
                    test_id=output.test_id,
                    prompt=output.prompt,
                    response=output.response,
                    status="error",
                    reason=f"Execution error: {output.error}",
                    detections={},
                    metadata=output.metadata
                ))
                continue

            # The outputs are evaluated by the evaluators
            vulnerability_detected, vuln_matches = self.vulnerability_evaluator.detect(output.response)
            refusal_detected, refusal_matches = self.refusal_evaluator.detect(output.response)
            partial_detected, partial_matches = self.partial_compliance_evaluator.detect(output.response)
            suspicious_detected, suspicious_matches = self.suspicious_output_evaluator.detect(output.response)

            detections = {
                "vulnerability": {"detected": vulnerability_detected, "matches": vuln_matches or None},
                "refusal": {"detected": refusal_detected, "matches": refusal_matches or None},
                "partial_compliance": {"detected": partial_detected, "matches": partial_matches or None},
                "suspicious_output": {"detected": suspicious_detected, "matches": suspicious_matches or None},
            }

            # Determine verdict for the test
            status, reason = self.determine_test_status(detections)

            results.append(AnalysisResult(
                test_id=output.test_id,
                prompt=output.prompt,
                response=output.response,
                status=status,
                reason=reason,
                detections=detections,
                metadata=output.metadata
            ))
        # TODO: Use lazy formatting
        logger.info(f"Analysis complete: {len(results)} results")
        return results

    def determine_test_status(self, detections: Dict[str, Any]) -> Tuple[str, str]:
        """
        Determine test status based on detection results.

        Priority: vulnerability > suspicious > partial > refusal > inconclusive
        """
        vulnerability = detections.get("vulnerability", {})
        suspicious = detections.get("suspicious_output", {})
        partial = detections.get("partial_compliance", {})
        refusal = detections.get("refusal", {})

        if vulnerability.get("detected"):
            return ("failed", f"Vulnerability detected: {', '.join(vulnerability.get('matches', []))}")

        if suspicious.get("detected"):
            return ("failed", f"Suspicious output detected: {', '.join(suspicious.get('matches', []))}")

        if partial.get("detected"):
            return ("failed", f"Partial compliance detected: {', '.join(partial.get('matches', []))}")

        if refusal.get("detected"):
            return ("passed", f"Proper refusal detected: {', '.join(refusal.get('matches', []))}")

        return ("error", "Vulnerability analysis inconclusive - Manual review required")

    def report(
        self,
        results: List[AnalysisResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON
    ) -> ReportData:
        """
        Phase 4 of the testing pipeline. Generate a report in the specified format.

        Args:
            results: List[AnalysisResult] from analyze()
            output_path: Path for output file / directory
            report_format: Report format

        Returns:
            ReportData: The final report with all the test data
        """
        # TODO: Use lazy formatting
        logger.info(f"Generating {report_format.value.upper()} report")

        # Attach ELM evaluations to results if ELM was used
        if self.evaluation_connector:
            for result in results:
                if result.test_id in self.elm_evaluations:
                    result.elm_evaluation = self.elm_evaluations[result.test_id]

        # Build ReportData object
        report_data = ReportData(
            test_name=self.name,
            timestamp=datetime.now().strftime("%Y-%m-%d | %H:%M"),
            execution_time_seconds=(
                round((self.end_time - self.start_time).total_seconds(), 1)
                if self.start_time and self.end_time else None
            ),
            summary=self.calculate_passrates(results),
            results=results,
            configuration={
                "model_config": Path(self.model_config_path).name if self.model_config_path else "",
                "test_config": Path(self.test_config_path).name if self.test_config_path else "",
                "testable_model": self.testable_model_name,
                "evaluation_model": self.evaluation_model_name or "",
                "elm_evaluation_used": self.evaluation_connector is not None
            }
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
        # TODO: Use lazy formatting
        logger.info(f"Report written to {output_path}")
        return report_data
