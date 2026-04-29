"""TODO"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class BaseCLConnector(ABC):
    """A connector handles communication with a specific API / backend,
    abstracting the API usage for the framework.
    This allows SET cases to be written only once and users are able to run them against different models with different configurations.

    Class Methods:

    Class Attributes:

    """

    pass
