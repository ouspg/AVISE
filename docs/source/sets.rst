Security Evaluation Tests
=================================

Security Evaluation Tests, or SETs, contain the detailed logic for identifying a specific vulnerability
or assessing the security of a target system or component within a specified scope. SETs inherit the base
logic for the execution flow of a certain type of a SET from BaseSETPipelines. For example, all language model
SETs inherit the execution flow logic from ``pipelines.languagemodel.BaseSETPipeline``.

Developing new SETs and contributing them to the repository is straightforward. Check out :ref:`_contributing_set`
for details on how to contribute a new SET to the repository, and :ref:`_building_set` for step-by-step guide on
how to create a new SET.

.. toctree::
   :maxdepth: 2

   avise.sets