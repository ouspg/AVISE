"""
Base class for analyzers.
Analyzers look for predetermined patterns in responses.
"""
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """
    Abstract base class for analyzers.

    Attributes:
        name: Unique identifier for the analyzer
        description: Description of what the analyzer detects
        patterns: List of regex patterns used for detection
    """

    name: str = ""
    description: str = ""
    patterns: List[str] = []

    @abstractmethod
    def detect(self, response: str) -> Tuple[bool, List[str]]:
        """
        Analyze a response for patterns

        Args:
            response: The response to analyze

        Returns:
            Tuple containing:
            - Detection (bool): True if patterns were found, False otherwise
            - Found patterns (List[str]): List of patterns that were found in the response
        """
        pass

    def _find_pattern_matches(self, text: str) -> List[str]:
        """
        Find all matching patterns in the given response

        Method that iterates through the patterns definined in the analyzer
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
