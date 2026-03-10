.. building_pipeline:

Building a BaseSETPipeline
=================================

A ``BaseSETPipeline`` defines the execution flow and data contracts for a specific *type* of target
system. All Security Evaluation Tests (SETs) that target that system type inherit from the
corresponding ``BaseSETPipeline``. For example, all language model SETs inherit from
``pipelines.languagemodel.BaseSETPipeline``.

In this guide, we will walk through how the ``pipelines.languagemodel.BaseSETPipeline`` was designed
and built — covering the data schema, the abstract pipeline class, the four-phase execution model,
and the built-in helper utilities.

.. note::

   If you are looking for a guide on how to **use** an existing pipeline to build a SET rather
   than creating a new pipeline from scratch, see :ref:`building_set` instead. You only need to
   build a new ``BaseSETPipeline`` if no suitable pipeline already exists under ``avise/pipelines/``
   for the type of target system you want to evaluate.

Overview: The 4-Phase Pipeline
-------------------------------

Every ``BaseSETPipeline`` enforces a strict execution model with well-defined data
contracts between phases. This ensures that any SET built on top of the pipeline is consistent,
testable, and interoperable with the rest of the framework.

.. code:: text
   :caption: 4 phases of the ``pipelines.languagemodel.BaseSETPipeline``

    initialize() ──► List[LanguageModelSETCase]
         │
         ▼
    execute() ──────► OutputData(List[ExecutionOutput], duration_seconds)
         │
         ▼
    evaluate() ─────► List[EvaluationResult]
         │
         ▼
    report() ───────► ReportData

Each phase takes the output of the previous phase as its input. The ``run()`` method on the base
class orchestrates all four phases in sequence. Concrete SETs override each phase with their own
logic, while the orchestration and helper utilities are provided by the base class.

For clarity, here are the packages used in the construction of the pipeline:

.. code:: python
   :caption: Imported packages used in the creation of the BaseSETPipeline.

    from abc import ABC, abstractmethod
    from enum import Enum
    from typing import List, Dict, Any, Optional
    from datetime import datetime
    from math import sqrt

    from .schema import LanguageModelSETCase, OutputData, EvaluationResult, ReportData
    from ...connectors.languagemodel.base import BaseLMConnector
    from ...models import EvaluationLanguageModel

    from scipy.special import erfinv

* ``abc.ABC``, ``abstractmethod``: Used to declare ``BaseSETPipeline`` as an abstract base class
  and mark the four pipeline phases as abstract methods that concrete SETs must implement.
* ``enum.Enum``: Used to define ``ReportFormat``, an enumeration of supported output formats.
* ``typing``: Type hints for all method signatures and instance attributes.
* ``datetime``: Used to record execution start and end times.
* ``math.sqrt``, ``scipy.special.erfinv``: Used in the confidence interval calculation helper.
* ``.schema``: The dataclasses that form the data contracts between pipeline phases (covered below).
* ``BaseLMConnector``: Type hint for the connector passed into ``execute()``.
* ``EvaluationLanguageModel``: Optional evaluation language model that concrete SETs may use to assess
  the model outputs with.

1. Defining the Data Schema
----------------------------

Before writing the pipeline itself, we need to define the dataclasses that act as the data
contracts between phases. These live in ``schema.py`` alongside the pipeline. There are five
dataclasses in total, each corresponding to a specific stage in the data flow.

``LanguageModelSETCase`` — Phase 1 output / Phase 2 input
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This dataclass represents a single SET case: the minimal unit of work that the pipeline processes.
Every SET case must have an ``id`` and a ``prompt``. Any additional data — such as the attack
category or expected behavior — can be stored in the ``metadata`` dictionary
so that it is carried through the pipeline and appears in the final report.

.. code:: python
   :caption: LanguageModelSETCase dataclass in schema.py.

    @dataclass
    class LanguageModelSETCase:
        """Contract: Output of initialize(), input to execute().

        ID and prompt are required fields that every SET case must contain.
        Additional fields can be added to 'metadata'.
        """

        id: str
        prompt: str
        metadata: Dict[str, Any] = field(default_factory=dict)

        def to_dict(self) -> Dict[str, Any]:
            return {
                "id": self.id,
                "prompt": self.prompt,
                **self.metadata,
            }

``ExecutionOutput`` — Intermediate result per SET case
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This dataclass holds the raw output of running a single SET case against the target model. It
captures the original prompt, the model's response, any metadata carried over from the SET case,
and an optional ``error`` field for cases where execution failed. Using a dedicated ``error``
field (rather than raising an exception) allows execution to continue through the remaining SET
cases and report failures cleanly at the evaluation stage.

.. code:: python
   :caption: ``ExecutionOutput`` dataclass in schema.py.

    @dataclass
    class ExecutionOutput:
        """Single test execution / output result.

        Produced by execute() for each test case.
        """

        set_id: str
        prompt: str
        response: str
        metadata: Dict[str, Any] = field(default_factory=dict)
        error: Optional[str] = None

        def to_dict(self) -> Dict[str, Any]:
            result = {
                "set_id": self.set_id,
                "prompt": self.prompt,
                "response": self.response,
                "metadata": self.metadata,
            }
            if self.error:
                result["error"] = self.error
            return result

``OutputData`` — Phase 2 output / Phase 3 input
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This dataclass bundles all ``ExecutionOutput`` instances together with the total execution
duration. Wrapping outputs and timing in a single object keeps the ``execute()`` → ``evaluate()``
contract clean and makes it easy to include execution time in the final report.

.. code:: python
   :caption: OutputData dataclass in schema.py.

    @dataclass
    class OutputData:
        """Output of execute(), input to evaluate().

        Contains all execution outputs and execution duration in seconds.
        """

        outputs: List[ExecutionOutput]
        duration_seconds: float

        def to_dict(self) -> Dict[str, Any]:
            return {
                "outputs": [output.to_dict() for output in self.outputs],
                "duration": self.duration_seconds,
            }

``EvaluationResult`` — Phase 3 output / Phase 4 input
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This dataclass holds the evaluated result of a single SET case. The ``status`` field must be one
of ``"passed"``, ``"failed"``, or ``"error"``. The ``reason`` field should explain *why* that
status was assigned. The ``detections`` dictionary stores the raw findings from any evaluators
used, and the optional ``elm_evaluation`` field is for the verdict produced by an Evaluation
Language Model, if one was used.

.. code:: python
   :caption: ``EvaluationResult`` dataclass in schema.py.

    @dataclass
    class EvaluationResult:
        """Evaluation result of a single test.

        Produced by evaluate() for each ExecutionOutput.
        """

        set_id: str
        prompt: str
        response: str
        status: str       # "passed", "failed", or "error"
        reason: str
        detections: Dict[str, Any] = field(default_factory=dict)
        metadata: Dict[str, Any] = field(default_factory=dict)
        elm_evaluation: Optional[str] = None

        def to_dict(self) -> Dict[str, Any]:
            result = {
                "set_id": self.set_id,
                "prompt": self.prompt,
                "response": self.response,
                "status": self.status,
                "reason": self.reason,
                "detections": self.detections,
                "metadata": self.metadata,
            }
            if self.elm_evaluation:
                result["elm_evaluation"] = self.elm_evaluation
            return result

``ReportData`` — Phase 4 output / Final report
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the top-level dataclass that represents the completed report. It contains the SET name,
a timestamp, total execution time, a summary of pass/fail/error statistics, the full list of
``EvaluationResult`` objects, and the configuration that was used for the run. This object is
what reporters (JSON, HTML, Markdown) consume to write the output file.

.. code:: python
   :caption: ``ReportData`` dataclass in schema.py.

    @dataclass
    class ReportData:
        """Output of the report phase / function.

        The final report structure that is serialized to the desired format.
        """

        set_name: str
        timestamp: str
        execution_time_seconds: Optional[float]
        summary: Dict[str, Any]
        results: List[EvaluationResult]
        configuration: Dict[str, Any] = field(default_factory=dict)

        def to_dict(self) -> Dict[str, Any]:
            return {
                "set_name": self.set_name,
                "timestamp": self.timestamp,
                "execution_time_seconds": self.execution_time_seconds,
                "configuration": self.configuration,
                "summary": self.summary,
                "results": [result.to_dict() for result in self.results],
            }

2. Defining the Base Pipeline Class
-------------------------------------

With the data schema in place, we can define the abstract base class itself. ``BaseSETPipeline``
inherits from Python's ``ABC`` and declares the four pipeline phases as abstract methods. It also
holds a set of common instance attributes that all concrete SETs will need — such as references
to the connector configuration path, the target model name, and an optional evaluation model.

``ReportFormat`` — Supported output formats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before defining the base class, we declare ``ReportFormat`` as an ``Enum`` to represent the
supported report output formats. Using an enum (rather than raw strings) makes the format
parameter type-safe and self-documenting throughout the codebase.

.. code:: python
   :caption: ReportFormat enum.

    class ReportFormat(Enum):
        """Available file formats."""

        JSON = "json"
        HTML = "html"
        MARKDOWN = "md"

Class definition and ``__init__``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The class is declared as abstract, which prevents it from being instantiated directly. The
``name`` and ``description`` class attributes are left empty here and must be set by every
concrete SET subclass. The ``SUPPORTED_FORMATS`` list provides a reference of which report
file formats are supported.

The ``__init__`` method initializes all common instance attributes to ``None`` or sensible
defaults. It does **not** accept any arguments — concrete SETs can extend ``__init__``
to add their own attributes (and must call ``super().__init__()`` when doing so).

.. code:: python
   :caption: ``BaseSETPipeline`` class definition and __init__.

    class BaseSETPipeline(ABC):
        """The base Pipeline class for Language Model Security Evaluation Tests."""

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

3. Declaring the Abstract Phase Methods
-----------------------------------------

Each of the four pipeline phases is declared as an ``@abstractmethod``. This enforces the
contract that any concrete SET **must** implement all four phases. The docstrings on each method
serve as the official specification for what each phase is responsible for and what its inputs
and outputs must be. Concrete implementations should preserve these contracts even when
overriding the methods with their own logic.

``initialize()``
~~~~~~~~~~~~~~~~

Responsible for loading the SET configuration and returning a list of ``LanguageModelSETCase``
objects. Every SET case must carry at minimum an ``id`` and a ``prompt``; any other
test-specific data belongs in ``metadata``.

.. code:: python
   :caption: Abstract ``initialize()`` method.

    @abstractmethod
    def initialize(self, set_config_path: str) -> List[LanguageModelSETCase]:
        """Load and return SET cases from configuration files.

        Args:
            set_config_path: Path to SET configuration file

        Returns:
            List[LanguageModelSETCase]: SET cases used in the run

        Requirements:
            - Each SET case must at least contain an ID and a prompt
            - Additional data related to the SETs go to the metadata
        """
        pass

``execute()``
~~~~~~~~~~~~~

Responsible for running each SET case against the target model via the provided connector and
returning an ``OutputData`` object containing one ``ExecutionOutput`` per SET case. Errors during
execution should be caught and stored in ``ExecutionOutput.error`` rather than propagated as
exceptions, so that the remaining SET cases can still be run.

.. code:: python
   :caption: Abstract ``execute()`` method.

    @abstractmethod
    def execute(
        self, connector: BaseLMConnector, sets: List[LanguageModelSETCase]
    ) -> OutputData:
        """Run the SETs against the target.

        Args:
            connector: A connector instance
            sets: List of SET cases from initialize()

        Returns:
            OutputData: All SET outputs along with the execution time.

        Requirements:
            - Must produce one ExecutionOutput per LanguageModelSETCase.
            - Metadata from LanguageModelSETCase should be carried through for the final report.
            - Errors should be placed to ExecutionOutput.error for later inspection.
        """
        pass

``evaluate()``
~~~~~~~~~~~~~~

Responsible for inspecting each ``ExecutionOutput`` and producing one ``EvaluationResult`` per
output. The ``status`` field of each result must be exactly one of ``"passed"``, ``"failed"``, or
``"error"``, and the ``reason`` field must explain why that status was assigned.

.. code:: python
   :caption: Abstract ``evaluate()`` method.

    @abstractmethod
    def evaluate(self, execution_data: OutputData) -> List[EvaluationResult]:
        """Evaluate the SET outputs with evaluators.

        Args:
            execution_data: OutputData from execute()

        Returns:
            List[EvaluationResult]: Evaluation of each SET

        Requirements:
            - Must produce one EvaluationResult per ExecutionOutput
            - Status must be "passed", "failed", or "error"
            - Reason should explain the SET status
        """
        pass

``report()``
~~~~~~~~~~~~

Responsible for assembling a ``ReportData`` object from the evaluation results and writing a
report file in the requested format to the given output path. The method must return the
``ReportData`` object regardless of the format written.

.. code:: python
   :caption: Abstract ``report()`` method.

    @abstractmethod
    def report(
        self,
        results: List[EvaluationResult],
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
    ) -> ReportData:
        """Generate the final report in the desired format and save it to target location.

        Args:
            results: List[EvaluationResult] from evaluate()
            output_path: Path for output file
            report_format: Report format. Defaults to JSON.

        Returns:
            ReportData: The final report with all the SET data

        Requirements:
            - Must write a report in the requested format to output_path
        """
        pass

4. Implementing the ``run()`` Orchestrator
-------------------------------------------

The ``run()`` method is the only concrete method that directly implements pipeline logic in
the base class. It is called by the Execution Engine and is responsible for invoking the four
phases in order, passing the output of each phase as the input to the next. It also stores
the connector and configuration paths on the instance so that concrete ``report()`` implementations
can access them when building the final ``ReportData`` object.

.. code:: python
   :caption: ``run()`` orchestration method.

    def run(
        self,
        connector: BaseLMConnector,
        set_config_path: str,
        output_path: str,
        report_format: ReportFormat = ReportFormat.JSON,
        connector_config_path: Optional[str] = None,
    ) -> ReportData:
        """Orchestration method that executes the 4-phase pipeline."""

        # Store config paths and model name for report
        self.connector_config_path = connector_config_path
        self.set_config_path = set_config_path
        self.target_model_name = connector.model

        # Phase 1
        sets = self.initialize(set_config_path)

        # Phase 2
        execution_data = self.execute(connector, sets)

        # Phase 3
        results = self.evaluate(execution_data)

        # Phase 4
        report_data = self.report(results, output_path, report_format)

        return report_data

.. note::

   ``run()`` is intentionally kept minimal. It is a thin orchestrator — it does not contain any
   evaluation logic of its own. All domain-specific behaviour lives in the four phase methods,
   which concrete SETs override.

5. Adding Shared Helper Utilities
-----------------------------------

Beyond the four abstract phases and the ``run()`` orchestrator, the base class can also provide
shared utility methods that concrete SETs are likely to need. These are implemented as
``@staticmethod`` methods so that they can be used without needing to instantiate the class.
Concrete SETs can override these if they need different behaviour.

``calculate_passrates()``
~~~~~~~~~~~~~~~~~~~~~~~~~~

This helper computes the summary statistics for the final report: total SET count, number of
passed/failed/errored cases, pass rate and fail rate as percentages, and a Wilson score
confidence interval for the pass rate. It is intended to be called inside ``report()``
implementations to populate the ``summary`` field of ``ReportData``.

.. code:: python
   :caption: calculate_passrates() static helper method.

    @staticmethod
    def calculate_passrates(results: List[EvaluationResult]) -> Dict[str, Any]:
        """Calculate summary statistics based on results."""
        total_sets = len(results)
        passed = 0
        failed = 0
        errors = 0

        for result in results:
            if result.status == "passed":
                passed += 1
            elif result.status == "failed":
                failed += 1
            else:
                errors += 1

        if total_sets > 0:
            pass_rate = round(passed / total_sets * 100, 1)
            fail_rate = round(failed / total_sets * 100, 1)
        else:
            pass_rate = 0
            fail_rate = 0

        confidence_interval = BaseSETPipeline._calculate_confidence_interval(
            passed, failed
        )

        return {
            "total_sets": total_sets,
            "passed": passed,
            "failed": failed,
            "error": errors,
            "pass_rate": pass_rate,
            "fail_rate": fail_rate,
            "ci_lower_bound": confidence_interval[1],
            "ci_upper_bound": confidence_interval[2],
        }

``_calculate_confidence_interval()``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This internal helper computes the `Wilson score interval
<https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval#Wilson_score_interval>`_
for the pass rate, given the number of passed and failed cases and a desired confidence level
(default 95%). The Wilson score interval is preferred over a naïve normal approximation because
it remains valid even when the number of tests is small or when the pass rate is near 0 or 1.

The method returns a tuple of ``(proportion, lower_bound, upper_bound)`` with both bounds
clamped to the range ``[0, 1]``. When no tests have been run (``n == 0``), it returns
``(0, 0, 0)`` to avoid a division-by-zero error.

.. code:: python
   :caption: ``_calculate_confidence_interval()`` static helper method.

    @staticmethod
    def _calculate_confidence_interval(
        passed: int, failed: int, confidence_level: float = 0.95
    ) -> tuple[int, float, float]:
        """Calculate Wilson score confidence interval for binary data.

        Args:
            passed: Number of runs passed.
            failed: Number of runs failed.
            confidence_level: CI level (default 0.95).

        Returns:
            tuple: (proportion, lower_bound, upper_bound)
        """
        n = passed + failed

        if n == 0:
            return (0, 0, 0)

        p = passed / n
        z = 1.96 if confidence_level == 0.95 else sqrt(2) * erfinv(confidence_level)

        denominator = 1 + (z**2 / n)
        center = (p + (z**2 / (2 * n))) / denominator
        margin = (z / denominator) * sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))

        lower_bound = max(0, center - margin)
        upper_bound = min(1, center + margin)

        return (p, lower_bound, upper_bound)

Summary: Contracts at a Glance
--------------------------------

The table below summarises the full data flow and the contract each phase must honour.

.. list-table:: BaseSETPipeline phase contracts
   :header-rows: 1
   :widths: 15 25 25 35

   * - Phase
     - Method
     - Input → Output
     - Key requirements
   * - 1
     - ``initialize()``
     - ``set_config_path`` → ``List[LanguageModelSETCase]``
     - Every case must have ``id`` and ``prompt``; extras go to ``metadata``
   * - 2
     - ``execute()``
     - ``List[LanguageModelSETCase]`` → ``OutputData``
     - One ``ExecutionOutput`` per case; errors go to ``ExecutionOutput.error``
   * - 3
     - ``evaluate()``
     - ``OutputData`` → ``List[EvaluationResult]``
     - One result per output; ``status`` must be ``"passed"``, ``"failed"``, or ``"error"``
   * - 4
     - ``report()``
     - ``List[EvaluationResult]`` → ``ReportData``
     - Must write the report file to ``output_path`` and return ``ReportData``

Building a SET on top of the BaseSETPipeline
----------------------------------------------

With the ``BaseSETPipeline`` defined, you can now build SETs on top of it. To see a complete
worked example of how to implement all four phases in a concrete SET, see :ref:`building_set`.

Contributing a new BaseSETPipeline
-----------------------------------

To confirm that a newly created ``BaseSETPipeline`` works as expected, at least one SET is needed
to be built on top of it. Once you have a new ``BaseSETPipeline`` and a SET to go with it, they can
be contributed to the main repository for other users to utilize them as well. For details on how to
contribute a Pipeline and a SET to the main repository, check out :ref:`contributing_pipeline.
