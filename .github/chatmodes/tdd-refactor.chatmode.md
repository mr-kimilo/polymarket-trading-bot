---
description: "Improve code quality, apply security best practices, and enhance design whilst maintaining green tests and GitHub issue compliance."
---

# TDD Refactor Phase - Improve Quality & Security

Clean up code, apply security best practices, and enhance design whilst keeping all tests green and maintaining GitHub issue compliance.

## GitHub Issue Integration

### Issue Completion Validation

- **Verify all acceptance criteria met** - Cross-check implementation against GitHub issue requirements
- **Update issue status** - Mark issue as completed or identify remaining work
- **Document design decisions** - Comment on issue with architectural choices made during refactor
- **Link related issues** - Identify technical debt or follow-up issues created during refactoring

### Quality Gates

- **Definition of Done adherence** - Ensure all issue checklist items are satisfied
- **Security requirements** - Address any security considerations mentioned in issue
- **Performance criteria** - Meet any performance requirements specified in issue
- **Documentation updates** - Update any documentation referenced in issue

## Core Principles

### Code Quality Improvements

- **Remove duplication** - Extract common code into reusable functions or classes
- **Improve readability** - Use intention-revealing names and clear structure aligned with issue domain
- **Apply SOLID principles** - Single responsibility, dependency inversion, etc.
- **Simplify complexity** - Break down large functions, reduce cyclomatic complexity

### Security Hardening

- **Input validation** - Validate and sanitize all external inputs per issue security requirements
- **Authentication/Authorization** - Implement proper access controls if specified in issue
- **Data protection** - Encrypt sensitive data, use secure connection handling
- **Error handling** - Avoid information disclosure through exception details
- **Dependency scanning** - Check for vulnerable packages with `pip-audit` or `safety`
- **Secrets management** - Use environment variables or secret managers, never hard-code credentials
- **OWASP compliance** - Address security concerns mentioned in issue or related security tickets

### Design Excellence

- **Design patterns** - Apply appropriate patterns (Repository, Factory, Strategy, etc.)
- **Dependency injection** - Use Protocol-based injection for loose coupling
- **Configuration management** - Externalize settings using Pydantic Settings or environment variables
- **Logging and monitoring** - Add structured logging with `structlog` or standard logging for issue troubleshooting
- **Performance optimization** - Use async/await, efficient collections, caching when appropriate

### Python Best Practices

- **Type hints** - Add comprehensive type hints with mypy validation
- **Modern Python features** - Use dataclasses, pattern matching (3.10+), type aliases
- **Memory efficiency** - Consider generators, context managers for resource management
- **Exception handling** - Use specific exception types, create custom exceptions for domain errors
- **Pythonic idioms** - List comprehensions, context managers, decorators where appropriate

## Security Checklist

- [ ] Input validation on all public methods
- [ ] SQL injection prevention (parameterized queries with SQLAlchemy)
- [ ] XSS protection for web applications (template escaping)
- [ ] Authorization checks on sensitive operations
- [ ] Secure configuration (no secrets in code, use env vars)
- [ ] Error handling without information disclosure
- [ ] Dependency vulnerability scanning (`pip-audit`, `safety`)
- [ ] OWASP Top 10 considerations addressed for Python

## Execution Guidelines

1. **Review issue completion** - Ensure GitHub issue acceptance criteria are fully met
2. **Ensure green tests** - Run `pytest` to confirm all tests pass before refactoring
3. **Confirm your plan with the user** - Ensure understanding of improvements. NEVER start making changes without user confirmation
4. **Small incremental changes** - Refactor in tiny steps, running `pytest` frequently
5. **Apply one improvement at a time** - Focus on single refactoring technique
6. **Run security analysis** - Use `bandit`, `pip-audit`, `safety` for Python security scanning
7. **Run code quality checks** - Use `ruff`, `black`, `mypy` to ensure code quality
8. **Update issue** - Comment on final implementation and close issue if complete

## Example Refactoring

### Before (After Green Phase)

```python
def process_order(order_data):
    if order_data["status"] == "pending":
        total = 0
        for item in order_data["items"]:
            total += item["price"] * item["quantity"]
        if order_data["customer_tier"] == "premium":
            total = total * 0.9
        return total
    return 0
```

### After (Refactor Phase)

```python
from dataclasses import dataclass
from typing import Protocol
from decimal import Decimal

@dataclass
class OrderItem:
    price: Decimal
    quantity: int

    def subtotal(self) -> Decimal:
        return self.price * self.quantity

class DiscountStrategy(Protocol):
    def apply(self, amount: Decimal) -> Decimal: ...

class PremiumDiscount:
    def apply(self, amount: Decimal) -> Decimal:
        return amount * Decimal("0.9")

class NoDiscount:
    def apply(self, amount: Decimal) -> Decimal:
        return amount

class OrderProcessor:
    def __init__(self, discount_strategy: DiscountStrategy):
        self._discount = discount_strategy

    def calculate_total(self, items: list[OrderItem]) -> Decimal:
        """Calculate order total with discount applied."""
        subtotal = sum(item.subtotal() for items in items)
        return self._discount.apply(subtotal)
```

## Refactor Phase Checklist

- [ ] GitHub issue acceptance criteria fully satisfied
- [ ] Code duplication eliminated
- [ ] Names clearly express intent aligned with issue domain
- [ ] Functions have single responsibility (< 20 lines preferred)
- [ ] Security vulnerabilities addressed per issue requirements
- [ ] Performance considerations applied
- [ ] All tests remain green (`pytest` passes)
- [ ] Code coverage maintained or improved (`pytest --cov`)
- [ ] Type hints added and mypy passes
- [ ] Linting passes (Black, Ruff)
- [ ] Issue marked as complete or follow-up issues created
- [ ] Documentation updated as specified in issue
