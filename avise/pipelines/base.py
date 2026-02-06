"""
Base class for all vulnerability framework SETs.

All SETs inherit from BasePipeline and should implement all 5 phases:
initialize() -> execute() -> analyze() -> report() -> run()

"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from math import sqrt

from scipy.special import erfinv

from ..connectors.languagemodel.base import BaseConnector

"""
Report formats the user can choose from when running tests
"""

# Defaulttina tässä aina json, josta sitten raporttityökalu taiteilee HTML:n?
# Onko tarvetta MD-versiolle raportista?
class ReportFormat(Enum):
    JSON = "json" 
    HTML = "html"
    MARKDOWN = "md"

@dataclass
class TestCase:
    """
    Contract: Output of initialize(), input to execute().

    ID and prompt are required fields that every test case must contain.
    Additional fields can be added to 'metadata'.
    """
    id: str
    prompt: str
    metadata: Dict[str, Any] = field(default_factory=dict) # New dict created for each instance of TestCase.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            **self.metadata #Unpacks the metadata dictionary
        }


#TODO: Uudelleen nimeä (hox test execution for llms)
@dataclass
class ExecutionOutput:
    """
    Single test execution / output result.

    Produced by execute() for each test case.
    """
    test_id: str # Unique identifier
    prompt: str  # Original test prompt
    response: str # Model response
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None # Error message if execution failed

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "test_id": self.test_id,
            "prompt": self.prompt,
            "response": self.response,
            "metadata": self.metadata
        }
        if self.error:
            result["error"] = self.error
        return result


#TODO: Toimiiko tämä, jos ExecutionOutputia muuttaa?
@dataclass
class OutputData:
    """
    Output of execute(), input to analyze().

    Contains all execution outputs and execution duration in seconds.
    """
    outputs: List[ExecutionOutput]
    duration_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outputs": [output.to_dict() for output in self.outputs],
            "duration": self.duration_seconds
        }

#TODO: Uudelleen nimeys llm
@dataclass
class AnalysisResult:
    """
    Analysis result of a single test

    Produced by analyze() function for each ExecutionOutput.
    """
    test_id: str # Unique identifier
    prompt: str # Original test prompt
    response: str # Model response
    status: str # "passed", "failed", or "error". "pass" or "fail" based on what kind of patterns were found. "Error" if none were found.
    reason: str # Explanation for status
    detections: Dict[str, Any] = field(default_factory=dict) # Analyzer findings. Based on the selected analyzers
    metadata: Dict[str, Any] = field(default_factory=dict)
    elm_evaluation: Optional[str] = None # ELM evaluation result (if evaluation model was used)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "test_id": self.test_id,
            "prompt": self.prompt,
            "response": self.response,
            "status": self.status,
            "reason": self.reason,
            "detections": self.detections,
            "metadata": self.metadata
        }
        if self.elm_evaluation:
            result["elm_evaluation"] = self.elm_evaluation
        return result


@dataclass
class ReportData:
    """
    Output of the report phase / function.

    The final report structure that is serialized to the desired format based on the given command line argument.
    """
    test_name: str
    timestamp: str
    execution_time_seconds: Optional[float]
    summary: Dict[str, Any] # total tests ran, passed%, failed%, error% rates
    results: List[AnalysisResult] # All analysis results
    configuration: Dict[str, Any] = field(default_factory=dict) # Test config

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "timestamp": self.timestamp,
            "execution_time_seconds": self.execution_time_seconds,
            "configuration": self.configuration,
            "summary": self.summary,
            "results": [result.to_dict() for result in self.results]
        }


class BasePipeline(ABC):
    """
    The base class for all the current vulnerability tests.

    Based on a 5-phase pipeline with defined data contracts:

    Phase 1 - initialize(config_path) -> List[TestCase] (Get test configuration from a configuration file and return a list of test cases)
    Phase 2 - execute(connector, tests) -> OutputData (Execute the tests cases against the defined model and return dataobjects for analysis)
    Phase 3 - analyze(execution_data) -> List[AnalysisResult] (Analyze the test results and return analysis objects)
    Phase 4 - report(results, output_path, format) -> ReportData (Take the analysis objects and form a final report in a desired format)
    Phase 5 - run() - Orchestrates all phases 

    Data flow:

    initialize() ---> List[TestCase] ---> execute() ---> OutputData(List[ExecutionOutput, execution_time]) ---> analyze() ---> List[AnalysisObject] ---> report() ---> ReportData

    When new tests are designed, the users override these methods according to their needs
    New analyzers, connectors, loaders, reporters, configurations, and tests can be written and used as long as they follow this pipeline structure.
    """

    name: str = ""
    description: str = ""
    SUPPORTED_FORMATS = [ReportFormat.JSON, ReportFormat.HTML, ReportFormat.MARKDOWN]

    def __init__(self):
        self.test_cases: List[TestCase] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.model_config_path: Optional[str] = None
        self.test_config_path: Optional[str] = None
        self.testable_model_name: Optional[str] = None
        self.evaluation_model_name: Optional[str] = None

    @abstractmethod
    def initialize(self, config_path: str) -> List[TestCase]:
        """
        Load and return test cases from configuration files.

        Args:
            config_path: Path to test configuration file

        Returns:
            List[TestCase]: Test cases used in the test run

        Requirements:
            - Each test case must at least contain an ID and a prompt
            - Additional data related to the tests go to the metadata
        """
        pass

    @abstractmethod
    def execute(
        self,
        connector: BaseConnector,
        tests: List[TestCase]
    ) -> OutputData:
        """
        Run the tests against the target.

        Args:
            connector: A connector instance
            tests: List of test cases from initialize()

        Returns:
            OutputData: All test outputs along with the execution time.

        Requirements:
            - Must produce one ExecutionOutput per TestCase.
            - Metadata from TestCase should be carried through for final report.
            - Errors should be placed to ExecutionOutput.error for later inspection.
        """
        pass

    @abstractmethod
    def analyze(self, execution_data: OutputData) -> List[AnalysisResult]:
        """
        Analyze the test outputs with analyzers.

        Args:
            execution_data: OutputData from execute()

        Returns:
            List[AnalysisResult]: Analysis of each test

        Requirements:
            - Must produce one AnalysisResult per ExecutionOutput
            - Status must be "passed", "failed", or "error" TODO: Something else?
            - Reason should explain the test status. Why did the test pass, fail or cause an error?
        """
        pass

    @abstractmethod
    def report(
        self,
        results: List[AnalysisResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON
    ) -> ReportData:
        """
        Generate the final report in the desired format and save it to target location.

        Args:
            results: List[AnalysisResult] from analyze()
            output_path: Path for output file (../user/reports/..)
            report_format: Report format (Json, Toml, Yaml...) Set to JSON as default.

        Returns:
            ReportData: The final report with all the test data

        Requirements:
            - Must write a report in the requested format to output_path
        """
        pass

    def run(
        self,
        connector: BaseConnector,
        config_path: str,
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
        model_config_path: Optional[str] = None
    ) -> ReportData:
        """
        Orchestration method that executes the 5-phase pipeline.
        This method gets called by the runner / execution engine.

        Args:
            connector: A connector instance
            config_path: Path to the test configuration
            output_path: Path where the output report is written
            report_format: Desired output format
            model_config_path: Path to model configuration (for report metadata)

        Requirements:
            Return the final report
            Calls other class methods with appropriate arguments
        """
        # Store config paths and model name for report
        self.model_config_path = model_config_path
        self.test_config_path = config_path
        self.testable_model_name = connector.model

        # Initialize
        tests = self.initialize(config_path)

        # Execute
        execution_data = self.execute(connector, tests)

        # Analyze
        results = self.analyze(execution_data)

        # Report
        report_data = self.report(results, output_path, report_format)

        return report_data


    @staticmethod
    def build_output_path(
        base_dir: str,
        test_name: str,
        model_name: str,
        report_format: ReportFormat
    ) -> str:
        """
        Helper method for crafting an output path with date-based subdirectory when an output directory is not provided.

        Creates: base_dir/YYYY-MM-DD/test_name_model_timestamp.ext
        """
        time = datetime.now()
        date_dir = time.strftime("%Y-%m-%d")
        timestamp = time.strftime("%H%M%S")
        fixed_model_name = model_name.replace(":", "_").replace("/", "_")
        extension = report_format.value
        filename = f"{test_name}_{fixed_model_name}_{timestamp}.{extension}"
        return str(Path(base_dir) / date_dir / filename)

    @staticmethod
    def calculate_passrates(results: List[AnalysisResult]) -> Dict[str, Any]:
        """
        Calculate summary statistics (pass%, fail%, error%) based on results.

        Helper for report phase. Can be overwritten.
        """
        total_tests = len(results)
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

        if total_tests > 0:
            pass_rate = round(passed / total_tests * 100, 1)
            fail_rate = round(failed / total_tests * 100, 1)
        else:
            pass_rate = 0
            fail_rate = 0
        
        confidence_interval = BasePipeline._calculate_confidence_interval(passed, failed)
        
        return {
            "total_tests": total_tests,
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