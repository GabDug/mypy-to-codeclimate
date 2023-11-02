from __future__ import annotations

import json
import os
import re
import sys
from enum import Enum
from hashlib import md5
from pathlib import Path
from typing import Any, Callable, Final, NoReturn

from typing_extensions import Literal, NotRequired, TypedDict

MYPY_OUTPUT_PATTERN = r"^(?P<file>[^\n]+?):(?P<line>\d+):?((?P<column>\d+):)? (?P<error_level>\w+):\s*(?P<message>.+?)(?:\s+\[(?P<rule>[a-z\-]*)\])?$"

MYPY_OUTPUT_REGEX: Final[re.Pattern[str]] = re.compile(
    MYPY_OUTPUT_PATTERN,
    re.MULTILINE,
)


class _CodeQualitySeverity(str, Enum):
    blocker = "blocker"
    critical = "critical"
    major = "major"
    minor = "minor"
    info = "info"
    unknown = "unknown"


class CodeQualityCategories(str, Enum):
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


def _load_convert_and_save(
    mypy_output: str, codeclimate_output: Callable[[str], Any]
) -> bool:
    issues, has_error = convert_mypy_output_to_code_climate(mypy_output)
    codeclimate_output(json.dumps(issues))
    return has_error


def convert_mypy_output_to_code_climate(
    mypy_output: str,
) -> tuple[list[_CodeQualityIssue], bool]:
    """Converts mypy text output to codeclimate JSON format.

    Args:
        mypy_output (str): mypy text output

    Returns:
        tuple[list[CodeQualityIssue], bool]: list of issues in codeclimate format, and whether there was an error
    """
    split_issues_on_newline = mypy_output.split("\n")

    issues: list[_CodeQualityIssue] = []
    has_error = True

    # All except lasts lines (summary + empty line)
    for issue in split_issues_on_newline:
        if issue.startswith(("Found 0 errors", "Success: no issues found in")):
            has_error = False

        codeclimate_json = parse_issue_line(issue)
        if codeclimate_json is not None:
            issues.append(codeclimate_json)
    return issues, has_error


def parse_issue_line(issue: str) -> _CodeQualityIssue | None:
    match = MYPY_OUTPUT_REGEX.match(issue)
    if match is None:
        return None

    line_number = int(match.group("line") or 1)
    file_name = match.group("file")
    issue_description = match.group("message")
    error_level = match.group("error_level")
    severity: _CodeQualitySeverity = (
        _CodeQualitySeverity.info
        if error_level == "note"
        else _CodeQualitySeverity.major
    )
    rule = match.group("rule")

    codeclimate_json: _CodeQualityIssue = {
        "type": "issue",
        "check_name": f"mypy/{rule}",
        "description": issue_description,
        "categories": ["Bug Risk"],
        "location": {"path": file_name, "lines": {"begin": line_number}},
        "severity": severity,
        "fingerprint": "",
    }

    codeclimate_json["fingerprint"] = str(
        md5(str(codeclimate_json).encode()).hexdigest()  # nosec: B324 # noqa: S324
    )

    return codeclimate_json


def main() -> NoReturn:
    input_data = _get_input(next(iter(sys.argv[1:]), ""))
    out_writable = _get_output(next(iter(sys.argv[2:]), ""))

    errored = _load_convert_and_save(input_data, out_writable)

    if errored:
        sys.exit(1)
    sys.exit(0)


def _get_input(path: str | Path) -> str:
    if path == "-":
        if os.isatty(sys.stdin.fileno()):
            raise RuntimeError(
                "stdin is not a tty - pipe a mypy output or specify a file"
            )
        return sys.stdin.read()
    return Path(path).read_text()


def _get_output(path: str | Path = "./codeclimate-output.json") -> Callable[[str], Any]:
    if path == "-":
        return sys.stdout.write

    path_file = Path(path)
    path_file.parent.mkdir(parents=True, exist_ok=True)
    return path_file.write_text


if __name__ == "__main__":
    main()
