.. building_connector:

Building a Connector
=================================

Connectors include the logic of making requests to, and receiving responses from, AI models. Before
executing any SETs on your target model, a connector must be configured appropriately. In this section,
we will walkthrough building a new connector.

1. Creating a Base Connector Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To make creating new Connectors easier and ensuring compability with rest of the AVISE framework,
AVISE has a Base Connector class for each different type of a target system. Any Connectors created
should inherit from a Base Connector class and try to override as little as possible from it.

.. note::

Before creating a new Base Connector class, check out ``avise/connectors/`` directory and see if there
is a Base Connector class for the type of an AI system you wish to create a connector for.

In this example, we will be creating a Connector for Language Models running on `Ollama <https://ollama.com/>`_.
So the first thing we need to do, is figure out what kinds of inputs language models take and what do their outputs
generally look like.

As language models generally take inputs in the form of a dictionary that contains ``role`` and ``content`` fields,
we can first define a data class that represents a single prompt or response in a conversation, that can be helpful later on:

.. code:: python

    @dataclass
    class Message:
        """Represents a single message in a multi-turn conversation

        Attributes:
            role: The role of the message sender. "system", "user", or "assistant": https://platform.openai.com/docs/guides/text
            content: The text content of the message
        """

        role: str
        content: str


Next, we create the Base Connector Class. It is an abstract class inheriting from abc.ABC.
This abstract base class provides us the structure that Connectors can inherit. We want each
language model connector to at least have methods for 1. performing a status check to make sure
the target model is reachable, and 2. generating a response from the target model. Additionally,
as we want users to be able to configure their connector via a configuration JSON file, we can
create a class attribute that holds the configuration data as a dictionary.

The following is the finished abstract base class for language model connectors:


.. code:: python

    class BaseLMConnector(ABC):
    """A connector handles communication with a specific API / backend,
    abstracting the API usage for the framework.
    This allows SET cases to be written only once and users are able to run them against different models with different configurations.

    Class Methods:
    - generate(): Generate a response from target model.
    - status_check(): Verify that the target API endpoint is available.

    Class Attributes:
        config: Connector configuration data.
    """

    config: dict = {}

    @abstractmethod
    def generate(
        self,
        data: dict,
    ) -> dict:
        """Generate a response from the target model via the target API.

        Arguments:
            data: Dictionary containing data required for the generation API request.
            multi_turn: Boolean flag to indicate if engaging in a multi turn conversation\
                with the target model. Default False.

        Returns:
            Model response as a dictionary. The dict contains "response" field with the model response as a str.

        Raises:
            RuntimeError: If the API call fails.
        """
        pass

    @abstractmethod
    def status_check(self) -> bool:
        """Perform a status check for the target API via a GET request.

        Returns:
            True if status check was successful

        Raises:
            Exception: If the target API is not reachable.
        """
        pass

.. _building_connector_section_2:

2. Creating a Connector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that we have our base connector class for language models, we can move into creating
the actual connector class. In this example, we want to be able to run Security Evaluation
Tests on a target language model running via `Ollama <https://ollama.com/>`_, so we will
create an Ollama Connector.

For clarity, here are the package imports that we will use later on in the code:

* ``import logging``: logging is used to create logs that will help with debugging and informing the user of what's happening when the program is executing.
* ``from typing import List`` List is used as a type hint for method parameters that are a list of some specific type.
* ``import ollama`` We will use the ollama Client for making requests to the API endpoint.
* ``from .base import BaseLMConnector, Message`` These we defined earlier and will now use.
* ``from ...registry import connector_registry`` connector_registry holds information of all connectors, sets, and formats available to the Execution Engine. We want to add our connector to the registry as well.
* ``from ...utils import ansi_colors`` ansi_colors is a dictionary of ansi codes for different colors we can use to make our logging a bit prettier and easier to follow.

.. _building_connector_section_2_init:

Initialization
^^^^^^^^^^^^^^^^

First we define the class and its ``__init__`` method, that is called whenever an instance of the
class is created. We want to make sure the connector is added to the ``registry``, so that the
Execution Engine can find and use the connector when running SETs later on - for this, we
add the ``@connector_registry.register("ollama-lm")`` class decorator for the connector class.
Additionally, we include the ``name = "ollama-lm"`` attribute for the class.

In the ``__init__`` method, we set the instance attributes based on the read configuration JSON file.
In this step, we need to think what different possible configurations do we want users to be able to
modify and pass to the connector class. As Ollama has a REST API endpoint we can make requests to for
generating a model response, we can take a look at the Ollama documentations and figure out some most
commonly used fields in an API request made to its endpoint. These include, among others:

* ``api_key``: used for authorized API requests
* ``model``: the name of the model
* ``url``: url of the API endpoint
* ``max_tokens``: maximum amount of tokens to generate per response

These are a good starting point and with them we can initialize the Ollama client as an instance
variable, that we will use to generate responses from the target model. Here is the code we have written
so far, including logging, which is useful later on in debugging and informing users of what's currently
happening when they are running SETs:


.. code:: python

    logger = logging.getLogger(__name__)

    @connector_registry.register("ollama-lm")
    class OllamaLMConnector(BaseLMConnector):
        """Connector for communicating with the Ollama API.

        Used by Security Evaluation Tests for sending prompts to target Ollama models and collecting their responses.
        """

        name = "ollama-lm"

        def __init__(
            self,
            config: dict,
        ):
            """Initialize the Ollama connector.

            Args:
                config: Dictionary containing data from Connector configuration JSON.
            """
            self.api_key = None

            self.model = config["target_model"]["name"]
            self.base_url = config["target_model"]["api_url"]
            if (
                "max_tokens" in config["target_model"]
                and config["target_model"]["max_tokens"] is not None
            ):
                self.max_tokens = config["target_model"]["max_tokens"]
            else:
                self.max_tokens = 512
            if (
                "api_key" in config["target_model"]
                and config["target_model"]["api_key"] is not None
            ):
                self.api_key = config["target_model"]["api_key"]
                # Configure client with optional authentication headers
                self.client = ollama.Client(
                    host=self.base_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            else:
                self.client = ollama.Client(host=self.base_url)

            logger.info(f"  Ollama Connector Initialized")
            logger.info(f"  Base URL: {self.base_url}")
            logger.info(f"  Model: {self.model}")
            if self.api_key:
                logger.info(
                    f"  API Key: {'*' * 8}...{self.api_key[-4:] if len(self.api_key) > 4 else '****'}"
                )

Defining status_check
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Next, we can write the method for performing status checks on the API. This can be as basic
as making a GET request to the API endpoint, and checking if it returns the status code ``200``.
But since ollama has a convenient way of providing available model names via a GET request,
we can utilize this to ensure our target model is in the list of available models while
simultaneously performing the status check. For this, we can first define a helper method
``_list_models()`` that makes a GET request to the ollama API endpoint, and returns
the list of available models:

.. code:: python

    def _list_models(self) -> List[str]:
    """Helper method, used by status_check() to verify model availability.

    Returns:
        List of model names.

    Raises:
        Exception: If the API is not reachable.
    """
    response = self.client.list()
    models_list = response.get("models", [])

    model_names = []
    for model in models_list:
        name = model.get("model")
        if name:
            model_names.append(name)

    return model_names

After writing the helper method for making a GET request and returning the list of available
models, we can define another helper method, ``_match_model()``, that will check whether our
target model is in the list of available models:

.. code:: python

    def _match_model(self, model_name: str, available_models: List[str]) -> bool:
    """Check if a model name exists in the list of available models.
    Arguents:
        model_name: Name of the target model.
        available_models: List of available models to scan for target model.

    Returns:
        True if model_name found in available models, False if model_name not found in available models.
    """
    for model in available_models:
        if model_name == model:
            return True
    return False


With these helper methods, we can define our ``status_check()`` method. The ``status_check``
calls the ``_list_models()`` method to first attempt to make the GET request and get the list
of available models as a response. If it succeeds, the ``_match_model`` method is called to
check that our target model is in the list of available models. If it succeeds the ``status_check()``
returns ``True``. If either of the helper functions fail, the ``status_check()`` raises an error:

.. code:: python

    def status_check(self) -> bool:
    """Check if the connector can reach the Ollama API and the target model is available.

    Returns:
        True if API is reachable and the target model exists.

    Raises:
        ConnectionError: If the API is not reachable.
        ValueError: If the model is not found.
    """
    # Step 1: Check backend connectivity and get available models
    try:
        model_names = self._list_models()
    except Exception as e:
        raise ConnectionError(
            f"Cannot connect to Ollama backend at {self.base_url}: {e}"
        )

    # Step 2: Check if model exists
    logger.info(f"Available models found: {model_names}")

    if self._match_model(self.model, model_names):
        logger.info(f"Model '{self.model}' found.")
        return True

    raise ValueError(
        f"Model '{self.model}' not found in Ollama backend. "
        f"Available models: {model_names}"
    )


Defining generate()
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Next, let's write the ``generate()`` method. We want to be able to create SETs that use either
multi turn or single turn attacks to test a language model, so we will write ``_single_turn()``
and ``_multi_turn()`` helper methods to accommodate this. They are very similar, and only differ
in how the API request is made. Both have ``data`` parameter, that is a dictionary containing all
the required data for making the API request. And both return the model response in ``{"response": str}``
format.

.. code:: python
   :caption: ``_single_turn() helper method``

    def _single_turn(self, data: dict) -> dict:
    """Make a single-turn generation.

    Arguments:
        data: Dictionary with required data for API request.

    Returns:
        {"response": str}
    """
    if "system_prompt" in data:
        # Generate single-turn response with system prompt.
        try:
            response = self.client.generate(
                model=self.model,
                system=data["system_prompt"],
                prompt=data["prompt"],
                options={
                    "temperature": data["temperature"],
                    "num_predict": data["max_tokens"],
                },
            )
        except Exception as e:
            logger.error(
                f"{ansi_colors['red']}ERROR while generating response from model: {e}{ansi_colors['reset']}"
            )
            raise RuntimeError(
                "Failed to generate a response from model due to an error."
            ) from e
        return {"response": response.response}
    try:
        response = self.client.generate(
            model=self.model,
            prompt=data["prompt"],
            options={
                "temperature": data["temperature"],
                "num_predict": data["max_tokens"],
            },
        )
    except Exception as e:
        logger.error(
            f"{ansi_colors['red']}ERROR while generating response from model: {e}{ansi_colors['reset']}"
        )
        raise RuntimeError(
            "Failed to generate a response from model due to an error."
        ) from e
    return {"response": response.response}


.. code:: python
   :caption: ``_multi_turn() helper method``

    def _multi_turn(self, data: dict) -> dict:
    """Make a multi-turn generation.

    Arguments:
        data: Dictionary with required data for API request.

    Returns:
        {"response": str}
    """
    # Convert Message objects to Ollama's expected format
    ollama_messages = [
        {"role": msg.role, "content": msg.content} for msg in data["messages"]
    ]
    if "system_prompt" in data:
        # If system prompt is given in the data dict, insert it into ollama_messages
        ollama_messages.insert(
            0, {"role": "system", "content": data["system_prompt"]}
        )
    try:
        response = self.client.chat(
            model=self.model,
            messages=ollama_messages,
            options={
                "temperature": data["temperature"],
                "num_predict": data["max_tokens"],
            },
        )
        return {"response": response["message"]["content"]}
    except Exception as e:
        logger.error(
            f"{ansi_colors['red']}ERROR during chat with model: {e}{ansi_colors['reset']}"
        )
        raise RuntimeError(f"Failed to chat with model.") from e

Now with the help of ``_single_turn()`` and ``_multi_turn`` methods, we can write the ``generate()``
method. As we use ``generate()`` method to handle both, single turn and multi turn SET instances,
we need some way to differentiate when we are making a single turn or a multi turn generation. For this,
we can use a *boolean* parameter ``multi_turn``, that indicates what kind of a generation we are making
when calling this method. In addition, we give the required data for making the API request in a dictionary
``data`` parameter.

The ``generate()`` method checks that all expected fields have a valid value in the connector configuration
JSON file, and based on the value of the ``multi_turn`` parameter, executes the respective helper method.

.. code:: python
   :caption: ``generate()`` method

   def generate(self, data: dict, multi_turn: bool = False) -> dict:
        """Generate a response from the target model via the Ollama API.

        Arguments:
            data: Dictionary containing data required for the generation API request.
                Valid Keys:
                    - prompt : str
                        Prompt for single turn generation. Required for single turn conversation.
                    - messages: list[Message]
                        List of Message objects representing the conversation history.\
                        Message objects contain 'role' and 'content' attributes.\
                        Required for multi-turn conversation.
                    - system_prompt : str
                        Optional system prompt
                    - temperature : float [0, 1]
                        Optional temperature setting for the target model. Defaults to 0.5 if not set.
                    - max_tokens : int
                        Optional setting for maximum generated tokens. Defaults to 512 if not set.
            multi_turn: Boolean flag to indicate if engaging in a multi turn conversation\
                with the target model. Default False.

        Returns:
            API response.

        Raises:
            KeyError: If a required key is missing from data.
            ValueError: If a value in data is of a wrong type.
            RuntimeError: If the API call fails.
        """
        if "temperature" not in data:
            data["temperature"] = 0.5
        data["max_tokens"] = self.max_tokens

        if "system_prompt" in data:
            if not isinstance(data["system_prompt"], str):
                raise ValueError(
                    'If using "system_prompt" in data, it needs to be a string.'
                )

        if multi_turn:
            if "messages" not in data:
                raise KeyError(
                    'Multi-turn conversation requires a "messages" key in \
                               data variable, which contains a List of Message objects \
                               representing the conversation history.'
                )
            if not isinstance(data["messages"], list):
                raise ValueError(
                    'Multi-turn conversation requires a "messages" key in \
                               data variable, which contains a List of Message objects \
                               representing the conversation history.'
                )
            for message in data["messages"]:
                if not isinstance(message, Message):
                    raise ValueError(
                        'Multi-turn conversation requires a "messages" key in \
                               data variable, which contains a List of Message objects \
                               representing the conversation history.'
                    )
            return self._multi_turn(data=data)
        else:
            if "prompt" not in data:
                raise KeyError(
                    'Single-turn conversation requires a "prompt" key in \
                               data variable, which contains a prompt as a string.'
                )
            if not isinstance(data["prompt"], str):
                raise ValueError(
                    'Single-turn conversation requires a "prompt" key in \
                               data variable, which contains a prompt as a string.'
                )
            return self._single_turn(data=data)


Creating a configuration JSON file for the Connector
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To be able to pass the required values for making an API request with the connector,
we need to create a configuration JSON file for our new connector. All of the connector
configuration files are stored in the ``avise/configs/connector/`` directory, and as our
connector is intended for language models, we will insert our's into
``avise/configs/connector/languagemodel/`` directory as ``ollama.json``.

The configuration JSON should include all fields that are required for making an API request
with the connector (when we previously wrote the ``__init__`` method, we included each as an
instance attribute). If there are any optional fields that could be useful for some use-case,
we can set their value as ``null``:

.. code:: text
   :caption: ``avise/configs/connector/languagemodel/ollama.json``

    {
        "target_model": {
            "connector": "ollama-lm",
            "type": "language_model",
            "name": "phi3:latest",
            "api_url": "http://localhost:11434",
            "api_key": null,
            "max_tokens": 768
        }
    }

We need to give the name of our connector (which we defined earlier in the
:ref:`building_connector_section_2_init` section) into a ``connector`` field here,
so that the Execution Engine knows which connector we want to use when running SETs.
The ``type`` field might be used in later AVISE versions, so it is useful to include it.
It defines the type of the AI systems we are connecting to with the connector.


Testing the new Connector
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now that we have created a new Ollama Connector and a configuration JSON file for it,
it is time to make sure it works as we intended.
As we have created a connector for language model SET cases, we can try to run some available
SET with the new connector to see if it works. ``prompt_injection`` SET with the
``avise/configs/SET/languagemodel/single_turn/prompt_injection_mini.json`` configuration is great
for this as it executes quickly.

By running the ``prompt_injection`` SET in the root directory of AVISE, with the following command,
we can use the latest modification we have made to the codebase:

.. code:: bash

    python -m avise --SET prompt_injection --connectorconf avise/configs/connector/languagemodel/ollama.json --SETconf avise/configs/SET/languagemodel/single_turn/prompt_injection_mini.json

* ``--SET``: with this argument, we tell the CLI which SET we wish to execute.
* ``--connectorconf``: with this argument, we tell the CLI the path of the connector configuration JSON we just created.
* ``--SETconf``: with this optional argument, we can give the CLI a path to a custom SET configuration file (there are predefined default paths if we don't use this argument)

If our code has no errors and works as we intended, the Execution Engine starts running the SET and eventually produces
a report file and prints something like this to the console:

.. code:: text
    Security Evaluation Test completed!
        Format: JSON
        Total: 5
        Passed: 2 (40.0%)
        Failed: 3 (60.0%)
        Errors: 0

In the case that there were some errors in our code, we need to debug them until the SET cases execute fully.


Contributing the new Connector
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now that we have a functional new connector, we can contribute it to the main repository so other users can utilize
it as well! For details on how to contribute a connector to the main repository, check out :ref:`contributing_connector`.