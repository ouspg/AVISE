"""
JSON report writer.
"""
import json
from pathlib import Path

from .base import BaseReporter
from ...pipelines.languagemodel import ReportData


class JSONReporter(BaseReporter):
    """
    Writes reports in JSON format.
    
    """

    format_name = "json"
    file_extension = ".json"

    def write(self, report_data: ReportData, output_path: Path) -> None:
        """
        Write report data as JSON file.

        Args:
            report_data: The report data to write
            output_path: Path to the output file / directory
        """
        with open(output_path, 'w') as f:
            json.dump(report_data.to_dict(), f, indent=2)
