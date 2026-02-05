"""
Context test for multi-turn conversations.

Tests if the LLM correctly interpret the conversation context across multiple turns.
The full conversation history is sent with each API call.
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

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
from ...connectors.base import BaseConnector, Message
from ...reportgen.reporters import JSONReporter, HTMLReporter, MarkdownReporter
from ...utils import ConfigLoader

logger = logging.getLogger(__name__)

@set_registry.register("context_test")
class ContextTest(BasePipeline):

    name = "Context test"
    description = "A simple test for multi-turn conversations where the conversation history is passed to the target"

    def __init__(self):
        super().__init__()
        self.evaluation_connector: Optional[BaseConnector] = None


    def initialize(self, config_path: str) -> List[TestCase]:
        #TODO: Change to lazy formatting (improves run time, reduces compute)
        logger.info(f"Initializing test: {self.name}")

        config = ConfigLoader().load(config_path)

        tests = config.get("tests", [])
        if not tests:
            raise ValueError("No tests found in the configuration file")

        test_cases = []
        for i, test in enumerate(tests):
            test_cases.append(TestCase(
                id=test.get("id", f"CONTEXT-{i+1}"),
                prompt=test.get("description", "Context test"),
                metadata={
                    "conversation": test.get("conversation", []),
                    "expected_in_response": test.get("expected_in_response", []),
                    "description": test.get("description", "")
                }
            ))

        self.test_cases = test_cases
        #TODO: Change to lazy formatting (improves run time, reduces compute)
        logger.info(f"Loaded {len(test_cases)} test cases")
        return test_cases

    def execute(
        self,
        connector: BaseConnector,
        tests: List[TestCase]
    ) -> OutputData:
        #TODO: Change to lazy formatting (improves run time, reduces compute)
        logger.info(f"Executing {len(tests)} context tests")
        self.start_time = datetime.now()

        outputs = []

        for i, test in enumerate(tests):
            #TODO: Change to lazy formatting (improves run time, reduces compute)
            logger.info(f"Running test {i + 1}/{len(tests)} [{test.id}]")

            try:
                conversation = test.metadata.get("conversation", [])
                messages: List[Message] = []
                final_response = ""

                for turn in conversation:
                    role = turn.get("role", "user")
                    content = turn.get("content", "")

                    if role == "user":
                        messages.append(Message(role="user", content=content))
                        response = connector.multi_turn(messages, max_tokens=256)
                        messages.append(Message(role="assistant", content=response))
                        final_response = response
                    elif role == "system":
                        messages.insert(0, Message(role="system", content=content))

                outputs.append(ExecutionOutput(
                    test_id=test.id,
                    prompt=test.prompt,
                    response=final_response,
                    metadata={
                        **test.metadata,
                        "full_conversation": [
                            {"role": m.role, "content": m.content}
                            for m in messages
                        ]
                    }
                ))

            except Exception as e:
                #TODO: Change to lazy formatting (improves run time, reduces compute)
                logger.error(f"Test {test.id} failed: {e}")
                outputs.append(ExecutionOutput(
                    test_id=test.id,
                    prompt=test.prompt,
                    response="ERROR: Target failed to respond or an error occured during execution.",
                    metadata=test.metadata,
                    error=str(e)
                ))

        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        #TODO: Change to lazy formatting (improves run time, reduces compute)
        logger.info(f"Execution completed in {duration:.1f} seconds")

        return OutputData(
            outputs=outputs,
            duration_seconds=duration
        )

    def analyze(self, execution_data: OutputData) -> List[AnalysisResult]:
        #TODO: Change to lazy formatting (improves run time, reduces compute)
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

            expected = output.metadata.get("expected_in_response", [])
            response_lower = output.response.lower()

            found = []
            missing = []
            for item in expected:
                if item.lower() in response_lower:
                    found.append(item)
                else:
                    missing.append(item)

            detections = {
                "expected": expected,
                "found": found,
                "missing": missing
            }

            if not expected:
                status = "error"
                reason = "No expected values defined for this test"
            elif len(missing) == 0:
                status = "passed"
                reason = f"Context interpreted correctly: found all expected items ({', '.join(found)})"
            elif len(found) > 0:
                status = "failed"
                reason = f"Partial context interpretation: found {found}, missing {missing}"
            else:
                status = "failed"
                reason = f"Context interpretation failed: none of {expected} found in response"

            results.append(AnalysisResult(
                test_id=output.test_id,
                prompt=output.prompt,
                response=output.response,
                status=status,
                reason=reason,
                detections=detections,
                metadata=output.metadata
            ))
        #TODO: Change to lazy formatting (improves run time, reduces compute)
        logger.info(f"Analysis complete: {len(results)} results")
        return results

    def report(
        self,
        results: List[AnalysisResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON
    ) -> ReportData:
        #TODO: Change to lazy formatting (improves run time, reduces compute)
        logger.info(f"Generating {report_format.value.upper()} report")

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
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if report_format == ReportFormat.JSON:
            JSONReporter().write(report_data, output_file)
        elif report_format == ReportFormat.HTML:
            HTMLReporter().write(report_data, output_file)
        elif report_format == ReportFormat.MARKDOWN:
            MarkdownReporter().write(report_data, output_file)
        #TODO: Change to lazy formatting (improves run time, reduces compute)
        logger.info(f"Report written to {output_path}")
        return report_data
