"""Generic REST API Connector for Continual Learning systems."""

import logging
import requests

from .base import BaseCLConnector
from ...registry import connector_registry
from ...utils import ansi_colors

logger = logging.getLogger(__name__)


@connector_registry.register("generic-rest-cl")
class GenericRESTCLConnector(BaseCLConnector):
    """Connector for communicating with custom Continual Learning REST APIs.

    Used by Continual Learning SETs for querying a target model.
    """

    name = "generic-rest-cl"

    def __init__(self, config: dict):
        """Initialize the Generic REST API connector.

        Args:
            config: Dictionary containing data from Connector configuration JSON.
        """
        self.config = config
        try:
            self.base_url = config["target_model"]["api_endpoint"]["base"].get(
                "url", ""
            )
            if not self.base_url:
                raise ValueError(
                    '[["target_model"]"api_endpoint"]["base"]["url"] is not configured in the provided Generic REST CL Connector configuration file.'
                )
            if not isinstance(self.base_url, str):
                raise TypeError(
                    '[["target_model"]"api_endpoint"]["base"]["url"] must be a string in the Generic REST CL Connector configuration file.'
                )
            self.base_headers = config["target_model"]["api_endpoint"]["base"].get(
                "headers", ""
            )
            self.base_api_key = config["target_model"]["api_endpoint"]["base"].get(
                "api_key", ""
            )
            if not isinstance(self.base_api_key, (str, type(None))):
                raise TypeError(
                    '[["target_model"]"api_endpoint"]["base"]["api_key"] must be a string or null in the Generic REST CL Connector configuration file.'
                )
            self.base_method = config["target_model"]["api_endpoint"]["base"].get(
                "method", "POST"
            )
            if not self.base_method:
                self.base_method = "POST"
            if not isinstance(self.base_api_key, str):
                raise TypeError(
                    '[["target_model"]"api_endpoint"]["base"]["method"] must be a string in the Generic REST CL Connector configuration file.'
                )
            self.base_pred_field = config["target_model"]["api_endpoint"]["base"].get(
                "prediction_field", ""
            )
            if not isinstance(self.base_pred_field, str):
                self.base_pred_field = str(self.base_pred_field)
            if not self.base_pred_field:
                raise ValueError(
                    '["target_model"]["api_endpoint"]["base"]["prediction_field"] is required in the Generic REST CL Connector configuration file. It is the API response field that contains the target model´s prediction or response.'
                )
            if "train" in config["target_model"]["api_endpoint"]:
                if (
                    config["target_model"]["api_endpoint"]["train"].get("url")
                    is not None
                ):
                    self.train_url = config["target_model"]["api_endpoint"][
                        "train"
                    ].get("url")
                    if not isinstance(self.train_url, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["train"]["url"] must be a string in the Generic REST CL Connector configuration file.'
                        )
                    self.train_headers = config["target_model"]["api_endpoint"][
                        "train"
                    ].get("headers")
                    self.train_api_key = config["target_model"]["api_endpoint"][
                        "train"
                    ].get("api_key")
                    if not isinstance(self.train_api_key, (str, type(None))):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["train"]["api_key"] must be a string or null in the Generic REST CL Connector configuration file.'
                        )
                    self.train_method = config["target_model"]["api_endpoint"][
                        "train"
                    ].get("method", "POST")
                    if not isinstance(self.train_method, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["train"]["method"] must be a string in the Generic REST CL Connector configuration file.'
                        )
            if "inference" in config["target_model"]["api_endpoint"]:
                if (
                    config["target_model"]["api_endpoint"]["inference"].get("url")
                    is not None
                ):
                    self.infer_url = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("url")
                    if not isinstance(self.infer_url, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["inference"]["url"] must be a string in the Generic REST CL Connector configuration file.'
                        )
                    self.infer_headers = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("headers")
                    self.infer_api_key = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("api_key")
                    if not isinstance(self.infer_api_key, (str, type(None))):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["inference"]["api_key"] must be a string or null in the Generic REST CL Connector configuration file.'
                        )
                    self.infer_method = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("method", "POST")
                    if not isinstance(self.infer_method, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["inference"]["method"] must be a string in the Generic REST CL Connector configuration file.'
                        )
        except (KeyError, ValueError) as e:
            logger.error(
                f"{ansi_colors['red']}ERROR while generating initializing GenericRESTCLConnector: {e}{ansi_colors['reset']}"
            )
        logger.info(
            f"  Generic REST API Connector Initialized for Continual Learning target system."
        )
        logger.info(f"  Base URL: {self.base_url}")
        if self.base_api_key is not None:
            logger.info(
                f"  Base API Key: {'*' * 8}...{self.base_api_key[-4:] if len(self.base_api_key) > 4 else '****'}"
            )
        if self.train_api_key is not None:
            logger.info(
                f"  Train API Key: {'*' * 8}...{self.train_api_key[-4:] if len(self.train_api_key) > 4 else '****'}"
            )
        if self.infer_api_key is not None:
            logger.info(
                f"  Inference API Key: {'*' * 8}...{self.infer_api_key[-4:] if len(self.infer_api_key) > 4 else '****'}"
            )

    def query(self, data: list):
        """TODO"""
        pass

    def status_check(self):
        """TODO"""
        pass
