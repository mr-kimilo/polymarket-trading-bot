---
mode: "agent"
description: "Generate a complete MCP server project in Python with tools, resources, and proper configuration"
---

# Generate Python MCP Server

Create a complete Model Context Protocol (MCP) server in Python with the following specifications:

## Requirements

1. **Project Structure**: Create a new Python project with proper structure using uv or standard setup
2. **Dependencies**: Include mcp[cli] package
3. **Transport Type**: Choose between stdio (for local) or streamable-http (for remote)
4. **Tools**: Create at least one useful tool with proper type hints
5. **Error Handling**: Include comprehensive error handling and validation

## Implementation Details

### Project Setup

- Initialize project with proper structure
- Add MCP SDK: `uv add "mcp[cli]"` or `pip install "mcp[cli]"`
- Create main server file (e.g., `server.py`)
- Add `.gitignore` for Python projects
- Configure for direct execution with `if __name__ == "__main__"`
- Add `pyproject.toml` or `setup.py` for packaging

### Server Configuration

- Use `FastMCP` class from `mcp.server.fastmcp`
- Set server name and optional instructions
- Choose transport: stdio (default) or streamable-http
- For HTTP: optionally configure host, port, and stateless mode

### Tool Implementation

- Use `@mcp.tool()` decorator on functions
- **Always include type hints** - they generate schemas automatically
- Write clear docstrings - they become tool descriptions
- Use Pydantic models or TypedDicts for structured outputs
- Support async operations for I/O-bound tasks with `async def`
- Include proper error handling with try/except
- Follow Python best practices (PEP 8, type hints, etc.)

### Resource/Prompt Setup (Optional)

- Add resources with `@mcp.resource()` decorator
- Use URI templates for dynamic resources: `"resource://{param}"`
- Add prompts with `@mcp.prompt()` decorator
- Return strings or Message lists from prompts

### Code Quality

- Use type hints for all function parameters and returns
- Write docstrings for tools, resources, and prompts (Google or NumPy style)
- Follow PEP 8 style guidelines
- Use async/await for asynchronous operations
- Implement context managers for resource cleanup
- Add inline comments for complex logic
- Use Pydantic for input validation

## Example Tool Types to Consider

- Data processing and transformation
- File system operations (read, analyze, search)
- External API integrations
- Database queries (with SQLAlchemy)
- Text analysis or generation (with sampling)
- System information retrieval
- Math or scientific calculations (NumPy, Pandas)

## Configuration Options

- **For stdio Servers**:
  - Simple direct execution
  - Test with `uv run mcp dev server.py`
  - Install to Claude: `uv run mcp install server.py`
- **For HTTP Servers**:
  - Port configuration via environment variables
  - Stateless mode for scalability: `stateless_http=True`
  - JSON response mode: `json_response=True`
  - CORS configuration for browser clients
  - Mounting to existing ASGI servers (Starlette/FastAPI)

## Example Server Structure

```python
#!/usr/bin/env python3
"""
MCP Server Example - [Server Name]
Description of what this server does.
"""

import asyncio
from typing import Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("server-name")

@mcp.tool()
async def example_tool(
    parameter: str,
    optional_param: int = 10
) -> dict[str, Any]:
    """
    Tool description that becomes the schema description.

    Args:
        parameter: Description of parameter
        optional_param: Description of optional parameter

    Returns:
        Dictionary with result data

    Raises:
        ValueError: If parameter is invalid
    """
    if not parameter:
        raise ValueError("Parameter cannot be empty")

    # Implementation here
    result = {
        "status": "success",
        "data": parameter,
        "count": optional_param
    }

    return result

@mcp.resource("data://{resource_id}")
async def get_data(resource_id: str) -> str:
    """
    Provide data resource by ID.

    Args:
        resource_id: The ID of the resource to retrieve

    Returns:
        Resource content as string
    """
    # Fetch and return resource data
    return f"Data for resource {resource_id}"

@mcp.prompt()
async def example_prompt() -> str:
    """Generate an example prompt."""
    return "This is a prompt template that can guide LLM interactions"

if __name__ == "__main__":
    # Run the server
    mcp.run()
```

## Testing Guidance

- Explain how to run the server:
  - stdio: `python server.py` or `uv run server.py`
  - HTTP: `python server.py` then connect to `http://localhost:PORT/mcp`
- Test with MCP Inspector: `uv run mcp dev server.py`
- Install to Claude Desktop: `uv run mcp install server.py`
- Include example tool invocations
- Add troubleshooting tips for common issues

## Additional Features to Consider

- Context usage for logging, progress, and notifications
- LLM sampling for AI-powered tools
- User input elicitation for interactive workflows
- Lifespan management for shared resources (databases, connections)
- Structured output with Pydantic models
- Icons for UI display
- Image handling with Image class
- Completion support for better UX
- Error handling with custom exceptions

## Best Practices

- **Type hints everywhere** - they're not optional for MCP
- Return structured data when possible (dicts, Pydantic models)
- Log to stderr (or use Context logging) to avoid stdout pollution
- Clean up resources properly with context managers
- Validate inputs early with Pydantic
- Provide clear error messages
- Test tools independently before LLM integration
- Use async for I/O operations
- Follow Python security best practices (no eval, pickle, etc.)
- Add docstrings with examples

## Project Structure

```
mcp-server/
├── server.py              # Main MCP server
├── pyproject.toml         # Project configuration
├── README.md              # Documentation
├── requirements.txt       # Dependencies
├── .gitignore            # Git ignore
└── tests/                # Tests
    └── test_server.py
```

## Dependencies to Include

```toml
[project]
name = "mcp-server-example"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=1.0.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
```

Generate a complete, production-ready MCP server with type safety, proper error handling, comprehensive documentation, and Python best practices.
