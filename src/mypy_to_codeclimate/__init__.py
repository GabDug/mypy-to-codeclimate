from __future__ import annotations

import argparse
import json
import re
import sys
from enum import Enum
from hashlib import md5
from pathlib import Path
from typing import Any, Callable, NoReturn

from typing_extensions import Literal, NotRequired, TypedDict

from mypy_to_codeclimate._version import __version__

MYPY_OUTPUT_PATTERN = r"^(?P<file>[^\n]+?):(?P<line>\d+):?((?P<column>\d+):)? (?P<error_level>\w+):\s*(?P<message>.+?)(?:\s+\[(?P<rule>[a-z\-]*)\])?$"

MYPY_OUTPUT_REGEX: re.Pattern[str] = re.compile(MYPY_OUTPUT_PATTERN, re.MULTILINE)
MYPY_FAIL_REGEX: re.Pattern[str] = re.compile(
    r"Found \d+ errors? in \d+ files? \(checked \d+ source files?\)", re.MULTILINE
)


class _CodeQualitySeverity(str, Enum):
    blocker = "blocker"
    critical = "critical"
    major = "major"
    minor = "minor"
    info = "info"
    unknown = "unknown"


class _CodeQualityCategories(str, Enum):
    bug_risk = "Bug Risk"
    compatibility = "Compatibility"
    complexity = "Complexity"
    duplication = "Duplication"
    performance = "Performance"
    security = "Security"
    style = "Style"
    clarity = "Clarity"


class _CodeQualityLine(TypedDict):
    begin: int
    end: NotRequired[int]


class _CodeQualityLocation(TypedDict):
    path: str
    lines: _CodeQualityLine
    positions: NotRequired[dict[str, dict[str, int]]]


class _CodeQualityIssue(TypedDict):
    type: str
    check_name: str
    description: str
    fingerprint: str
    categories: list[str]
    severity: _CodeQualitySeverity
    location: _CodeQualityLocation
    content: NotRequired[dict[Literal["body"], str]]
    remediation_points: NotRequired[int]


class MypyExitCode(Enum):
    SUCCESS = 0
    ERROR = 1
    FATAL = 2


def main() -> NoReturn:
    parser = _get_parser()
    args = _parse_args(parser)

    try:
        exit_code = _load_convert_and_save(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        exit_code = MypyExitCode.FATAL

    sys.exit(exit_code.value)


def _get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert mypy output to codeclimate json format")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    parser.add_argument(
        "input",
        metavar="INPUT",
        type=_get_input,
        nargs="?",
        default="-",
        help='Input file or "-" for stdin. Defaults to "-".',
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT",
        type=_get_output,
        nargs="?",
        default="./codeclimate-output.json",
        help='Output file or "-" for stdout. Defaults to "./codeclimate-output.json"',
    )
    # parser.add_argument('--print-input', dest='print_input', action='store_const', help='Print the input to stdout')

    return parser


def _parse_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    return parser.parse_args()


def convert_mypy_output_to_code_climate(
    mypy_output: str,
) -> tuple[list[_CodeQualityIssue], MypyExitCode]:
    """Converts mypy text output to codeclimate JSON format.

    Args:
        mypy_output (str): mypy text output

    Returns:
        tuple[list[CodeQualityIssue], bool]: list of issues in codeclimate format, and whether there was an error
    """
    split_issues_on_newline = mypy_output.split("\n")

    issues: list[_CodeQualityIssue] = []
    exit_code = MypyExitCode.FATAL

    # All except lasts lines (summary + empty line)
    for issue in split_issues_on_newline:
        codeclimate_json = parse_issue_line(issue)
        if isinstance(codeclimate_json, MypyExitCode):
            exit_code = codeclimate_json
        elif codeclimate_json is not None:
            issues.append(codeclimate_json)
    return issues, exit_code


def parse_issue_line(issue: str) -> _CodeQualityIssue | MypyExitCode | None:
    """Parse a single line of mypy output

    Args:
        issue (str): line of mypy output

    Returns:
        CodeQualityIssue | MypyExitCode | None: CodeQualityIssue if valid issue, MypyExitCode if found a finish message, None otherwise
    """
    if issue.startswith(("Found 0 errors", "Success: no issues found in")):
        return MypyExitCode.SUCCESS
    if MYPY_FAIL_REGEX.match(issue):
        return MypyExitCode.ERROR

    match = MYPY_OUTPUT_REGEX.match(issue)
    if match is None:
        return None

    parsed_issue = _extract_issue_from_match(match)

    return _fingerprint_issue(parsed_issue)


def _load_convert_and_save(mypy_output: str, codeclimate_output_writer: Callable[[str], Any]) -> MypyExitCode:
    issues, exit_code = convert_mypy_output_to_code_climate(mypy_output)
    codeclimate_output_writer(json.dumps(issues))
    return exit_code


def _extract_issue_from_match(match: re.Match[str]) -> _CodeQualityIssue:
    line_number = int(match.group("line") or 1)
    file_name: str = match.group("file")
    issue_description: str = match.group("message")
    error_level: str = match.group("error_level")
    severity: _CodeQualitySeverity = _CodeQualitySeverity.info if error_level == "note" else _CodeQualitySeverity.major
    rule: str = match.group("rule")

    codeclimate_json: _CodeQualityIssue = {
        "type": "issue",
        "check_name": f"mypy/{rule}",
        "description": issue_description,
        "categories": [_CodeQualityCategories.bug_risk],
        "location": {"path": file_name, "lines": {"begin": line_number}},
        "severity": severity,
        "fingerprint": "",
    }

    return codeclimate_json


def _fingerprint_issue(issue: _CodeQualityIssue) -> _CodeQualityIssue:
    """Fingerprint an issue"""
    issue["fingerprint"] = ""
    issue["fingerprint"] = str(md5(str(issue).encode()).hexdigest())  # nosec: B324 # noqa: S324
    return issue


def _get_input(path_str: str | Path) -> str:
    """Get the input from the path or stdin"""
    if path_str == "-":
        if sys.stdin.isatty():
            err_msg = "stdin is not a tty: pipe a mypy output or specify an input file path"
            raise argparse.ArgumentTypeError(err_msg)
        return sys.stdin.read()
    path = Path(path_str)
    try:
        return path.read_text()
    except FileNotFoundError as e:
        err_msg = f"File not found: {path.absolute()}"
        raise argparse.ArgumentTypeError(err_msg) from e


def _get_output(path: str | Path = "./codeclimate-output.json") -> Callable[[str], Any]:
    """Return a function to write the output to the path or stdout"""
    if path == "-":
        return sys.stdout.write

    path_file = Path(path)
    path_file.parent.mkdir(parents=True, exist_ok=True)
    return path_file.write_text


if __name__ == "__main__":
    main()
