"""
Base class for connectors / API clients

Connectors communicate with different backends by sending test prompts to them in a desired format, retrieving the outputs from the LLMs / AI models, and
sending original test prompts along with the output to an evaluative language model (ELM) for further vulnerability analysis.  

By abstracting the communication with different APIs to different connectors users can focus more on developing test cases and just pick a suitable API client
for their use case.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """
    Represents a single message in a multi-turn conversation

    Attributes:
        role: The role of the message sender. "system", "user", or "assistant": https://platform.openai.com/docs/guides/text
        content: The text content of the message
    """
    role: str
    content: str


class BaseLMConnector(ABC):
    """
    A connector handles communication with a specific API / backend,
    abstracting the API usage for the framework.
    This allows SET cases to be written only once and users are able to run them against different models with different configurations.

    Class Methods:
    - generate(): Generate a response from target model.
    - status_check(): Verify that the target API endpoint is available.

    Class Attributes:
        name: Connector type identifier
        model (Optional): Target model defined in configuration file.
        api_key (Optional): Optional authorization API key (passed as a command line argument -apikey KEY or alternatively in a connector configuration file). 

        

    - single_turn(): Send a single prompt and get a response
    - multi_turn(): Send prompts, collect conversation history, and send conversation history back to the stateless API backend for history context.
    - single_turn_with_system_prompt(): Send a single prompt with a system prompt and get a response. 
        Used for providing contextual instructions to the evaluative language model.
    - health_check(): Verify the backend is available
    - list_models(): Get the list of available models on the backend. Used for 

    Class Attributes:
        name: Connector type identifier
        model: The specific model being used by the connertor (Defined in the configuration)
        api_key: Optional API key for authentication (Passed as a command line argument -apikey KEY)
    """

    name: str = ""
    model: Optional[str] = ""
    api_key: Optional[str] = None

    @abstractmethod
    def generate(
        self,
        data: dict,
        multi_turn: bool = False
    ) -> dict:
        """
        Generate a response from the target model via the target API.

        Arguments:
            data: Dictionary containing data required for the generation API request.
            multi_turn: Boolean flag to indicate if engaging in a multi turn conversation\
                with the target model. Default False.
        Raises:
            RuntimeError: If the API call fails.
        """
        pass

    @abstractmethod
    def status_check(self) -> bool:
        """
        Perform a status check for the target API via a GET request.

        Raises:
            Exception: If the target API is not reachable.
        """
        pass
