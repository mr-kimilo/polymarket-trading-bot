---
description: "Defines layered architecture principles for maintainable Python applications"
applyTo: "**/*.py"
---

# Clean Architecture Instructions

## Overview

This instruction file enforces Clean Architecture principles in Python projects to ensure separation of concerns, testability, and maintainability.

## Layer Structure

### 1. Domain Layer (Core/Entities)

- Contains business entities, value objects, and domain logic
- No dependencies on external frameworks or libraries (except standard library)
- Pure Python classes with business rules
- Located in: `domain/` or `core/`

**Example:**

```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass(frozen=True)
class OrderId:
    value: str

@dataclass
class Order:
    id: OrderId
    customer_id: str
    created_at: datetime
    total_amount: float

    def apply_discount(self, percentage: float) -> 'Order':
        """Business logic stays in the domain"""
        if not 0 <= percentage <= 100:
            raise ValueError("Invalid discount percentage")
        new_total = self.total_amount * (1 - percentage / 100)
        return Order(self.id, self.customer_id, self.created_at, new_total)
```

### 2. Application Layer (Use Cases)

- Contains application-specific business rules
- Orchestrates the flow of data between layers
- Uses interfaces/protocols for external dependencies
- Located in: `application/` or `use_cases/`

**Example:**

```python
from typing import Protocol
from domain.order import Order, OrderId

class OrderRepository(Protocol):
    def get_by_id(self, order_id: OrderId) -> Optional[Order]:
        ...

    def save(self, order: Order) -> None:
        ...

class ApplyDiscountUseCase:
    def __init__(self, order_repository: OrderRepository):
        self._repository = order_repository

    def execute(self, order_id: OrderId, discount: float) -> Order:
        order = self._repository.get_by_id(order_id)
        if not order:
            raise ValueError(f"Order {order_id.value} not found")

        discounted_order = order.apply_discount(discount)
        self._repository.save(discounted_order)
        return discounted_order
```

### 3. Infrastructure Layer

- Implements interfaces defined in application layer
- Contains framework-specific code (database, API clients, file I/O)
- Located in: `infrastructure/`

**Example:**

```python
from sqlalchemy.orm import Session
from domain.order import Order, OrderId
from application.repositories import OrderRepository

class SqlAlchemyOrderRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_by_id(self, order_id: OrderId) -> Optional[Order]:
        # SQLAlchemy-specific implementation
        ...

    def save(self, order: Order) -> None:
        # SQLAlchemy-specific implementation
        ...
```

### 4. Presentation Layer (API/UI)

- Handles HTTP requests, CLI commands, or UI events
- Converts external data formats to domain models
- Located in: `api/` or `presentation/`

**Example:**

```python
from fastapi import FastAPI, Depends
from pydantic import BaseModel

app = FastAPI()

class ApplyDiscountRequest(BaseModel):
    order_id: str
    discount_percentage: float

@app.post("/orders/{order_id}/discount")
async def apply_discount(
    order_id: str,
    request: ApplyDiscountRequest,
    use_case: ApplyDiscountUseCase = Depends(get_use_case)
):
    order = use_case.execute(
        OrderId(request.order_id),
        request.discount_percentage
    )
    return {"order_id": order.id.value, "total": order.total_amount}
```

## Dependency Rule

**CRITICAL:** Dependencies must always point inward:

- Domain layer has NO dependencies
- Application layer depends only on Domain
- Infrastructure depends on Application and Domain
- Presentation depends on Application and Domain

## Type Hints and Protocols

- Use `typing.Protocol` for dependency inversion
- All public methods must have type hints
- Use `mypy` for static type checking

## Testing Strategy

- **Unit tests** for domain logic (no mocks needed)
- **Integration tests** for use cases (mock infrastructure)
- **E2E tests** for API endpoints (with test database)

## File Organization

```
project/
├── domain/
│   ├── entities/
│   ├── value_objects/
│   └── exceptions.py
├── application/
│   ├── use_cases/
│   ├── repositories.py  # Protocol definitions
│   └── services.py
├── infrastructure/
│   ├── database/
│   ├── external_apis/
│   └── repositories/
└── api/
    ├── routes/
    ├── dependencies.py
    └── schemas.py
```

## Validation Checklist

- [ ] Domain entities contain no framework dependencies
- [ ] Use cases depend on protocols, not concrete implementations
- [ ] Infrastructure implements application protocols
- [ ] All layers use type hints
- [ ] Dependencies flow inward only
