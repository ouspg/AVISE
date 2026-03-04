.. _contributing_set:

Contributing a Security Evaluation Test
=================================

Security Evaluation Tests, or SETs, contain the detailed logic for identifying a specific vulnerability
or assessing the security of a target system or component within a specified scope. SETs inherit the base
logic for the execution flow of a certain type of a SET from BaseSETPipelines. For example, all language model
SETs inherit the execution flow logic from ``pipelines.languagemodel.BaseSETPipeline``.

Writing a New SET
-----------------------

Before starting a new SET module, check whether any of the existing SETs could
be used to fit your needs. Often it is enough to create a new SET configuration JSON
that modifies how an existing SET executes. For a practical reference,
see how ``avise.sets.languagemodel.multiturn.prompt_injection`` was built  —
it serves as a good example of the structure and conventions to follow.


Check out :ref:`_building_set` for a step-by-step example guide, on how to build a new pipeline.

Testing Your SET
----------------------

In order to test if a SET is functional, you can try to run it on some target model with the AVISE
CLI. Remember to import your SET in the ``avise/sets/<AI_MODEL_TYPE>/<SET_TYPE>/__init__.py`` file.
This adds the SET into the ``registry``, allowing the Execution Engine to find and run it.

When the SET is ready to be tested, you can run it with the CLI by e.g.:

.. code:: bash

   python -m avise --SET  YOUR_SET_ID --SETconf path/to/your/set/config/json --connectorconf ollama


AVISE supports ``pytest`` tests located in the ``./unit-tests`` directory. You can run the full
test suite from the root of the repository with:

.. code-block:: bash

   python -m pytest

All tests must pass before any code can be merged to the main repository. When submitting a Pull Request, ensure
that the entire test suite passes, and consider adding tests that cover the behaviour of
your new SET to help maintain confidence in the codebase going forward.

Contributing Your Pipeline
----------------------------

Did you build a SET that could be useful to other users of AVISE as well? We love community contributions and
would like to include it in the main repository. Once your SET is complete and all
unit tests are passing, take a look at the :ref:`_contributing` documentation for guidance on how
to submit your work to the project.