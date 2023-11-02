import argparse
import os
import sys
import tempfile
from unittest import mock

import pytest
from mypy_to_codeclimate import (
    MypyExitCode,
    _get_input,
    _get_output,
    _load_convert_and_save,
    convert_mypy_output_to_code_climate,
    main,
    parse_issue_line,
)
from mypy_to_codeclimate._version import __version__
from pytest_mock import MockerFixture

# Valid issues to be parsed
valid_issues = [
    "pkg/module.py:4: error: Description",
    "module.py:4: error: Description",
    "module.py:4: note: Description",
    "module.py:4: unknown: Description",
    "module.py:4: error: Description",
    'module.py:4: error: Description "test" [123] (abc)',
    "module.py:4: error: Description  [error-code]",
    "module.py:4:5: error: Description",
    """long/path.py:513: error: Return type "Test" of "toto" incompatible with return type "None" in supertype "TotoTest"  [override]""",
]


@pytest.mark.parametrize("issue", valid_issues)
def test_valid_issues(issue: str) -> None:
    result = parse_issue_line(issue)
    assert result is not None


# Complete with no errors
@pytest.mark.parametrize(
    "issue", ["Success: no issues found in 1 source file", "Success: no issues found in 360 source files"]
)
def test_no_errors(issue: str) -> None:
    result = parse_issue_line(issue)
    assert result == MypyExitCode.SUCCESS


# Complete with errors
@pytest.mark.parametrize(
    "issue",
    ["Found 5 errors in 1 file (checked 1 source file)", "Found 5 errors in 3 files (checked 360 source files)"],
)
def test_errors(issue: str) -> None:
    result = parse_issue_line(issue)
    assert result == MypyExitCode.ERROR


@pytest.mark.parametrize(
    "issue",
    [
        "mypy: can't read file 'doesnotexist.py': No such file or directory",
        "fatal error because mypy is a teapot",
        " " * 4,
        "",
    ],
)
def test_parse_none_line(issue: str) -> None:
    result = parse_issue_line(issue)
    assert result is None


def test_main_success() -> None:
    with mock.patch.object(
        argparse.ArgumentParser,
        "parse_args",
        return_value=argparse.Namespace(input="-", output="./codeclimate-output.json"),
    ):
        with mock.patch("mypy_to_codeclimate._load_convert_and_save", return_value=MypyExitCode.SUCCESS):
            with mock.patch("sys.exit") as mock_exit:
                main()
                mock_exit.assert_called_once_with(MypyExitCode.SUCCESS.value)


def test_main_error() -> None:
    with mock.patch.object(
        argparse.ArgumentParser,
        "parse_args",
        return_value=argparse.Namespace(input="-", output="./codeclimate-output.json"),
    ):
        with mock.patch("mypy_to_codeclimate._load_convert_and_save", side_effect=Exception("Test Exception")):
            with mock.patch("sys.exit") as mock_exit:
                with mock.patch("builtins.print") as mock_print:
                    main()
                    mock_print.assert_called_once_with("Error: Test Exception", file=sys.stderr)
                    mock_exit.assert_called_once_with(MypyExitCode.FATAL.value)


def test_get_input_from_file() -> None:
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"test input")
        tf.close()
        assert _get_input(tf.name) == "test input"
        os.unlink(tf.name)


def test_get_input_from_stdin(mocker: MockerFixture) -> None:
    mocker.patch("sys.stdin.read", return_value="test input")
    mocker.patch("os.isatty", return_value=False)
    assert _get_input("-") == "test input"


def test_get_output_to_file() -> None:
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.close()
        output_func = _get_output(tf.name)
        output_func("test output")
        with open(tf.name, "r") as f:
            assert f.read() == "test output"
        os.unlink(tf.name)


def test_get_output_to_stdout(mocker: MockerFixture) -> None:
    mocker.patch("sys.stdout.write")
    output_func = _get_output("-")
    output_func("test output")
    sys.stdout.write.assert_called_once_with("test output")


def test_get_input_from_stdin_isatty(mocker):
    mocker.patch("sys.stdin.isatty", return_value=True)
    with pytest.raises(argparse.ArgumentTypeError, match="specify an input file"):
        _get_input("-")


def test_get_input_from_nonexistent_file():
    with pytest.raises(argparse.ArgumentTypeError, match="File not found"):
        _get_input("/path/to/nonexistent/file")


def test_convert_mypy_output_to_code_climate_no_input():
    mypy_output = ""

    issues, exit_code = convert_mypy_output_to_code_climate(mypy_output)

    assert issues == []
    assert exit_code == MypyExitCode.FATAL


def test_convert_mypy_output_to_code_climate_with_issues():
    mypy_output = """main.py:5: error: Incompatible return value type (got "int", expected "str")
Found 1 error in 1 file (checked 1 source file)"""

    issues, exit_code = convert_mypy_output_to_code_climate(mypy_output)

    assert len(issues) == 1
    assert issues[0]["description"] == 'Incompatible return value type (got "int", expected "str")'
    assert issues[0]["location"]["path"] == "main.py"
    assert issues[0]["location"]["lines"]["begin"] == 5
    assert exit_code == MypyExitCode.ERROR


def test_convert_mypy_output_to_code_climate_no_issues():
    mypy_output = "Success: no issues found in 1 source file"

    issues, exit_code = convert_mypy_output_to_code_climate(mypy_output)

    assert issues == []
    assert exit_code == MypyExitCode.SUCCESS


def test_load_convert_and_save_no_issues():
    mypy_output = "Success: no issues found in 1 source file"

    exit_code = _load_convert_and_save(mypy_output, lambda x: None)

    assert exit_code == MypyExitCode.SUCCESS


def test_load_convert_and_save_with_issues() -> None:
    mypy_output = """main.py:5: error: Incompatible return value type (got "int", expected "str")
Found 1 error in 1 file (checked 1 source file)"""

    exit_code = _load_convert_and_save(mypy_output, lambda x: None)

    assert exit_code == MypyExitCode.ERROR


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    test_args = [
        "mypy-to-codeclimate",
        "--version",
    ]

    with mock.patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit):
            main()

    captured = capsys.readouterr()
    assert "mypy-to-codeclimate" in captured.out
    assert __version__ in captured.out


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    test_args = [
        "mypy-to-codeclimate",
        "--help",
    ]

    with mock.patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit):
            main()

    captured = capsys.readouterr()
    assert "usage" in captured.out
    assert "mypy-to-codeclimate" in captured.out
