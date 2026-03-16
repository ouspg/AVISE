"""Context test for multi-turn conversations.

Tests if the LLM correctly interpret the conversation context across multiple turns.
The full conversation history is sent with each API call.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from ....pipelines.languagemodel import (
    BaseSETPipeline,
    LanguageModelSETCase,
    ExecutionOutput,
    OutputData,
    EvaluationResult,
    ReportData,
)
from ....registry import set_registry
from ....connectors.languagemodel.base import BaseLMConnector, Message
from ....reportgen.reporters import JSONReporter, HTMLReporter, MarkdownReporter
from ....utils import ConfigLoader, ReportFormat, ansi_colors

logger = logging.getLogger(__name__)


@set_registry.register("context_test")
class ContextTest(BaseSETPipeline):
    """Context Test SET."""

    name = "Context test"
    description = "A simple test for multi-turn conversations where the conversation history is passed to the target"

    def __init__(self):
        super().__init__()
        self.evaluation_connector: Optional[BaseLMConnector] = None

    def initialize(self, set_config_path: str) -> List[LanguageModelSETCase]:
        logger.info(f"Initializing Security Evaluation Test: {self.name}")

        set_config = ConfigLoader().load(set_config_path)

        sets = set_config.get("sets", [])
        if not sets:
            raise ValueError(
                "No Security Evaluation Tests found in the configuration file"
            )

        set_cases = []
        for i, set_ in enumerate(sets):
            set_cases.append(
                LanguageModelSETCase(
                    id=set_.get("id", f"CONTEXT-{i + 1}"),
                    prompt=set_.get("conversation", []),
                    metadata={
                        "expected_in_response": set_.get("expected_in_response", []),
                        "description": set_.get("description", ""),
                    },
                )
            )

        self.set_cases = set_cases
        logger.info(f"Loaded {len(set_cases)} SET cases")
        return set_cases

    def execute(
        self, connector: BaseLMConnector, sets: List[LanguageModelSETCase]
    ) -> OutputData:
        logger.info(f"Executing {len(sets)} context tests")
        self.start_time = datetime.now()

        outputs = []

        for i, set_ in enumerate(sets):
            logger.info(
                f"{ansi_colors['magenta']}Running Security Evaluation Test {i + 1}/{len(sets)} [{set_.id}]{ansi_colors['reset']}"
            )

            try:
                conversation = set_.prompt
                data = {"messages": []}
                final_response = ""

                for turn in conversation:
                    role = turn.get("role", "user")
                    content = turn.get("content", "")

                    if role == "user":
                        data["messages"].append(Message(role="user", content=content))
                        response = connector.generate(data, multi_turn=True)
                        data["messages"].append(
                            Message(role="assistant", content=response["response"])
                        )
                        final_response = response["response"]
                    elif role == "system":
                        data["messages"].insert(
                            0, Message(role="system", content=content)
                        )

                outputs.append(
                    ExecutionOutput(
                        set_id=set_.id,
                        prompt=set_.prompt,
                        response=final_response,
                        metadata={
                            **set_.metadata,
                            "full_conversation": [
                                {"role": m.role, "content": m.content}
                                for m in data["messages"]
                            ],
                        },
                    )
                )

            except Exception as e:
                logger.error(
                    f"{ansi_colors['red']}Security Evaluation Test {set_.id} failed: {e}{ansi_colors['reset']}"
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

            expected = output.metadata.get("expected_in_response", [])
            response_lower = output.response.lower()

            found = []
            missing = []
            for item in expected:
                if item.lower() in response_lower:
                    found.append(item)
                else:
                    missing.append(item)

            detections = {"expected": expected, "found": found, "missing": missing}

            if not expected:
                status = "error"
                reason = "No expected values defined for this test"
            elif len(missing) == 0:
                status = "passed"
                reason = f"Context interpreted correctly: found all expected items ({', '.join(found)})"
            elif len(found) > 0:
                status = "failed"
                reason = (
                    f"Partial context interpretation: found {found}, missing {missing}"
                )
            else:
                status = "failed"
                reason = f"Context interpretation failed: none of {expected} found in response"

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

    def report(
        self,
        results: List[EvaluationResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
        generate_ai_summary: bool = False,
    ) -> ReportData:
        logger.info(f"Generating {report_format.value.upper()} report")

        summary_stats = self.calculate_passrates(results)

        ai_summary = None
        if generate_ai_summary:
            logger.info("Generating AI summary...")
            ai_summary = self.generate_ai_summary(
                results,
                summary_stats,
                self.connector_config_path,
            )
            if ai_summary:
                logger.info("AI summary generated successfully")
            else:
                logger.warning("AI summary generation failed")

        report_data = ReportData(
            set_name=self.name,
            timestamp=datetime.now().strftime("%Y-%m-%d | %H:%M"),
            execution_time_seconds=(
                round((self.end_time - self.start_time).total_seconds(), 1)
                if self.start_time and self.end_time
                else None
            ),
            summary=summary_stats,
            results=results,
            configuration={
                "model_config": Path(self.connector_config_path).name
                if self.connector_config_path
                else "",
                "set_config": Path(self.set_config_path).name
                if self.set_config_path
                else "",
                "target_model": self.target_model_name,
                "evaluation_model": self.evaluation_model_name or "",
                "elm_evaluation_used": self.evaluation_connector is not None,
            },
            ai_summary=ai_summary,
        )
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
