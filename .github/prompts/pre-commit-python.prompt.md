---
description: "Setup pre-commit hooks for Python projects"
---

# Pre-commit Hooks Setup for Python

## Overview

This prompt helps you set up pre-commit hooks for Python projects with black, ruff, mypy, and pytest.

## Steps

### 1. Install pre-commit

```bash
pip install pre-commit
```

### 2. Create .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: [--ignore-missing-imports]

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
        args: ["-v", "--tb=short"]
```

### 3. Install hooks

```bash
pre-commit install
```

### 4. Run manually (optional)

```bash
# Run on all files
pre-commit run --all-files

# Run on staged files
pre-commit run
```

## Configuration Files

### pyproject.toml

```toml
[tool.black]
line-length = 100
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''

[tool.ruff]
line-length = 100
target-version = "py311"
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "N",  # pep8-naming
    "UP", # pyupgrade
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
]
ignore = []
fixable = ["ALL"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow tests",
]
```

## Usage

After setup, hooks will run automatically on `git commit`:

```bash
git add .
git commit -m "feat: add order processing"
# Hooks run automatically:
# - Format with black
# - Lint with ruff
# - Type check with mypy
# - Run pytest
```

## Skip Hooks (Emergency Only)

```bash
git commit --no-verify -m "emergency fix"
```

## Benefits

- ✅ Consistent code formatting
- ✅ Catch errors before commit
- ✅ Ensure tests pass
- ✅ Automatic import sorting
- ✅ Type checking enforcement
- ✅ Team consistency
