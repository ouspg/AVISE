"""
AVISE Command Line Interface.

Usage:
    Basic:
    python -m avise --SET <SET_name> --connectorconf </path/to/connectorconfig/> --SETconf </path/to/setconfig/>

    Adding report format (default is json):

    python -m avise --SET <SET_name> --connectorconf </path/to/connectorconfig/> --SETconf </path/to/setconfig/> --format json/html/md

    Add custom output directory (optional):
    
    python -m avise --SET <SET_name> --connectorconf </path/to/connectorconfig/> --SETconf </path/to/setconfig/> --format json/html/md --output <path/to/outputdir>

    Example:
    python -m avise --SET prompt_injection --connectorconf avise/configs/connector//ollama.json --SETconf avise/configs/SET/prompt_injection_mini.json

"""
import sys
import argparse
import logging

from avise import __version__

# Import to register different plugins and SETs
from . import evaluators
from . import connectors
from . import sets

from .utils import ReportFormat
from .engine import ExecutionEngine


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_REPORTS_DIR = "reports"

def main(arguments=[]) -> None:
    if not isinstance(arguments, list):
        raise TypeError("CLI parser expects a list of strings as arguments.")
    if len(arguments) > 200:
        raise ValueError("CLI parser received too many arguments.")
    for arg in arguments:
        if not isinstance(arg, str):
            raise TypeError("CLI parser expects a list of strings a arguments.")
    parser = argparse.ArgumentParser(
        description="AVISE - AI Vulnerability Identification & Security Evaluation"
    )
    parser.add_argument(
        "--SET_list",
        action="store_true",
        help="List available Security Evaluation Tests and formats"
    )
    parser.add_argument(
        "--connector_list",
        action="store_true",
        help="List available connectors"
    )

    parser.add_argument(
        "--SET",
        help="Security Evaluation Test to run (e.g., prompt_injection)"
    )

    parser.add_argument(
        "--connectorconf",
        help="Path to connector configuration JSON"
    )

    parser.add_argument(
        "--SETconf",
        help="Path to Security Evaluation Test configuration JSON"
    )
    

    parser.add_argument(
        "--format", "-f",
        choices=["json", "html", "md"],
        default="json",
        help="Report format: json (default), html, or md (markdown)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Custom output path (Overrider default date based naming)"
    )
    parser.add_argument(
        "--reports_dir", "-d",
        default=DEFAULT_REPORTS_DIR,
        help=f"Base directory for reports (default: {DEFAULT_REPORTS_DIR})"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=__version__
    )
    args = parser.parse_args(arguments)
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    engine = ExecutionEngine()

    if args.SET_list:
        engine.list_available()
        return
    
    if args.connector_list:
        engine.list_available(sets=False, reportformats=False)
        return

    if not args.SET:
        parser.print_help()
        print("\nError: --SET is required")
        return

    if not args.connectorconf:
        parser.print_help()
        print("\nError: --connectorconf is required")
        return

    if not args.SETconf:
        parser.print_help()
        print("\nError: --SETconf is required")
        return

    format_map = {
        "json": ReportFormat.JSON,
        "html": ReportFormat.HTML,
        "md": ReportFormat.MARKDOWN
    }
    report_format = format_map[args.format]

    # Run the SET by calling run_test function. The selected SET's run() function is called.
    try:
        report = engine.run_test(
            set_name=args.SET,
            set_config_path=args.SETconf,
            connector_config_path=args.connectorconf,
            output_path=args.output,
            report_format=report_format,
            reports_dir=args.reports_dir,
        )

        #Print a small summary to the console
        print(f"\nSecurity Evaluation Test completed!")
        print(f"  Format: {report_format.value.upper()}")
        print(f"  Total: {report.summary['total_sets']}")
        print(f"  Passed: {report.summary['passed']} ({report.summary['pass_rate']}%)")
        print(f"  Failed: {report.summary['failed']} ({report.summary['fail_rate']}%)")
        print(f"  Errors: {report.summary['error']}")

    except Exception as e:
        logger.error(f"Security Evaluation Test run failed: {e}", exc_info=True)
        raise




if __name__ == "__main__":
    main(sys.argv[1:])
