"""
JSON report writer.
"""
import json
from pathlib import Path

from .base import BaseReporter
from ...pipelines.language_model import ReportData


class JSONReporter(BaseReporter):
    """
    Writes reports in JSON format.
    """

    format_name = "json"
    file_extension = ".json"

    def write(self, report_data: ReportData, output_path: Path) -> None:
        """
        Write report data as JSON file, including grouped results.

        Args:
            report_data: The report data to write
            output_path: Path to the output file / directory
        """

        data = report_data.to_dict()

        # Add grouped_results
        if hasattr(report_data, "grouped_results") and report_data.grouped_results:
            data["grouped_results"] = report_data.grouped_results

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
