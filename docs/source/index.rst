AVISE Documentations
=====================

AVISE (AI Vulnerability Identification & Security Evaluation) is a modular framework for developing automated **S**\ ecurity
**E**\ valuation **T**\ ests (SETs) to identify vulnerabilities in and assess the security of AI systems. AVISE provides a scalable,
automated approach to red teaming AI systems. It allows developers and researchers to deploy consistent, rigorous security
evaluation tests across a wide range of different types of AI systems from Large Language Models to specialized
Continual Learning systems.

The core element of AVISE is its extensible acrhitecture. The modular design of the framework allows automated security
evaluation tests to be developed for various AI types with the same framework, without reinventing the wheel every time.
And as novel adversarial techniques and AI types emerge, new BaseSETModules can easily be developed with the framework that
allow development and deployment of new kinds of **S**\ ecurity **E**\ valuation **T**\ ests, addressing the emerging needs.

To get started, you can browse our SET Registry to select pre-built tests that match your specific AI stack.
If you are dealing with a unique edge case, or wish to identify vulnerabilities that we haven't yet developed
automated **S**\ ecurity **E**\ valuation **T**\ ests for, you can chat with us in `Discord <https://discord.gg/CebeeMUqSP>`_.
We are always eager to hear user and developer feedback on how we could improve AVISE. Additionally, extending AVISE with
new SETs is straightforward - we suggest to get familiar with BaseSETModules, SETs, and Contributing within these documentations, if you'd
like to develop your own **S**\ ecurity **E**\ valuation **T**\ ests. For technical support, you can also hop in to `Discord <https://discord.gg/CebeeMUqSP>`_
and we're happy to help you.


.. note::

   This project is under active development. For any questions, contributions, or improvement suggestions, the best way to reach us is
   at the project `Discord <https://discord.gg/CebeeMUqSP>`_ server.

.. toctree::
   :maxdepth: 1
   :caption: Usage:

   installation
   quickstart
   configuring.connectors
   configuring.sets


.. toctree::
   :caption: Reference:
   :maxdepth: 1

   core_components
   sets
   pipelines
   connectors
   evaluators
   registry
   reportgen
   execution_engine

.. toctree::
   :caption: Extending:
   :maxdepth: 1

   building.set
   building.pipeline
   building.connector
   building.evaluator

.. toctree::
   :caption: Contributing:
   :maxdepth: 1

   contributing.set
   contributing.pipeline
   contributing.connector
   contributing

