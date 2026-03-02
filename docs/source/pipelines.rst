Pipelines
=================================

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

.. toctree::
   :maxdepth: 2

   avise.pipelines.languagemodel