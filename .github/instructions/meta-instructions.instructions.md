---
description: "Meta-instruction defining how to write instruction files"
---

# Meta-Instructions for Writing Instruction Files

## Overview

This meta-instruction file defines the standard format, structure, and best practices for creating instruction files in `.github/instructions/`.

## File Naming Convention

All instruction files must follow this pattern:

```
<topic-name>.instructions.md
```

Examples:

- `domain-driven-design.instructions.md`
- `coding-style-python.instructions.md`
- `unit-and-integration-tests.instructions.md`

## Required Structure

Every instruction file must include:

### 1. Frontmatter

YAML frontmatter with metadata:

```yaml
---
description: "Brief description of what this instruction covers"
applyTo: "**/*.py" # Optional: file pattern
---
```

### 2. Title and Overview

```markdown
# [Topic] Instructions

## Overview

A clear, concise description of what this instruction file enforces.
```

### 3. Main Content Sections

Organize content logically with clear headings:

- Principles/Rules
- Examples (Good vs Bad)
- Implementation details
- Best practices

### 4. Validation Checklist

End with a checklist for easy reference:

```markdown
## Validation Checklist

- [ ] Item 1
- [ ] Item 2
- [ ] Item 3
```

## Content Guidelines

### Language

- Write in English only
- Use imperative mood for rules ("Use X" not "You should use X")
- Be specific and actionable

### Code Examples

- Include both ✅ Good and ❌ Bad examples
- Add comments explaining why
- Use realistic examples from the domain

### Structure

- Use hierarchical headings (##, ###, ####)
- Keep sections focused and cohesive
- Use bullet points for lists
- Use code blocks with language tags

## Example Template

````markdown
---
description: "Brief description"
applyTo: "**/*.py"
---

# Topic Instructions

## Overview

Clear explanation of what this instruction enforces.

## Section 1: Core Principles

### Rule 1

Explanation of the rule.

✅ **Good:**

```python
# Good example with explanation
def good_example():
    pass
```
````

❌ **Bad:**

```python
# Bad example with explanation
def bad_example():
    pass
```

## Section 2: Implementation

Detailed guidance on how to implement...

## Best Practices

1. Practice 1
2. Practice 2

## Anti-Patterns to Avoid

List common mistakes...

## Validation Checklist

- [ ] Rule 1 followed
- [ ] Rule 2 followed

```

## Frontmatter Attributes

Supported attributes:
- `description` (required): Brief description
- `applyTo` (optional): File pattern for when instructions apply

## Review Checklist

Before committing an instruction file:

- [ ] Follows naming convention
- [ ] Has valid YAML frontmatter with description
- [ ] Includes clear overview section
- [ ] Has code examples (good and bad)
- [ ] Includes validation checklist
- [ ] Written in clear, actionable language
- [ ] No grammatical errors
- [ ] Links to external resources are valid
- [ ] Consistent with other instruction files
```
