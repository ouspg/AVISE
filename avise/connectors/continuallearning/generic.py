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

            self.base_method = config["target_model"]["api_endpoint"]["base"].get(
                "method", "POST"
            )
            if not self.base_method:
                self.base_method = "POST"
            if not isinstance(self.base_method, str):
                raise TypeError(
                    '[["target_model"]"api_endpoint"]["base"]["method"] must be a string in the Generic REST CL Connector configuration file.'
                )
            self.time_out = config["target_model"]["api_endpoint"]["base"].get(
                "time_out", 30
            )
            if not isinstance(self.time_out, int):
                raise TypeError(
                    '[["target_model"]"api_endpoint"]["base"]["time_out"] must be an int in the Generic REST CL Connector configuration file.'
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
            self.base_confidence_field = config["target_model"]["api_endpoint"][
                "base"
            ].get("confidence_field", None)
            if self.base_confidence_field:
                if not isinstance(self.base_confidence_field, str):
                    self.base_confidence_field = str(self.base_confidence_field)
            self.base_probabilities_field = config["target_model"]["api_endpoint"][
                "base"
            ].get("probabilities_field", None)
            if self.base_probabilities_field:
                if not isinstance(self.base_probabilities_field, str):
                    self.base_probabilities_field = str(self.base_probabilities_field)
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
                    self.train_method = config["target_model"]["api_endpoint"][
                        "train"
                    ].get("method", "POST")
                    if not isinstance(self.train_method, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["train"]["method"] must be a string in the Generic REST CL Connector configuration file.'
                        )
            else:
                self.train_url = None
                self.train_headers = None
                self.train_method = None
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
                    self.infer_method = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("method", "POST")
                    if not isinstance(self.infer_method, str):
                        raise TypeError(
                            '["target_model"]["api_endpoint"]["inference"]["method"] must be a string in the Generic REST CL Connector configuration file.'
                        )

                    self.infer_pred_field = config["target_model"]["api_endpoint"][
                        "inference"
                    ].get("prediction_field", None)
                    if self.infer_pred_field:
                        if not isinstance(self.infer_pred_field, str):
                            self.infer_pred_field = str(self.infer_pred_field)
                    self.infer_confidence_field = config["target_model"][
                        "api_endpoint"
                    ]["inference"].get("confidence_field", None)
                    if self.infer_confidence_field:
                        if not isinstance(self.infer_confidence_field, str):
                            self.infer_confidence_field = str(
                                self.infer_confidence_field
                            )
                    self.infer_probabilities_field = config["target_model"][
                        "api_endpoint"
                    ]["inference"].get("probabilities_field", None)
                    if self.infer_probabilities_field:
                        if not isinstance(self.infer_probabilities_field, str):
                            self.infer_probabilities_field = str(
                                self.infer_probabilities_field
                            )
            else:
                self.infer_url = None
                self.infer_headers = None
                self.infer_method = None
                self.infer_pred_field = None
                self.infer_confidence_field = None
                self.infer_probabilities_field = None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                f"{ansi_colors['red']}ERROR while initializing GenericRESTCLConnector: {e}{ansi_colors['reset']}"
            )
        logger.info(
            f"  Generic REST API Connector Initialized for Continual Learning Target System."
        )
        logger.info(f"  Base URL: {self.base_url}")

    def query(self, data: list, task="inference") -> dict:
        """Function for making query requests to the target REST API.

        Arguments:
            data: Dictionary containing the required data for the API request.
            task: "inference" for inference query | "train" for training query.

        Returns:
            API response as a dict. The dict includes a "response" key containing the target system's response.
        """
        try:
            if task == "inference":
                if self.infer_url:
                    if self.infer_method == "POST":
                        if self.infer_headers is None:
                            response = requests.post(
                                url=self.infer_url, data=data, timeout=self.time_out
                            )
                        else:
                            response = requests.post(
                                url=self.infer_url,
                                data=data,
                                headers=self.infer_headers,
                                timeout=self.time_out,
                            )
                    else:
                        raise NotImplementedError(
                            "Only POST methods are implemented for inference requests in CL Generic REST Connector."
                        )
                else:
                    # Use the base url for inference request
                    if self.base_method == "POST":
                        if self.base_headers is None:
                            response = requests.post(
                                url=self.base_url, data=data, timeout=self.time_out
                            )
                        else:
                            response = requests.post(
                                url=self.base_url,
                                data=data,
                                headers=self.base_headers,
                                timeout=self.time_out,
                            )
                    else:
                        raise NotImplementedError(
                            "Only POST methods are implemented for inference requests in CL Generic REST Connector."
                        )
            elif task == "train":
                if self.train_url:
                    # Make a traning request
                    if self.train_method == "POST":
                        if self.train_headers is None:
                            response = requests.post(
                                url=self.train_url, data=data, timeout=self.time_out
                            )
                        else:
                            response = requests.post(
                                url=self.train_url,
                                data=data,
                                headers=self.train_headers,
                                timeout=self.time_out,
                            )
                    else:
                        raise NotImplementedError(
                            "Only POST methods are implemented for training requests in CL Generic REST Connector."
                        )
                else:
                    # Use the base url for training request
                    if self.base_method == "POST":
                        if self.base_headers is None:
                            response = requests.post(
                                url=self.base_url, data=data, timeout=self.time_out
                            )
                        else:
                            response = requests.post(
                                url=self.base_url,
                                data=data,
                                headers=self.base_headers,
                                timeout=self.time_out,
                            )
                    else:
                        raise NotImplementedError(
                            "Only POST methods are implemented for training requests in CL Generic REST Connector."
                        )
            else:
                raise ValueError(
                    'Only "inference" and "train" are valid values for `task` in GenericRESTCLConnector.query()'
                )

        except Exception as e:
            logger.error(
                f"{ansi_colors['red']}ERROR while querying Continual Learning system: {e}{ansi_colors['reset']}"
            )
            raise RuntimeError(
                "Failed to query the Continual Learning target system due to an error."
            ) from e
        return response.json()

    def status_check(self):
        """Check if the configured API endpoint(s) is available with a GET request."""
        try:
            if self.infer_url:
                response = (
                    requests.get(self.infer_url, timeout=self.time_out)
                    if self.infer_headers is None
                    else requests.get(
                        self.infer_url,
                        headers=self.infer_headers,
                        timeout=self.time_out,
                    )
                )
            else:
                response = (
                    requests.get(self.base_url, timeout=self.time_out)
                    if self.base_headers is None
                    else requests.get(
                        self.base_url, headers=self.base_headers, timeout=self.time_out
                    )
                )
            response1 = response.json()

            if self.train_url:
                # Perform status check for the training endpoint
                response = (
                    requests.get(self.train_url, timeout=self.time_out)
                    if self.train_headers is None
                    else requests.get(
                        self.train_url,
                        headers=self.train_headers,
                        timeout=self.time_out,
                    )
                )
                response2 = response.json()
                try:
                    if response1.status_code == 200:
                        if response2.status_code == 200:
                            return True
                except (KeyError, ValueError) as e:
                    logger.error(
                        f"{ansi_colors['red']}ERROR while doing a status check on the configured API endpoint: {e}{ansi_colors['reset']}"
                    )
                    raise RuntimeError(
                        f"Status check failed on the configured API endpoint at \
                                    url:{self.base_url}. Response did not have a valid status_code field."
                    ) from e
            try:
                if response1.status_code == 200:
                    return True
            except (KeyError, ValueError) as e:
                logger.error(
                    f"{ansi_colors['red']}ERROR while doing a status check on the configured API endpoint: {e}{ansi_colors['reset']}"
                )
                raise RuntimeError(
                    f"Status check failed on the configured API endpoint at \
                                url:{self.base_url}. Response did not have a valid status_code field."
                ) from e
        except Exception as e:
            logger.error(
                f"{ansi_colors['red']}ERROR while doing a status check on the configured API endpoint: {e}{ansi_colors['reset']}"
            )
            raise RuntimeError(
                f"Failed to send a GET request to url: {self.base_url} due to an error."
            ) from e
        return False
