"""
Connector for OpenAI API communication.

Supports GPT-4, GPT-3.5-turbo, and other OpenAI chat completion models.
"""
import logging
from typing import List, Optional

from openai import OpenAI

from .base import BaseLMConnector, Message
from ...registry import connector_registry

logger = logging.getLogger(__name__)


@connector_registry.register("openai-lm")
class OpenAILMConnector(BaseLMConnector):
    """
    Connector for communicating with the OpenAI API.

    Used by SETs for sending prompts to OpenAI models and collecting their responses.
    Supports both simple generation and generation with system prompts.

    Requires an API key, which can be passed via:
    - Constructor argument
    - Model config file (api_key field)
    - Command line (--apikey argument)
    """

    name = "openai-lm"

    # Default models
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize the OpenAI connector.

        Args:
            model: Model name for generation (e.g., gpt-4o-mini, gpt-4o, gpt-3.5-turbo)
            api_key: OpenAI API key (required)
            base_url: Optional custom base URL (for Azure OpenAI or proxies)
        """
        if not api_key:
            raise ValueError("OpenAI connector requires an API key. Use --apikey CLI argument or add 'api_key' to model configuration file.")

        self.model = model
        self.api_key = api_key
        self.base_url = base_url

        # Initialize OpenAI client
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)

        logger.info(f"  OpenAI Connector Initialized")
        logger.info(f"  Model: {model}")
        if base_url:
            logger.info(f"  Base URL: {base_url}")
        logger.info(f"  API Key: {'*' * 8}...{api_key[-4:] if len(api_key) > 4 else '****'}")
    
    def generate(self,
                 data: dict,
                 multi_turn: bool = False
    ) -> dict:
        """
        Generate a response from the target model via the OpenAI API.

        Arguments:
            data: Dictionary containing data required for the generation API request.
                Valid Keys:
                    - prompt : str
                        Prompt for single turn generation. Required for single turn generation.
                    - messages: list[Message]
                        List of Message objects representing the conversation history.\
                        Message objects contain 'role' and 'content' attributes.\
                        Required for multi-turn conversation.
                    - system_prompt : str
                        Optional system prompt that define the model's behavior, role, or constraints.
                    - temperature : float [0, 1]
                        Optional temperature setting for the target model. Defaults to 0.5 if not set.
                    - max_tokens : int
                        Optional setting for maximum generated tokens. Defaults to 512 if not set.
            multi_turn: Boolean flag to indicate if engaging in a multi turn conversation\
                with the target model. Default False.
        Returns:
            Generated response in format: {"response": str}
        Raises:
            KeyError: If a required key is missing from data.
            ValueError: If a value in data is of a wrong type.
            RuntimeError: If the API call fails.
        """
        if "temperature" not in data:
            data["temperature"] = 0.5
        if "max_tokens" not in data:
            data["max_tokens"] = 512

        if "system_prompt" in data:
            if not isinstance(data["system_prompt"], str):
                raise ValueError('If using "system_prompt" in data, it needs to be a string.')

        if multi_turn:
            if "messages" not in data:
                raise KeyError('Multi-turn conversation requires a "messages" key in \
                               data variable, which contains a List of Message objects \
                               representing the conversation history.')
            if not isinstance(data["messages"], list):
                raise ValueError('Multi-turn conversation requires a "messages" key in \
                               data variable, which contains a List of Message objects \
                               representing the conversation history.')
            for message in data["messages"]:
                if not isinstance(message, Message):
                    raise ValueError('Multi-turn conversation requires a "messages" key in \
                               data variable, which contains a List of Message objects \
                               representing the conversation history.')
            return self._multi_turn(data=data)
        else:
            if "prompt" not in data:
                raise KeyError('Single-turn conversation requires a "prompt" key in \
                               data variable, which contains a prompt as a string.')
            if not isinstance(data["prompt"], str):
                raise ValueError('Single-turn conversation requires a "prompt" key in \
                               data variable, which contains a prompt as a string.')
            return self._single_turn(data=data)

    def _single_turn(self,
                     data: dict
                     ) -> dict:
        """
        Make a single-turn generation.
        Arguments:
            data: Dictionary with required data for API request.
        Returns:
            {"response": str}
        """
        if "system_prompt" in data:
            # Generate with system prompt
            messages = [{"role": "system", "content": data["system_prompt"]},
                        {"role": "user", "content": data["prompt"]}
            ]
        else:
            # Generate without system prompt
            messages = [
                    {"role": "user", "content": data["prompt"]}
            ]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=data["temperature"],
                max_tokens=data["max_tokens"]
            )
            return {"response": response.choices[0].message.content or ""}

        except Exception as e:
            logger.error(f"ERROR while generating response from OpenAI: {e}")
            raise RuntimeError(f"Failed to generate response from OpenAI: {e}")


    def _multi_turn(self,
                    data: dict,
                    ) -> dict:
        """
        Make a multi-turn generation.
        Arguments:
            data: Dictionary with required data for API request.
        Returns:
            {"response": str}
        """
        try:
            # Convert Message objects to OpenAI's expected format
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in data["messages"]
            ]
            if "system_prompt" in data:
                # Add system prompt as the first message in conversation
                openai_messages.insert(0, {"role": "system", "content": data["system_prompt"]})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                temperature=data["temperature"],
                max_tokens=data["max_tokens"]
            )
            return {"response": response.choices[0].message.content or ""}

        except Exception as e:
            logger.error(f"ERROR during chat with OpenAI: {e}")
            raise RuntimeError(f"Failed to chat with OpenAI: {e}")


    def status_check(self) -> bool:
        """
        Check if the connector can reach the OpenAI API endpoint and the target model is available.

        Returns:
            True if API is reachable and the target model exists.

        Raises:
            ConnectionError: If the API is not reachable.
            ValueError: If the model is not found.
        """
        # Step 1: Check API connectivity and API key validity
        try:
            model_ids = self._list_models()
        except Exception as e:
            base_url_info = f" at {self.base_url}" if self.base_url else ""
            raise ConnectionError(f"Cannot connect to OpenAI API{base_url_info}: {e}")

        # Step 2: Check if model exists
        logger.info(f"Available models found: {len(model_ids)} models")

        if self.model in model_ids:
            logger.info(f"Model '{self.model}' is available.")
            return True

        # Note: Some models (fine-tuned, newer) may not appear in list but still work
        logger.warning(
            f"Model '{self.model}' not found in available models list. "
            f"Proceeding anyway as some models may not be listed."
        )
        return True

    def _list_models(self) -> List[str]:
        """
        Helper function, used by health_check() to verify model availability.

        Returns:
            List of model names.
        """
        models = self.client.models.list()
        return [m.id for m in models.data]
