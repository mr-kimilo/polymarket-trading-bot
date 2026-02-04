---
description: "Conventional Commits specification for consistent commit messages"
---

# Conventional Commits Instructions

## Overview

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for all commit messages.

## Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

## Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Changes to build process or auxiliary tools
- **ci**: CI/CD pipeline changes

## Examples

```
feat(orders): add discount calculation to order total

Implement discount logic based on customer tier and quantity.
Discounts are applied before tax calculation.

Closes #123
```

```
fix(api): handle missing customer_id in order creation

Previously would crash with KeyError. Now returns 400 Bad Request
with clear error message.
```

```
test(domain): add tests for order confirmation edge cases
```

## Breaking Changes

Use `!` or `BREAKING CHANGE:` footer:

```
feat(api)!: change order status enum values

BREAKING CHANGE: Order status values changed from integers to strings.
Update all API clients to use "pending", "confirmed" instead of 0, 1.
```

## Rules

- Use imperative mood ("add" not "added" or "adds")
- Don't capitalize first letter of subject
- No period at the end of subject
- Keep subject under 72 characters
- Separate subject from body with blank line
- Wrap body at 72 characters
