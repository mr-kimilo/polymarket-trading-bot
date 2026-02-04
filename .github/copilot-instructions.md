# Copilot instructions

## Language Policy

All instructions and prompts in this repository must be written in English. This applies to:

- All rule and instruction files in `.github/instructions/`
- All prompt files in `.github/prompts/`
- All documentation and code comments intended for contributors

## Development code generation

When working with Python code, follow these instructions very carefully.

It is **EXTREMELY important that you follow the instructions in the rule files very carefully.**

### Workflow implementation

**IMPORTANT:** Always follow these steps when implementing new features:

1. Consult any relevant instructions files listed below and start by listing which rule files have been used to guide the implementation (e.g. `Instructions used: [clean-architecture.instructions.md, domain-driven-design.instructions.md]`).

2. Follow TDD when it is possible. Always start new changes by writing new test cases (or changing existing tests).
   Remember to consult [Unit and Integration Tests](./instructions/unit-and-integration-tests.instructions.md) for details on how to write tests with pytest.

3. Always run `pytest` or `python -m pytest` to verify that all tests pass before committing your changes.
   Don't ask to run the tests, just do it. If you are not sure how to run the tests, ask for help.
   You can also use `pytest-watch` to run the tests automatically when you change the code.

4. Fix any linting errors (with ruff, black, mypy, etc.) and type checking warnings before going to the next step.

5. Ensure code coverage is maintained or improved. Use `pytest --cov` to check coverage.

When you see paths like `/[project]/features/[feature]/` in rules, replace [project] with the name of the project you are working on (e.g. `ordering`), and `[feature]` with the name of the feature you are working on (e.g. `verify_or_add_payment`).

## Python-specific guidelines

- Use type hints for all function signatures and class attributes
- Follow PEP 8 style guide (enforced by black and ruff)
- Use dataclasses or Pydantic models for data structures
- Prefer composition over inheritance
- Use context managers for resource management
- Follow the Zen of Python principles
