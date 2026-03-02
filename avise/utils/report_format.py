"""ReportFormat util class"""

from enum import Enum

class ReportFormat(Enum):
    """Available file formats."""
    JSON = "json"
    HTML = "html"
    MARKDOWN = "md"
