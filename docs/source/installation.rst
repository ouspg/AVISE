Installation
=================================

Currently, AVISE can be installed by cloning the repository and installing required dependencies. After installation,
Connector configuration files found in `avise/configs/connector/` need to be configured with details of the target model API endpoint.

The guide below assumes using `Ollama <https://ollama.com/>`__ to run models.

Prerequisites
~~~~~~~~~~~~~

-  Python 3.10+
-  Docker (for Ollama backend)
-  pip

1. Clone the Repository
~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   git clone https://github.com/ouspg/AVISE.git

.. code:: bash

   cd AVISE

2. Set Up Python Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Create Virtual Environment

.. code:: bash

   python -m venv venv

* Activate Virtual Environment

  * On Linux & Mac:

    .. code:: bash

       source venv/bin/activate

  * On Windows:

    .. code:: bash

       source venv/Scripts/activate

* Install dependencies

.. code:: bash

   pip install -r requirements.txt

3. Set Up by using Ollama Backend with Docker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**GPU Version:**

.. code:: bash

   docker-compose -f docker/ollama/docker-compose.yml up -d

**CPU-only Version:**

.. code:: bash

   docker-compose -f docker/ollama/docker-compose-cpu.yml up -d

4. Pull Models
~~~~~~~~~~~~~~

After Ollama is running, pull the models you want to test:

.. code:: bash

   docker exec -it ollama ollama pull MODEL_NAME

5. Configure Connectors
~~~~~~~~~~~~~~~~~~~~~~~

Edit ``avise/configs/connector/ollama.json``:

.. code:: json

   {
       "target_model": {
           "connector": "ollama-lm",
           "type": "language_model",
           "name": "phi3:latest", //ADD NAME OF THE OLLAMA MODEL TO TEST HERE
           "api_url": "http://localhost:11434", //Ollama default
           "api_key": null
       }
   }

Basic usage example
---------------------

AVISE uses preconfigured paths for SET and Connector configuration JSON files, if the paths are not given as CLI arguments:

.. code:: bash

   python -m avise --SET  prompt_injection --connectorconf ollama

Advanced usage example
-----------------------

If you wish to use custom SET and Connector configuration files, you can give them with the ``--connectorconf`` and ``--SETconf`` CLI arguments:

.. code:: bash

   python -m avise --SET  prompt_injection --connectorconf avise/configs/connector/ollama.json  --SETconf avise/configs/set/prompt_injection_mini.json
