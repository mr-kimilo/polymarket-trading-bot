---
mode: "agent"
description: "Create a comprehensive README.md file for Python projects"
---

## Role

You're a senior expert Python software engineer with extensive experience in open source projects. You always make sure the README files you write are appealing, informative, and easy to read.

## Task

1. Take a deep breath, and review the entire project and workspace, then create a comprehensive and well-structured README.md file for the Python project.
2. Include the following sections where appropriate:
   - **Project Title** with a brief tagline
   - **Features** - Key capabilities and highlights
   - **Installation** - Step-by-step setup instructions including virtual environment
   - **Usage** - Clear examples with code snippets
   - **Configuration** - Environment variables or configuration files
   - **Development** - How to set up development environment
   - **Testing** - How to run tests with pytest
   - **API Documentation** - If applicable (FastAPI, Flask, etc.)
   - **Contributing** - Reference to CONTRIBUTING.md if it exists
   - **License** - Reference to LICENSE file if it exists
3. Use GFM (GitHub Flavored Markdown) for formatting, and GitHub admonition syntax where appropriate.
4. Do not overuse emojis, and keep the readme concise and to the point.
5. Do not include sections like "LICENSE", "CONTRIBUTING", "CHANGELOG" with full content. There are dedicated files for those sections.
6. If you find a logo or icon for the project, use it in the readme's header.
7. For Python projects, include:
   - Python version requirements (e.g., "Python 3.11+")
   - Virtual environment setup instructions
   - Dependencies installation with pip or poetry
   - Pre-commit hooks setup if applicable
   - Type checking and linting commands

## Example Structure

```markdown
# Project Name

> Brief, compelling description of what this project does

## Features

- ✨ Feature 1
- 🚀 Feature 2
- 🔒 Feature 3

## Requirements

- Python 3.11+
- pip or poetry

## Installation

### Using pip

\`\`\`bash

# Create virtual environment

python -m venv .venv
source .venv/bin/activate # On Windows: .venv\\Scripts\\activate

# Install dependencies

pip install -r requirements.txt
\`\`\`

### Using poetry

\`\`\`bash
poetry install
poetry shell
\`\`\`

## Usage

\`\`\`python
from your_package import YourClass

# Example usage

instance = YourClass()
result = instance.do_something()
\`\`\`

## Configuration

Configure the application using environment variables:

\`\`\`bash
export API_KEY=your_api_key
export DATABASE_URL=postgresql://user:pass@localhost/db
\`\`\`

Or create a `.env` file:

\`\`\`env
API_KEY=your_api_key
DATABASE_URL=postgresql://user:pass@localhost/db
\`\`\`

## Development

### Setup

\`\`\`bash

# Install development dependencies

pip install -r requirements-dev.txt

# Install pre-commit hooks

pre-commit install
\`\`\`

### Running Tests

\`\`\`bash

# Run all tests

pytest

# Run with coverage

pytest --cov=src --cov-report=html

# Run specific test file

pytest tests/test_module.py
\`\`\`

### Code Quality

\`\`\`bash

# Format code

black .

# Lint

ruff check .

# Type checking

mypy src/
\`\`\`

## API Documentation

If this is a web API (FastAPI, Flask):

\`\`\`bash

# Run the server

uvicorn main:app --reload

# Access API docs

open http://localhost:8000/docs
\`\`\`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute.

## License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.
\`\`\`

## Guidelines

- Be concise but comprehensive
- Include actual code examples from the project
- Provide clear installation steps for both pip and poetry if applicable
- Show how to run tests and checks
- Use admonitions for important notes or warnings
- Keep the tone professional but friendly
- Ensure all code blocks have proper syntax highlighting
```
