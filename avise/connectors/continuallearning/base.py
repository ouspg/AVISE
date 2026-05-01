"""Base class for CL Connectors.

A Connector acts as the bridge between Security Evaluation Tests and a target system.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class BaseCLConnector(ABC):
    """A connector handles communication with a specific API / backend, abstracting
    the API usage for the framework. This allows SET cases to be written only once
    and users are able to run them against different models with different configurations.

    Class Methods:
        - query: Query the target model.

    Class Attributes:
        - config: Connector configuration data.
    """

    config: dict = {}

    @abstractmethod
    def query(self, data: list) -> dict:
        """"""
        pass

    @abstractmethod
    def status_check(self) -> bool:
        """Perform a status check for the target API via a GET request.

        Returns:
            True if status check was successful.

        Raises:
            Exception: If the target API is not reachable.
        """
        pass
