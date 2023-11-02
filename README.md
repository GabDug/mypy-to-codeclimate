
# mypy-code-climate

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/mypy-to-codeclimate)
[![PyPI](https://img.shields.io/pypi/v/mypy-to-codeclimate)](https://pypi.org/project/mypy-to-codeclimate/)
[![Downloads](https://static.pepy.tech/badge/mypy-to-codeclimate/month)](https://pepy.tech/project/mypy-to-codeclimate)
![PyPI - License](https://img.shields.io/pypi/l/mypy-to-codeclimate)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Standalone tool to convert Mypy output to Code Climate format. It does not require the Code Climate CLI and is dependency-free: great for CI/CD.

## Why Code Climate

The Code Climate format is supported by Gitlab CI, so you can generate a Code Quality report from mypy output, and have it tracked and displayed in your Gitlab UI.

## Usage

```bash
mypy-to-codeclimate <mypy_output_file> <code_climate_output_file>
```

Example:

```bash
mypy-to-codeclimate mypy-output.txt mypy-codequality.json
```

You can replace the filename by `-` to read from stdin, write to stdout, or both.

```bash
mypy <command_args> | mypy-to-codeclimate - mypy-codequality.json
```

Program will exit with code 1 if there are errors in the mypy output, and 0 otherwise.

## Installation

```bash
pip install mypy-to-codeclimate
```

> The package is distributed on Pypi, so you can install it with pipx, PDM, Poetry or any other Python package manager.

## Supported versions

### Mypy versions

Tested against Mypy 1.6.1. It should work with any version of mypy that outputs the same format.

Please open an issue if you find a version of mypy that is not supported.

### Python versions

Tested against Python 3.11. It should work with any actively supported version of Python.

Please open an issue if you have any problem with a specific version of Python.

## Example usage in Gitlab CI

Example of a job that runs mypy and generates a codeclimate report, on a Linux runner.

Dependency management is left as an exercise for the reader.

See [Gitlab CI code-quality artifacts reference](https://docs.gitlab.com/ee/ci/yaml/artifacts_reports.html#artifactsreportscodequality)

```yaml
lint_python_mypy:
  script:
    - mypy --version
    # Disable exit on error and pipefail:
    # mypy-code-climate will return a non-zero exit code if there are errors but we want to continue the job to generate the report
    - set +eo pipefail
    - mypy <command_args> | tee mypy-output.txt"
    # Enable exit on error again
    - set -xeo
    - mypy-to-codeclimate mypy-output.txt mypy-codequality.json
  artifacts:
    when: always
    paths:
      - mypy-codequality.json
    reports:
      codequality: mypy-codequality.json
```

## License

MIT, see [LICENSE](LICENSE) file.

## Acknowledgements

Inspired by [codeclimate-mypy](https://github.com/larkinscott/codeclimate-mypy) by Scott Larkin (@larkinscott).
