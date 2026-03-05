.. _contributing_pipeline:

Contributing a Pipeline
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


Writing a New Pipeline
-----------------------

Before starting a new pipeline module, check whether any of the existing pipelines could
be used to fit your needs. A new pipeline should only be created if none of the current
modules are a suitable fit for the SET you are trying to develop. For a practical reference,
see how ``avise.pipelines.languagemodel.pipeline``
was built  —
it serves as a good example of the structure and conventions to follow.


Check out :ref:`_building_pipeline` for a step-by-step example guide, on how to build a new pipeline.

Testing Your Pipeline
----------------------

In order to test if a pipeline is functional, it needs to be extended with a SET that can be ran on
some target model/system. This is why it is adviced to only create a new pipeline when one is needed
to create a new SET. For detailed guide on how to create a SET, check out :ref:`_building_set`.

After you have developed the first iterations of a new BaseSETPipeline, and some SET to go with it,
you can test if they work by running the SET on some target model. Remember to import the SET in
``avise/sets/<AI_MODEL_TYPE>/<SET_TYPE>/__init__.py``. This adds the SET into the ``registry`` and
allows the Execution Engine to use it. After you have added the import, you can run the SET on some
target model with e.g.:

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

Did you build a pipeline that could be useful to other users of AVISE as well? We love community contributions and
would like to include it in the main repository. Once your pipeline and SET is complete and all
unit tests are passing, take a look at the :ref:`_contributing` documentation for guidance on how
to submit your work to the project.