Evaluators
=================================

Evaluators define the logic for automated evaluation of SET results. They include algorithms that look for predefined patterns from SET results 
that would indicate if the target model or system is vulnerable to an attack which the SET simulates. Additionally if included in the connector 
configuration file, an evaluation language model can be used to analyze the SET results. The insights it provide will be included in the generated 
final report in addition to evaluators' assessments.

.. toctree::
   :maxdepth: 2
   
   avise.evaluators.languagemodel