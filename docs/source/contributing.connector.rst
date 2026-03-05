.. _contributing_connector:

Contributing a Connector
=================================

Connectors encapsulate the logic for making requests to, and receiving responses from, AI
models. Before executing any SETs on your target model, a connector must be configured
appropriately. The ``avise/configs/connector/`` directory includes template configuration
JSON files for different types of AI model hosts. Additionally, the
``avise/configs/connector/<model-type>/genericrest.json`` configuration file can be adjusted
to connect to models accessible via any REST API endpoint.

Writing a New Connector
-----------------------

Before starting a new connector module, check whether any of the existing connectors could
be adapted to fit your needs. A new connector should only be created if none of the current
modules are a suitable fit. For a practical reference, see how ``avise.connectors.languagemodel.ollama``
was built along with its configuration file ``avise/configs/connector/languagemodel/ollama.json`` —
they serve as a good example of the structure and conventions to follow.

New connectors must inherit from the base connector class corresponding to the target AI
system type. For example, if you are writing a connector for a Language Model, your connector
should inherit from ``avise.connectors.languagemodel.base``. When implementing your connector,
override as little as possible — only the methods that are strictly necessary for your
specific integration. This keeps connectors lean and maintainable.

Check out :ref:`_building_connector` for a step-by-step example guide, on how to build a new connector.

Testing Your Connector
----------------------

.. note::

Before you can use the AVISE CLI to test if your connector works, remember to import it in the
``avise/connectors/<AI_SYSTEM_TYPE>/__init__.py`` file. This adds the connector to the ``registry``
and can then be used by the Execution Engine.

While developing your connector, you can test it by running some SET via the CLI and giving the
configuration JSON file of your connector as an argument:

.. code:: bash

   python -m avise --SET  prompt_injection --connectorconf path/to/your/connector/config/json


AVISE supports ``pytest`` tests located in the ``./unit-tests`` directory. You can run the full
test suite from the root of the repository with:

.. code-block:: bash

   python -m pytest

All tests must pass before any code can be merged to the main repository. When submitting a Pull Request, ensure
that the entire test suite passes, and consider adding tests that cover the behaviour of
your new connector to help maintain confidence in the codebase going forward.

Contributing Your Connector
----------------------------

Did you build a connector that could be useful to other users of AVISE as well? We love community contributions and
would like to include it in the main repository. Once your connector is complete and all
unit tests are passing, take a look at the :ref:`_contributing` documentation for guidance on how
to submit your work to the project.