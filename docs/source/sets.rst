Security Evaluation Tests
=================================

Security Evaluation Tests, or SETs, contain the detailed logic for identifying a specific vulnerability
or assessing the security of a target system or component within a specified scope. SETs inherit the base
logic for the execution flow of a certain type of a SET from BaseSETPipelines. For example, all language model
SETs inherit the execution flow logic from ``pipelines.languagemodel.BaseSETPipeline``.

Developing new SETs and contributing them to the repository is straightforward. ``TODO: Add link or add details
of an example of developing a new SET.``

.. toctree::
   :maxdepth: 2

   avise.sets.languagemodel