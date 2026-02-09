"""
Language Model Connector for Custom/Generic REST APIs.
"""
import logging
import requests
from typing import List, Optional

from .base import BaseLMConnector
from ...registry import connector_registry
from ...utils import ConfigLoader

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
        config_path: str,
    ):
        """
        Initialize the Generic REST API connector.

        Args:
            config_path: Path to the Connector configuration file. TODO: Link to docs on how to create config file.
        """
        self.config = ConfigLoader().load(config_path)
        self.url = self.config["rest"]["RESTLMConnector"]["url"]
        if "api_key" in self.config["rest"]["RESTLMConnector"]:
            self.api_key = self.config["rest"]["RESTLMConnector"]["api_key"]
        else:
            self.api_key = None
        if "headers" in self.config["rest"]["RESTLMConnector"]:
                self.headers = self.config["rest"]["RESTLMConnector"]["headers"]
        else:
            self.headers = None

        logger.info(f"  Generic REST API Connector Initialized")
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
            method = self.config["rest"]["RESTLMConnector"]["method"]
            model_response_field = self.config["rest"]["RESTLMConnector"]["response_field"]
            
        except Exception as e:
            logger.error(f"ERROR while loading RESTLMConnector configuration file: {e}")
            raise ValueError("A required field is missing from RESTLMConnector configuration\
                              file. TODO: add link to docs.") from e
        
        try:
            if method == "POST":
                if self.headers is None:
                    response = requests.post(url=self.url, data=data)
                else:
                    response = requests.post(url=self.url, data=data, headers=self.headers)
            elif method == "GET":
                if self.headers is None:
                    response = requests.get(url=self.url, data=data)
                else:
                    response = requests.get(url=self.url, data=data, headers=self.headers)
            elif method == "PUT":
                if self.headers is None:
                    response = requests.put(url=self.url, data=data)
                else:
                    response = requests.put(url=self.url, data=data, headers=self.headers)
            else:
                raise ValueError(f"GenericRESTLMConnector currently only supports POST, \
                                 GET, and PUT methods. Attempted to generate a response \
                                 with {method} method.")
        except Exception as e:
            logger.error(f"ERROR while generating response from model: {e}")
            raise RuntimeError("Failed to generate a response from model due to an error.") from e
        
        response_data = response.json()
        response_data["response"] = response_data.get(model_response_field)
        return response_data

    def status_check(self) -> bool:
        """
        Check if the configured API endpoint is available with a GET request.
        """
        try:
            response = requests.get(self.url) if self.headers is None else requests.get(self.url, headers=self.headers)
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