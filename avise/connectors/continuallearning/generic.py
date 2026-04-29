"""TODO"""

import logging
import requests

from .base import BaseCLConnector
from ...registry import connector_registry
from ...utils import ansi_colors

logger = logging.getLogger(__name__)


@connector_registry.register("generic-rest-lm")
class GenericRESTCLConnector(BaseCLConnector):
    """Connector for communicating with custom REST APIs.

    Used by Continual Learning SETs for ..
    """

    name = "generic-rest-cl"

    def __init__(self, config: dict, evaluation: bool = False):
        """Initialize the Generic REST API connector.

        Args:
            config: Dictionary containing data from Connector configuration JSON.
            evaluation: Boolean flag indicating whether initializing a connector for the target model or the evaluation model
        """
        self.config = config
