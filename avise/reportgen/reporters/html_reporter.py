"""
HTML report writer.
"""
from pathlib import Path
from typing import Dict, Any

from .base import BaseReporter
from ...pipelines.languagemodel import ReportData, EvaluationResult


class HTMLReporter(BaseReporter):
    """
    Writes reports in styled HTML format.
    
    """

    format_name = "html"
    file_extension = ".html"

    # Status colors for styling
    STATUS_COLORS = {
        "passed": "#28a745",
        "failed": "#dc3545",
        "error": "#ffc107"
    }

    def write(self, report_data: ReportData, output_path: Path) -> None:
        """
        Write report data as styled HTML file.

        Args:
            report_data: The report data to write
            output_path: Path to the output file / directory
        """
        html = self._generate_html(report_data)
        with open(output_path, 'w') as f:
            f.write(html)

    def _generate_html(self, report_data: ReportData) -> str:
        """Generate complete HTML report."""
        html = self._get_html_header(report_data)
        html += self._get_summary_section(report_data)
        html += self._get_results(report_data.results)
        html += "</body>\n</html>"
        return html

    def _get_html_header(self, report_data: ReportData) -> str:
        """Generate HTML head and opening body."""
        config = report_data.configuration

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AVISE Report - {report_data.set_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: #1a1a2e;
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .header .meta {{ opacity: 0.8; font-size: 14px; }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .card .number {{ font-size: 36px; font-weight: bold; }}
        .card .label {{ color: #666; font-size: 14px; }}
        .card.passed .number {{ color: {self.STATUS_COLORS['passed']}; }}
        .card.failed .number {{ color: {self.STATUS_COLORS['failed']}; }}
        .card.error .number {{ color: {self.STATUS_COLORS['error']}; }}
        .category {{
            background: white;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .category-header {{
            background: #2d3436;
            color: white;
            padding: 15px 20px;
            border-radius: 10px 10px 0 0;
        }}
        .category-header h2 {{ margin: 0; font-size: 18px; }}
        .set-item {{
            border-bottom: 1px solid #eee;
            padding: 15px 20px;
        }}
        .set-item:last-child {{ border-bottom: none; }}
        .set-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .set-id {{ font-weight: bold; color: #2d3436; }}
        .status {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .status.passed {{ background: #d4edda; color: #155724; }}
        .status.failed {{ background: #f8d7da; color: #721c24; }}
        .status.error {{ background: #fff3cd; color: #856404; }}
        .prompt, .response {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            font-family: monospace;
            font-size: 13px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .label-sm {{ font-size: 12px; color: #666; margin-bottom: 5px; }}
        .reason {{ color: #666; font-style: italic; margin-top: 10px; }}
        .elm-eval {{
            background: #e7f3ff;
            border-left: 4px solid #0066cc;
            padding: 10px;
            margin-top: 10px;
        }}
        .conversation {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .conversation .message {{
            margin: 5px 0;
            padding: 5px 10px;
            border-radius: 5px;
        }}
        .conversation .user {{ background: #e3f2fd; }}
        .conversation .assistant {{ background: #e8f5e9; }}
        .conversation .system {{ background: #fff3e0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AVISE Security Report</h1>
        <div class="meta">
            Security Evaluation Test: {report_data.set_name} |
            Generated: {report_data.timestamp} |
            Duration: {report_data.execution_time_seconds}s
            {' | ELM Evaluation: Yes' if config.get('elm_evaluation_used') else ''}
        </div>
    </div>
"""

    def _get_summary_section(self, report_data: ReportData) -> str:
        """Generate summary cards section."""
        summary = report_data.summary
        return f"""
    <div class="summary-cards">
        <div class="card">
            <div class="number">{summary['total_sets']}</div>
            <div class="label">Total Security Evaluation Tests</div>
        </div>
        <div class="card passed">
            <div class="number">{summary['passed']}</div>
            <div class="label">Passed ({summary['pass_rate']}%)</div>
        </div>
        <div class="card failed">
            <div class="number">{summary['failed']}</div>
            <div class="label">Failed ({summary['fail_rate']}%)</div>
        </div>
        <div class="card error">
            <div class="number">{summary['error']}</div>
            <div class="label">Inconclusive</div>
        </div>
    </div>
"""

    def _get_results(self, results: list) -> str:
        """Generate list of results."""
        html = """
    <div class="category">
        <div class="category-header">
            <h2>Security Evaluation Test Results</h2>
        </div>
"""
        for result in results:
            if isinstance(result, EvaluationResult):
                set_ = {
                    "set_id": result.set_id,
                    "prompt": result.prompt,
                    "response": result.response,
                    "status": result.status,
                    "reason": result.reason,
                    "attack_type": result.metadata.get("attack_type", ""),
                    "detections": result.detections,
                    "full_conversation": result.metadata.get("full_conversation", []),
                    "description": result.metadata.get("description", "")
                }
                if result.elm_evaluation:
                    set_["elm_evaluation"] = result.elm_evaluation
            else:
                set_ = result
            html += self._get_set_item(set_)
        html += "    </div>\n"
        return html

    def _get_set_item(self, set_: Dict[str, Any]) -> str:
        """Generate HTML for a single SET item."""
        set_label = set_.get("attack_type") or set_.get("description") or ""
        if set_label:
            set_label = f" - {set_label}"

        elm_html = ""
        if "elm_evaluation" in set_:
            elm_html = f"""
                <div class="elm-eval">
                    <div class="label-sm">ELM Evaluation</div>
                    {self.escape_html(set_['elm_evaluation'])}
                </div>"""

        # Check for conversation format (memory test)
        conversation_html = ""
        if set_.get("full_conversation"):
            conversation_html = """
                <div class="label-sm">Conversation</div>
                <div class="conversation">"""
            for msg in set_["full_conversation"]:
                role = msg.get("role", "user")
                content = self.escape_html(msg.get("content", ""))
                conversation_html += f"""
                    <div class="message {role}"><strong>{role}:</strong> {content}</div>"""
            conversation_html += """
                </div>"""

        # Use prompt/response for non-conversation SETs
        prompt_response_html = ""
        if not conversation_html:
            prompt_response_html = f"""
            <div class="label-sm">Prompt</div>
            <div class="prompt">{self.escape_html(set_.get('prompt', ''))}</div>
            <div class="label-sm">Response</div>
            <div class="response">{self.escape_html(set_.get('response', ''))}</div>"""

        return f"""
        <div class="set-item">
            <div class="set-header">
                <span class="set-id">{set_['set_id']}{set_label}</span>
                <span class="status {set_['status']}">{set_['status']}</span>
            </div>
            {prompt_response_html}
            {conversation_html}
            <div class="reason">{self.escape_html(set_.get('reason', ''))}</div>
            {elm_html}
        </div>
"""
