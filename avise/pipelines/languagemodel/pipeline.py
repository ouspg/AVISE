
"""
Base class for all vulnerability framework SETs.

All SETs inherit from BaseSETPipeline and should implement all 4 phases:
initialize() -> execute() -> evaluate() -> report()

"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from math import sqrt

from .schema import LanguageModelSETCase, OutputData, EvaluationResult, ReportData
from ...connectors.languagemodel.base import BaseLMConnector
from ...models import EvaluationLanguageModel

from scipy.special import erfinv

class ReportFormat(Enum):
    JSON = "json"
    HTML = "html"
    MARKDOWN = "md"


class BaseSETPipeline(ABC):
    """
    The base Pipeline class for Language Model Security Evaluation Tests.

    Based on a 4-phase pipeline with defined data contracts:

    Phase 1 - initialize(config_path) -> List[LanguageModelSETCase] (Get SET configuration from a configuration file and return a list of SET cases)
    Phase 2 - execute(connector, sets) -> OutputData (Execute the SET cases against the defined model and return dataobjects for evaluation)
    Phase 3 - evaluate(execution_data) -> List[EvaluationResult] (Evaluate the test results and return evaluation objects)
    Phase 4 - report(results, output_path, format) -> ReportData (Take the evaluation objects and form a final report in a desired format
    run() - Runs all phases 

    Data flow:

    initialize() ---> List[LanguageModelSETCase] ---> execute() ---> OutputData(List[ExecutionOutput, execution_time]) ---> evaluate() ---> List[EvaluationResult] ---> report() ---> ReportData

    When new language model SETs are designed, override these methods according to your needs.
    New evaluators, connectors, loaders, reporters, configurations, and SETs can be written and used as long as they follow this pipeline structure.
    """

    name: str = ""
    description: str = ""
    SUPPORTED_FORMATS = [ReportFormat.JSON, ReportFormat.HTML, ReportFormat.MARKDOWN]

    def __init__(self):
        self.set_cases: List[LanguageModelSETCase] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.connector_config_path: Optional[str] = None
        self.set_config_path: Optional[str] = None
        self.target_model_name: Optional[str] = None
        self.target_model_max_tokens: Optional[int] = None
        self.evaluation_model_name: Optional[str] = None
        self.evaluation_model_max_tokens: Optional[int] = None
        self.evaluation_model: Optional[EvaluationLanguageModel] = None

    @abstractmethod
    def initialize(self, set_config_path: str) -> List[LanguageModelSETCase]:
        """
        Load and return SET cases from configuration files.

        Args:
            set_config_path: Path to SET configuration file

        Returns:
            List[LanguageModelSETCase]: SET cases used in the run

        Requirements:
            - Each SET case must at least contain an ID and a prompt
            - Additional data related to the SETs go to the metadata
        """
        pass

    @abstractmethod
    def execute(
        self,
        connector: BaseLMConnector,
        sets: List[LanguageModelSETCase]
    ) -> OutputData:
        """
        Run the SETs against the target.

        Args:
            connector: A connector instance
            sets: List of SET cases from initialize()

        Returns:
            OutputData: All SET outputs along with the execution time.

        Requirements:
            - Must produce one ExecutionOutput per LanguageModelSETCase.
            - Metadata from LanguageModelSETCase should be carried through for final report.
            - Errors should be placed to ExecutionOutput.error for later inspection.
        """
        pass

    @abstractmethod
    def evaluate(self, execution_data: OutputData) -> List[EvaluationResult]:
        """
        Evaluate the SET outputs with evaluators.

        Args:
            execution_data: OutputData from execute()

        Returns:
            List[EvaluationResult]: Evaluation of each SET

        Requirements:
            - Must produce one EvaluationResult per ExecutionOutput
            - Status must be "passed", "failed", or "error" TODO: Something else?
            - Reason should explain the SET status. Why did the SET pass, fail or cause an error?
        """
        pass

    @abstractmethod
    def report(
        self,
        results: List[EvaluationResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON
    ) -> ReportData:
        """
        Generate the final report in the desired format and save it to target location.

        Args:
            results: List[EvaluationResult] from evaluate()
            output_path: Path for output file (../user/reports/..)
            report_format: Report format (Json, Toml, Yaml...) Set to JSON as default.

        Returns:
            ReportData: The final report with all the SET data

        Requirements:ExecutionOutput
            - Must write a report in the requested format to output_path
        """
        pass

    def run(
        self,
        connector: BaseLMConnector,
        set_config_path: str,
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
        connector_config_path: Optional[str] = None
    ) -> ReportData:
        """
        Orchestration method that executes the 4-phase pipeline.
        This method gets called by the execution engine.

        Args:
            connector: A connector instance
            set_config_path: Path to the SET configuration
            output_path: Path where the output report is written
            report_format: Desired output format
            connector_config_path: Path to model configuration (for report metadata)

        Requirements:
            Return the final report
            Calls other class methods with appropriate arguments
        """
        # Store config paths and model name for report
        self.connector_config_path = connector_config_path
        self.set_config_path = set_config_path
        self.target_model_name = connector.model

        # Initialize
        sets = self.initialize(set_config_path)

        # Execute
        execution_data = self.execute(connector, sets)

        # Evaluate
        results = self.evaluate(execution_data)

        # Report
        report_data = self.report(results, output_path, report_format)

        return report_data

    @staticmethod
    def calculate_passrates(results: List[EvaluationResult]) -> Dict[str, Any]:
        """
        Calculate summary statistics (pass%, fail%, error%) based on results.

        Helper for report phase. Can be overwritten.
        """
        total_sets = len(results)
        passed = 0
        failed = 0
        errors = 0

        for result in results:
            if result.status == "passed":
                passed += 1
            elif result.status == "failed":
                failed += 1
            elif result.status == "error":
                errors += 1
            else:
                errors += 1

        if total_sets > 0:
            pass_rate = round(passed / total_sets * 100, 1)
            fail_rate = round(failed / total_sets * 100, 1)
        else:
            pass_rate = 0
            fail_rate = 0
        
        confidence_interval = BaseSETPipeline._calculate_confidence_interval(passed, failed)
        
        return {
            "total_sets": total_sets,
            "passed": passed,
            "failed": failed,
            "error": errors,
            "pass_rate": pass_rate,
            "fail_rate": fail_rate,
            "ci_lower_bound": confidence_interval[1],
            "ci_upper_bound": confidence_interval[2]
        }

    @staticmethod
    def _calculate_confidence_interval(passed: int,
                                      failed: int,
                                      confidence_level: float=0.95
                                      ) -> tuple[int, float, float]:
        """
        Calculate confidence interval for binary data using Wilson score interval.
        
        Arguments:
            passed (int): Number of runs passed.
            failed (int): Number of runs failed.
            confidence_level (float): CI level (default 0.95).
        
        Returns:
            tuple : (proportion, lower_bound, upper_bound)
        """
        n = passed + failed

        if n == 0:
            return (0, 0, 0)

        # Sample proportion
        p = passed / n

        # Z-score for confidence level (1.96 for 95% CI)
        z = 1.96 if confidence_level == 0.95 else sqrt(2) * erfinv(confidence_level)

        # Wilson score interval
        denominator = 1 + (z**2 / n)
        center = (p + (z**2 / (2 * n))) / denominator
        margin = (z / denominator) * sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))

        lower_bound = center - margin
        upper_bound = center + margin

        # Ensure bounds are within [0, 1]
        lower_bound = max(0, lower_bound)
        upper_bound = min(1, upper_bound)

        return (p, lower_bound, upper_bound)
