"""Output path builder."""

from pathlib import Path
from datetime import datetime

from . import ReportFormat


def build_output_path(
        base_dir: str,
        set_name: str,
        model_name: str,
        report_format: ReportFormat
    ) -> str:
        """Function for crafting an output path with date-based subdirectory when an output directory is not provided.

        Creates: base_dir/YYYY-MM-DD/set_name_model_timestamp.ext
        """
        time = datetime.now()
        date_dir = time.strftime("%Y-%m-%d")
        timestamp = time.strftime("%H%M%S")
        fixed_model_name = model_name.replace(":", "_").replace("/", "_")
        extension = report_format.value
        filename = f"{set_name}_{fixed_model_name}_{timestamp}.{extension}"
        return str(Path(base_dir) / date_dir / filename)
