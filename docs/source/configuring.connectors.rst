Configuring Connectors
=================================

Connectors are a component in the AVISE framework that contain the logic
for making requests and receiving responses from AI models. When using AVISE,
you need to pass a Connector configuration JSON file via the CLI argument ``--connectorconf``.

AVISE comes with multiple prebuilt configuration files for commonly used AI model 
hosting services:

Ollama Connector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Ollama <https://ollama.com/>`__ is a widely used software for running language models. 
To use AVISE with Ollama models, you can modify the existing ``avise/configs/connector/ollama.json`` 
configuration file:

.. code-block:: json
   :caption: ``avise/configs/connector/ollama.json``

   {
       "target_model": {
           "connector": "ollama-lm",
           "type": "language_model",
           "name": "phi3:latest", //ADD NAME OF THE OLLAMA MODEL TO TEST HERE
           "api_url": "http://localhost:11434", //Ollama default
           "api_key": null
       },
       "eval_model": {
           "connector": "ollama-lm",
           "type": "language_model",
           "name": "phi3:latest", //Optional
           "api_url": "http://localhost:11434", //Ollama default
           "api_key": null
       }
   }

In the Connector configuraiton files, ``target_model`` defines the configurations for the 
model you wish to test and evaluate. ``eval_model`` on the other hand defines the configurations 
for an optional evaluation language model, that will be used to generate a summary and helpful tips
for the final report produced when running SETs. Both fields require the same subfields:

* ``"connector"``: Name of the connector to use (See available connectors by running CLI command ``avise --connector_list``)
* ``"type"``: Type of the AI model *(e.g. language_model, continual_learning, multi_modal)*
* ``"name"``: Name of the model *(For Ollama connector, use the ollama model name)*
* ``"api_url"``: URL for the API endpoint (``http://localhost:11434`` is the default when running Ollama models locally)
* ``"api_key"``: Optional API authorization key if required by the API Endpoint. **Leave as ``null`` if not needed** 



OpenAI Connector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 
To use AVISE with `OpenAI <https://openai.com/>`__ models, you can modify the existing ``avise/configs/connector/openai.json`` 
configuration file:

.. code-block:: json
   :caption: ``avise/configs/connector/openai.json``

    {
        "target_model": {
            "connector": "openai-lm",
            "type": "language_model",
            "name": "gpt-4o-mini",
            "api_url": null,
            "headers": null,
            "api_key": "YOUR_OPENAI_API_KEY_HERE"
        },

        "eval_model": {
            "connector": "openai-lm",
            "type": "language_model",
            "name": "gpt-4o-mini",
            "api_url": null,
            "headers": null,
            "api_key": "YOUR_OPENAI_API_KEY_HERE"
        }
    }

In the Connector configuraiton files, ``target_model`` defines the configurations for the 
model you wish to test and evaluate. ``eval_model`` on the other hand defines the configurations 
for an optional evaluation language model, that will be used to generate a summary and helpful tips
for the final report produced when running SETs. Both fields require the same subfields:

* ``"connector"``: Name of the connector to use (See available connectors by running CLI command ``avise --connector_list``)
* ``"type"``: Type of the AI model *(e.g. language_model, continual_learning, multi_modal)*
* ``"name"``: Name of the model *(For OpenAI connector, use the openai model name)*
* ``"api_url"``: URL for the API endpoint
* ``"headers"``: Optional Headers for the API request.
* ``"api_key"``: OpenAI Authentication API Key.





Generic REST API Connector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With the Generic REST API Connector, you can connect AVISE to any RESTful API Endpoint. To configure the Generic REST API Connector,
modify the existing ``avise/configs/connector/genericrest.json`` configuration file:

.. code-block:: json
   :caption: ``avise/configs/connector/genericrest.json``

    {
        "target_model": {
            "connector": "generic-rest-lm",
            "type": "language_model",
            "name": "<PLACEHOLDER_NAME>",
            "api_url": "PLACEHOLDER_URL",
            "headers": null,
            "api_key": null,
            "response_field": "KEY_OF_GENERATED_RESPONSE",
            "method": "POST"
        },
        "eval_model": {
            "connector": "generic-rest-lm",
            "type": "language_model",
            "name": "PLACEHOLDER_NAME",
            "api_url": "PLACEHOLDER_URL",
            "headers": null,
            "api_key": null,
            "response_field": "KEY_OF_GENERATED_RESPONSE",
            "method": "POST"
        }
    }

In the Connector configuraiton files, ``target_model`` defines the configurations for the 
model you wish to test and evaluate. ``eval_model`` on the other hand defines the configurations 
for an optional evaluation language model, that will be used to generate a summary and helpful tips
for the final report produced when running SETs. Both fields require the same subfields:

* ``"connector"``: Name of the connector to use (See available connectors by running CLI command ``avise --connector_list``)
* ``"type"``: Type of the AI model *(e.g. language_model, continual_learning, multi_modal)*
* ``"name"``: Name of the model. *(Optional for Generic REST Connector)*
* ``"api_url"``: URL for the API endpoint
* ``"headers"``: Optional Headers for the API request.
* ``"api_key"``: OpenAI Authentication API Key.
* | ``"response_field"``:  The field in which the response of the AI model is contained in the API request response. E.g. if the API response is:
  | ``{status: "success", message: "example message", data: {"model_name": "Gemini 2.5", "prompt": "Hi, what is your name?", "response": "Hello there! I'm Gemini, developed by Google."}}``, then the ``response_field`` would be ``["data"]["response"]``.
* ``"method"``: API Method to use.
