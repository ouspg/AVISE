"""
Base class for evaluators.
Evaluators look for predetermined patterns in responses.
"""
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple

logger = logging.getLogger(__name__)


class BaseLMEvaluator(ABC):
    """
    Abstract base class for language model evaluators.

    Attributes:
        name: Unique identifier for the evaluator
        description: Description of what the evaluator detects
        patterns: List of regex patterns used for detection
    """

    name: str = ""
    description: str = ""
    patterns: List[str] = []

    @abstractmethod
    def detect(self, response: str) -> Tuple[bool, List[str]]:
        """
        Detect patterns in response.

        Args:
            response: The response to evaluate

        Returns:
            Tuple containing:
            - Detection (bool): True if patterns were found, False otherwise
            - Found patterns (List[str]): List of patterns that were found in the response
        """
        pass

    def _find_pattern_matches(self, text: str) -> List[str]:
        """
        Find all matching patterns in the given response

        Method that iterates through the patterns definined in the evaluator
        and returns a list of all patterns that match.

        Args:
            text: Text to search for patterns

        Returns:
            List of matched pattern strings (cleaned for readability)
        """
        matches = []
        for pattern in self.patterns:
            if re.search(pattern, text):
                readable = pattern.replace(r"(?i)", "").replace("\\s+", " ").strip()
                matches.append(readable)
        return matches
