Core Components
=================================

AVISE framework constitutes of 5 core components that include the required logic for the full life-cycle of
automated vulnerability identification and security evaluation:

1. Security Evaluation Tests

2. SET Pipelines

3. Connectors

4. Evaluators

5. Execution Engine

Security Evaluation Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Security Evaluation Tests, or SETs, contain the detailed logic for identifying a specific vulnerability
or assessing the security of a target system or component within a specified scope. SETs inherit the base
logic for the execution flow of a certain type of a SET from BaseSETPipelines. For example, all language model
SETs inherit the execution flow logic from ``pipelines.languagemodel.BaseSETPipeline``.

Developing new SETs and contributing them to the repository is straightforward. ``TODO: Add link or add details
of an example of developing a new SET.``


BaseSETPipelines
~~~~~~~~~~~~~~~~~~~~~~~~~~

BaseSETPipelines contain the execution flow logic of SETs. Each BaseSETPipeline has 4 phases, for which the required
data contracts are detailed in the Pipeline Schema. The 4 phases are: Initialization, Execution, Evaluation, and Reporting.
In the Initialization phase, the SET cases are loaded from a JSON configuration file in ``avise/configs/SET/``. Execution phase
executes the loaded SETs on the target model, or system, and returns data objects for evaluation. In Evaluation phase, the data
objects containing results from executing SET are evaluated by the evaluators and optionally a evaluation language model. In the
Reporting phase, Evaluation data objects which contain the evaluation results are passed to Report Generation tools, and a final
report of the executed SETs and their evaluation results is generated. The final report includes detailed logs as a JSON file,
and a human-readable HTML summarizing the executed SETs.

In order to develop SETs for some type of a target AI model or system (e.g. language models) not yet supported by AVISE,
first a BaseSETPipeline has to be created to accommodate a new execution flow for the SETs. Once a BaseSETPipeline has
been developed, it can be extended to create as many SETs as necessary.


Connectors
~~~~~~~~~~~~~

Connectors include the logic of making requests to, and receiving responses from, AI models. Before executing any SETs on your
target model, a connector must be configured appropriately. ``avise/configs/connector/`` directory includes template configuration
JSON files for different types of AI model hosts. Additionally, ``avise/configs/connector/genericrest.json`` configuration file can be
adjusted to connect to models accessible via any REST API endpoint.

Evaluators
~~~~~~~~~~~~~

Evaluators define the logic for automated evaluation of SET results. They include algorithms that look for predefined patterns from SET results
that would indicate if the target model or system is vulnerable to an attack which the SET simulates. Additionally if included in the connector
configuration file, an evaluation language model can be used to analyze the SET results. The insights it provide will be included in the generated
final report in addition to evaluators' assessments.

Execution Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~

The execution engine orchestrates performing Security Evaluation Tests based on provided configuration files.
