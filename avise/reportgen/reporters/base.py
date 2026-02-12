"""
Base class for report writers.

Reporters handle writing the final report from ReportData to different file formats (JSON, HTML, MD)
"""
from abc import ABC, abstractmethod
from pathlib import Path

from ...pipelines.languagemodel import ReportData


class BaseReporter(ABC):
    """
    Base class for report writers.

    Each reporter handles a specific output format (JSON, HTML, MD).
    """

    format_name: str = ""
    file_extension: str = ""

    @abstractmethod
    def write(self, report_data: ReportData, output_path: Path) -> None:
        """
        Write report data to a file.

        Args:
            report_data: The report data to write
            output_path: Path to the output file / directory
        """
        pass

    @staticmethod
    def escape_html(text: str) -> str:
        """
        Helper method for escaping special HTML characters.
        Done to prevent possibly malicious outputs from the SETs from causing problems when rendering HTML
        """
        return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))
