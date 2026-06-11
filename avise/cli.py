"""AVISE Command Line Interface.

Usage:
    Basic:
    python -m avise --SET <SET_name> --connectorconf </path/to/connectorconfig/> --SETconf </path/to/setconfig/>

    Adding report format (default is json):

    python -m avise --SET <SET_name> --connectorconf </path/to/connectorconfig/> --SETconf </path/to/setconfig/> --format json/html/md

    Add custom output directory (optional):

    python -m avise --SET <SET_name> --connectorconf </path/to/connectorconfig/> --SETconf </path/to/setconfig/> --format json/html/md --output <path/to/outputdir>

Example:
    python -m avise --SET prompt_injection --connectorconf configs/connector/languagemodel/ollama.json --SETconf configs/SET/prompt_injection_mini.json

"""

import sys
import argparse
import logging

from avise import __version__

# Import to register different plugins and SETs
from . import evaluators
from . import connectors
from . import sets

from .utils import ReportFormat, ansi_colors
from .engine import ExecutionEngine


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_REPORTS_DIR = "avise-reports"

DEFAULT_SET_CONFIGS = {
    "deceptive_delight": "configs/SET/languagemodel/multi_turn/deceptive_delight.json",
    "red_queen": "configs/SET/languagemodel/multi_turn/red_queen.json",
    "prompt_injection": "configs/SET/languagemodel/single_turn/prompt_injection_mini.json",
    "context_test": "configs/SET/languagemodel/multi_turn/context_test.json",
}


def main(arguments=None) -> None:
    """Main function."""
    if arguments is None:
        arguments = []
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
        "--SET-list",
        action="store_true",
        help="List available Security Evaluation Tests",
    )
    parser.add_argument(
        "--connector-list",
        action="store_true",
        help="List available connectors and formats",
    )

    parser.add_argument(
        "--SET",
        "-s",
        nargs="+",
        type=str,
        help="Security Evaluation Test(s) to run (e.g., prompt_injection)",
    )

    parser.add_argument(
        "--connectorconf", "-c", help="Path to connector configuration file"
    )

    parser.add_argument(
        "--SETconf", help="Path to Security Evaluation Test configuration file"
    )

    parser.add_argument(
        "--target", "-t", help="Name of the target model or system to evaluate"
    )

    parser.add_argument(
        "--elm",
        help="Boolean indicator whether to use an Evaluation Language Model to evaluate SET results or not. True or False. Default: True",
    )

    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "html", "md"],
        default="html",
        help="Report format: html (default; generates both, json and html report files), json, or md (markdown)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Custom output path (overrides default date based naming)",
    )
    parser.add_argument(
        "--runs",
        "-r",
        type=int,
        default=1,
        help="How many times each SET is executed (default 1).",
    )
    parser.add_argument(
        "--reports-dir",
        "-d",
        default=DEFAULT_REPORTS_DIR,
        help=f"Base directory for reports (default: {DEFAULT_REPORTS_DIR}).",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--ai-summary",
        type=lambda x: x.lower() == "true",
        default=True,
        help="Enable or disable AI-powered summary (True/False). Default: True",
    )
    parser.add_argument(
        "--api-key",
        "-a",
        help="API Key to use with requests sent to target API (overrides api_key from Connector configuration file).",
    )
    parser.add_argument("--version", "-V", action="version", version=__version__)
    args = parser.parse_args(arguments)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    engine = ExecutionEngine()

    if args.SET_list:
        engine.list_available(reportformats=False, connectors=False)
        return

    if args.connector_list:
        engine.list_available(sets=False)
        return

    if not args.SET:
        parser.print_help()
        print("\nError: --SET is required")
        return

    if not args.connectorconf:
        parser.print_help()
        print("\nError: --connectorconf is required")
        return

    if args.elm:
        if args.elm == "True":
            args.elm = "mistralai/Ministral-3-3B-Instruct-2512"
        elif args.elm == "False":
            args.elm = ""
        else:
            parser.print_help()
            print("\nError: --elm takes only boolean values: True or False")
            return
    else:
        args.elm = "mistralai/Ministral-3-3B-Instruct-2512"

    format_map = {
        "json": ReportFormat.JSON,
        "html": ReportFormat.HTML,
        "md": ReportFormat.MARKDOWN,
    }
    report_format = format_map[args.format]

    # Predefined connector configs
    if args.connectorconf == "ollama_lm":
        args.connectorconf = "configs/connector/languagemodel/ollama.json"
    elif args.connectorconf == "openai_lm":
        args.connectorconf = "configs/connector/languagemodel/openai.json"
    elif args.connectorconf == "genericrest_lm":
        args.connectorconf = "configs/connector/languagemodel/genericrest.json"

    for set_ in args.SET:
        try:
            if len(args.SET) == 1:
                if not args.SETconf:
                    try:
                        set_config_path = DEFAULT_SET_CONFIGS[set_]
                    except KeyError:
                        parser.print_help()
                        print("\nError: --SETconf is required for this SET.")
                        return
                else:
                    set_config_path = args.SETconf
            elif len(args.SET) > 1:
                try:
                    set_config_path = DEFAULT_SET_CONFIGS[set_]
                except KeyError:
                    logger.error(
                        f"{ansi_colors['red']}Could not find default configuration path for {set_} SET. When executing multiple SETs, each needs to have a default configuration path. Add it to DEFAULT_SET_CONFIGS in cli.py.{ansi_colors['reset']}"
                    )
                    continue
            else:
                parser.print_help()
                print("\nError: --SET is required")
                return
            # Run the SET by calling run_test function. The selected SET's run() function is called.
            report = engine.run_test(
                set_name=set_,
                set_config_path=set_config_path,
                connector_config_path=args.connectorconf,
                evaluation_model_name=args.elm,
                report_format=report_format,
                reports_dir=args.reports_dir,
                generate_ai_summary=args.ai_summary,
                runs=args.runs,
                output_path=args.output,
                target=args.target,
                api_key=args.api_key,
            )

            # Print a small summary to the console
            print("\nSecurity Evaluation Test completed!")
            print(f"  Format: {report_format.value.upper()}")
            print(f"  Total: {report.summary['total_set_cases']}")
            print(
                f"  Passed: {report.summary['passed']} ({report.summary['pass_rate']}%)"
            )
            print(
                f"  Failed: {report.summary['failed']} ({report.summary['fail_rate']}%)"
            )
            print(f"  Errors: {report.summary['error']}")

        except Exception as e:
            logger.error(
                f"{ansi_colors['red']}Security Evaluation Test run failed: {e}{ansi_colors['reset']}",
                exc_info=True,
            )
            raise


if __name__ == "__main__":
    main(sys.argv[1:])
