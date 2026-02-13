"""
Language Model Connector for Custom/Generic REST APIs.
"""
import logging
import requests

from .base import BaseLMConnector
from ...registry import connector_registry

logger = logging.getLogger(__name__)

@connector_registry.register("generic-rest-lm")
class GenericRESTLMConnector(BaseLMConnector):
    """
    Connector for communicating with custom REST APIs.

    Used by tests for sending prompts to testable models and collecting their responses.
    Supports both simple generation and generation with system prompts.
    """

    name = "generic-rest-lm"

    def __init__(
        self,
        config: dict,
        evaluation: bool = False
    ):
        """
        Initialize the Generic REST API connector.

        Args:
            config: Dictionary containing data from Connector configuration JSON.
            evaluation: Boolean flag indicating whether initializing a connector for the target model or the evaluation model
        """
        self.config = config
        try:
            if evaluation:
                self.url = config["eval_model"]["api_url"]
                self.name = config["eval_model"]["name"]
                self.method = config["eval_model"]["method"]
                self.response_field = config["eval_model"]["response_field"]
                if "api_key" in config["eval_model"] and config["eval_model"]["api_key"] is not None:
                    self.api_key = config["eval_model"]["api_key"]
                else:
                    self.api_key = None
                if "headers" in config["eval_model"] and config["eval_model"]["headers"] is not None:
                    self.headers = config["eval_model"]["headers"]
                else:
                    self.headers = None
                if "time_out" in config["eval_model"] and config["eval_model"]["time_out"] is not None:
                    self.time_out = config["eval_model"]["time_out"]
                else:
                    self.time_out = 30

            else:
                self.url = config["target_model"]["api_url"]
                self.name = config["target_model"]["name"]
                self.method = config["target_model"]["method"]
                self.response_field = config["target_model"]["response_field"]
                if "api_key" in config["target_model"] and config["target_model"]["api_key"] is not None:
                    self.api_key = config["target_model"]["api_key"]
                else:
                    self.api_key = None
                if "headers" in config["target_model"] and config["target_model"]["headers"] is not None:
                    self.headers = config["target_model"]["headers"]
                else:
                    self.headers = None
                if "time_out" in config["target_model"] and config["target_model"]["time_out"] is not None:
                    self.time_out = config["target_model"]["time_out"]
                else:
                    self.time_out = 30
        except (KeyError, ValueError) as e:
            logger.error(f"ERROR while generating initializing GenericRESTLMConnector: {e}")

        conn = f"Evaluation model {self.name}" if evaluation else f"Target model: {self.name}"
        logger.info(f"  Generic REST API Connector Initialized for {conn}")
        logger.info(f"  Base URL: {self.url}")
        if self.api_key is not None:
            logger.info(f"  API Key: {'*' * 8}...{self.api_key[-4:] if len(self.api_key) > 4 else '****'}")
    
    def generate(self,
                 data: dict,
                 ) -> dict:
        """
        Function for making generation requests to the REST API.

        Arguments:
            data: Dictionary containing the required data for the API request.
        Returns:
            API response as a dict. The dict includes a "response" key with the model response.
        """

        try:
            if self.method == "POST":
                if self.headers is None:
                    response = requests.post(url=self.url, data=data, timeout=self.time_out)
                else:
                    response = requests.post(url=self.url, data=data, headers=self.headers, timeout=self.time_out)
            elif self.method == "GET":
                if self.headers is None:
                    response = requests.get(url=self.url, data=data, timeout=self.time_out)
                else:
                    response = requests.get(url=self.url, data=data, headers=self.headers, timeout=self.time_out)
            elif self.method == "PUT":
                if self.headers is None:
                    response = requests.put(url=self.url, data=data, timeout=self.time_out)
                else:
                    response = requests.put(url=self.url, data=data, headers=self.headers, timeout=self.time_out)
            else:
                raise ValueError(f"GenericRESTLMConnector currently only supports POST, \
                                 GET, and PUT methods. Attempted to generate a response \
                                 with {self.method} method.")
        except Exception as e:
            logger.error(f"ERROR while generating response from model: {e}")
            raise RuntimeError("Failed to generate a response from model due to an error.") from e
        
        response_data = response.json()
        response_data[self.response_field] = response_data.get(self.response_field)
        return response_data

    def status_check(self) -> bool:
        """
        Check if the configured API endpoint is available with a GET request.
        """
        try:
            response = requests.get(self.url, timeout=self.time_out) if self.headers is None else requests.get(self.url, headers=self.headers, timeout=self.time_out)
        except Exception as e:
            logger.error(f"ERROR while doing a status check on the configured API endpoint: {e}")
            raise RuntimeError(f"Failed to send a request to url: {self.url} due to an error.") from e
        response = response.json()
        try:
            if response.status_code == 200:
                return True
        except (KeyError, ValueError) as e:
            logger.error(f"ERROR while doing a status check on the configured API endpoint: {e}")
            raise RuntimeError(f"Status check failed on the configured API endpoint at \
                               url:{self.url}. Response did not have a valid status_code field.") from e
        logger.error(f"Status check failed on the configured API endpoint at url:{self.url}.\
                          Response status_code should be 200, received {response.status_code} instead.")
        return False
