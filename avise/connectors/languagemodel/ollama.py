"""
Connector for Ollama API communication using the ollama library.
"""
import logging
import ollama
from typing import List, Optional

from .base import BaseLMConnector, Message
from ...registry import connector_registry

logger = logging.getLogger(__name__)


@connector_registry.register("ollama-lm")
class OllamaLMConnector(BaseLMConnector):
    """
    Connector for communicating with the Ollama API.

    Used by Security Evaluation Tests for sending prompts to target Ollama models and collecting their responses.
    """

    name = "ollama-lm"

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        api_key: Optional[str] = None
    ):
        """
        Initialize the Ollama connector.

        Args:
            model: Target model name for generation (For example: llama3.2:3b)
            base_url: Base URL for Ollama API (For example: http://localhost:11434)
            api_key: Optional API key for authenticated Ollama instances
        """
        self.model = model
        self.base_url = base_url
        self.api_key = api_key

        # Configure client with optional authentication headers
        if api_key:
            self.client = ollama.Client(
                host=base_url,
                headers={"Authorization": f"Bearer {api_key}"}
            )
        else:
            self.client = ollama.Client(host=base_url)

        logger.info(f"  Ollama Connector Initialized")
        logger.info(f"  Base URL: {base_url}")
        logger.info(f"  Model: {model}")
        if api_key:
            logger.info(f"  API Key: {'*' * 8}...{api_key[-4:] if len(api_key) > 4 else '****'}")

    def generate(self,
                 data: dict,
                 multi_turn: bool = False
                 ) -> dict:
        """
        Generate a response from the target model via the Ollama API.

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


    def _multi_turn(self,
                    data: dict
                    ) -> dict:
        """
        Make a multi-turn generation.
        Arguments:
            data: Dictionary with required data for API request.
        Returns:
            {"response": str}
        """
        # Convert Message objects to Ollama's expected format
        ollama_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in data["messages"]
        ]
        if "system_prompt" in data:
            # If system prompt is given in the data dict, insert it into ollama_messages
            ollama_messages.insert(0, {"role": "system", "content": data["system_prompt"]})
        try:
            response = self.client.chat(
                model=self.model,
                messages=ollama_messages,
                options={
                    "temperature": data["temperature"],
                    "num_predict": data["max_tokens"]
                }
            )
            return {"response": response["message"]["content"]}
        except Exception as e:
            logger.error(f"ERROR during chat with model: {e}")
            raise RuntimeError(f"Failed to chat with model: {e}")

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
            #Generate single-turn response with system prompt.
            try:
                response = self.client.generate(
                model=self.model,
                system=data["system_prompt"],
                prompt=data["prompt"],
                options={
                    "temperature": data["temperature"],
                    "num_predict": data["max_tokens"]
                    }
                )
            except Exception as e:
                logger.error(f"ERROR while generating response from model: {e}")
                raise RuntimeError(f"Failed to generate a response from model due to an error: {e}")
            return {"response": response.response}
        try:
            response = self.client.generate(
            model=self.model,
            prompt=data["prompt"],
            options={
                "temperature": data["temperature"],
                "num_predict": data["max_tokens"]
                }
            )
        except Exception as e:
            logger.error(f"ERROR while generating response from model: {e}")
            raise RuntimeError(f"Failed to generate a response from model due to an error: {e}")
        return {"response": response.response}


    def _match_model(self, model_name: str, available_models: List[str]) -> bool:
        """
        Check if a model name exists in the list of available models.
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

    def status_check(self) -> bool:
        """
        Check if the connector can reach the Ollama API and the target model is available.

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
            raise ConnectionError(f"Cannot connect to Ollama backend at {self.base_url}: {e}")

        # Step 2: Check if model exists
        logger.info(f"Available models found: {model_names}")

        if self._match_model(self.model, model_names):
            logger.info(f"Model '{self.model}' found.")
            return True

        raise ValueError(
            f"Model '{self.model}' not found in Ollama backend. "
            f"Available models: {model_names}"
        )

    def _list_models(self) -> List[str]:
        """
        Helper function, used by status_check() to verify model availability.

        Returns:
            List of model names.

        Raises:
            Exception: If the API is not reachable.
        """
        response = self.client.list()
        models_list = response.get('models', [])

        model_names = []
        for model in models_list:
            name = model.get("model")
            if name:
                model_names.append(name)

        return model_names
