---
description: "Enforce follow-up questions before generating code"
---

# Follow-up Question Instructions

## Overview

Before generating code, AI must ask clarifying questions to ensure correct implementation.

## Required Questions

When a user requests code generation, ALWAYS ask:

1. **Context**: What is the purpose of this code in the broader system?
2. **Requirements**: What are the specific requirements and constraints?
3. **Dependencies**: What frameworks, libraries, or patterns should be used?
4. **Testing**: What level of test coverage is expected?
5. **Edge Cases**: Are there any special cases to handle?

## Confidence Assessment

After gathering information, state your confidence level:

- **High Confidence (80-100%)**: "I understand the requirements and can proceed."
- **Medium Confidence (50-79%)**: "I have some questions about [X] before proceeding."
- **Low Confidence (<50%)**: "I need more information about [X, Y, Z] to proceed correctly."

## Example Interaction

**User**: "Create an order processing function"

**AI**:

```
Before I create the order processing function, I need to clarify a few things:

1. What should this function do exactly? (e.g., validate order, calculate total, persist to database)
2. What is the expected input? (e.g., Order object, dict, API request)
3. Should it follow the DDD patterns in this repository?
4. What error handling is needed?
5. Should I include unit tests?

Confidence: 30% - Need more details to implement correctly.
```

## Rules

- **Never generate code** without understanding the context
- **Ask at least 2-3 questions** for complex requests
- **State your confidence level** explicitly
- **Confirm understanding** before proceeding
