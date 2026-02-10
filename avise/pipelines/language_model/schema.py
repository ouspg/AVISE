"""
Dataclasses for avise/pipelines/language_model/pipeline.py
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class LanguageModelSETCase:
    """
    Contract: Output of initialize(), input to execute().

    ID and prompt are required fields that every SET case must contain.
    Additional fields can be added to 'metadata'.
    """
    id: str
    prompt: str
    metadata: Dict[str, Any] = field(default_factory=dict) # New dict created for each instance of LanguageModelSETCase.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            **self.metadata #Unpacks the metadata dictionary
        }


@dataclass
class ExecutionOutput:
    """
    Single test execution / output result.

    Produced by execute() for each test case.
    """
    set_id: str # Unique identifier
    prompt: str  # Original test prompt
    response: str # Model response
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None # Error message if execution failed

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "set_id": self.set_id,
            "prompt": self.prompt,
            "response": self.response,
            "metadata": self.metadata
        }
        if self.error:
            result["error"] = self.error
        return result


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

@dataclass
class AnalysisResult:
    """
    Analysis result of a single test

    Produced by analyze() function for each ExecutionOutput.
    """
    set_id: str # Unique identifier
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
            "set_id": self.set_id,
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
    set_name: str
    timestamp: str
    execution_time_seconds: Optional[float]
    summary: Dict[str, Any]  # total tests ran, passed%, failed%, error% rates
    results: Optional[List[AnalysisResult]] = field(default_factory=list)  # All analysis results, optional
    configuration: Dict[str, Any] = field(default_factory=dict)  # Test config

    def to_dict(self) -> Dict[str, Any]:
        return {
            "set_name": self.set_name,
            "timestamp": self.timestamp,
            "execution_time_seconds": self.execution_time_seconds,
            "configuration": self.configuration,
            "summary": self.summary,
            "results": [result.to_dict() for result in self.results] if self.results else []
        }