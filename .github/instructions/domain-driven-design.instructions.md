---
description: "Domain-Driven Design principles and tactical patterns for Python"
applyTo: "**/*.py"
---

# Domain-Driven Design Instructions

## Overview

This instruction file enforces Domain-Driven Design (DDD) tactical patterns in Python projects.

## Building Blocks

### 1. Entities

Objects with a distinct identity that persists over time.

```python
from dataclasses import dataclass
from typing import List
from uuid import UUID, uuid4

@dataclass
class Customer:
    id: UUID
    email: str
    name: str
    _version: int = 0

    @classmethod
    def create(cls, email: str, name: str) -> 'Customer':
        """Factory method for entity creation"""
        return cls(id=uuid4(), email=email, name=name)

    def change_email(self, new_email: str) -> None:
        """Domain behavior"""
        if '@' not in new_email:
            raise ValueError("Invalid email format")
        self.email = new_email
        self._version += 1
```

### 2. Value Objects

Immutable objects defined by their attributes, not identity.

```python
from dataclasses import dataclass
from typing import Self

@dataclass(frozen=True)
class Money:
    amount: float
    currency: str

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")
        if not self.currency:
            raise ValueError("Currency is required")

    def add(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)

    def multiply(self, factor: float) -> 'Money':
        return Money(self.amount * factor, self.currency)
```

### 3. Aggregates

A cluster of entities and value objects with a root entity.

```python
from dataclasses import dataclass, field
from typing import List
from datetime import datetime

@dataclass
class OrderItem:
    product_id: str
    quantity: int
    price: Money

@dataclass
class Order:
    """Aggregate Root"""
    id: UUID
    customer_id: UUID
    items: List[OrderItem] = field(default_factory=list)
    status: str = "PENDING"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_item(self, product_id: str, quantity: int, price: Money) -> None:
        """Business invariant: can't modify confirmed orders"""
        if self.status != "PENDING":
            raise ValueError("Cannot modify confirmed order")

        # Check if item exists, update quantity
        for item in self.items:
            if item.product_id == product_id:
                item.quantity += quantity
                return

        self.items.append(OrderItem(product_id, quantity, price))

    def confirm(self) -> None:
        """State transition with validation"""
        if not self.items:
            raise ValueError("Cannot confirm empty order")
        if self.status != "PENDING":
            raise ValueError("Order already confirmed")
        self.status = "CONFIRMED"

    def calculate_total(self) -> Money:
        """Aggregate consistency"""
        if not self.items:
            return Money(0, "USD")

        total = self.items[0].price.multiply(self.items[0].quantity)
        for item in self.items[1:]:
            total = total.add(item.price.multiply(item.quantity))
        return total
```

### 4. Domain Events

Represent something that happened in the domain.

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=datetime.utcnow)

@dataclass(frozen=True)
class OrderConfirmed(DomainEvent):
    order_id: UUID
    customer_id: UUID
    total_amount: Money

@dataclass
class Order:
    # ... previous code ...
    _events: List[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def confirm(self) -> None:
        if not self.items:
            raise ValueError("Cannot confirm empty order")
        if self.status != "PENDING":
            raise ValueError("Order already confirmed")

        self.status = "CONFIRMED"

        # Record domain event
        event = OrderConfirmed(
            order_id=self.id,
            customer_id=self.customer_id,
            total_amount=self.calculate_total()
        )
        self._events.append(event)

    def clear_events(self) -> List[DomainEvent]:
        events = self._events.copy()
        self._events.clear()
        return events
```

### 5. Repositories (Protocol)

Abstract persistence mechanism.

```python
from typing import Protocol, Optional
from uuid import UUID

class OrderRepository(Protocol):
    """Repository interface (port)"""

    def get_by_id(self, order_id: UUID) -> Optional[Order]:
        """Retrieve aggregate by ID"""
        ...

    def save(self, order: Order) -> None:
        """Persist aggregate"""
        ...

    def find_by_customer(self, customer_id: UUID) -> List[Order]:
        """Query method"""
        ...
```

### 6. Domain Services

Operations that don't naturally fit into entities or value objects.

```python
class PricingService:
    """Domain service for complex pricing logic"""

    def calculate_discounted_price(
        self,
        base_price: Money,
        customer_tier: str,
        quantity: int
    ) -> Money:
        discount = 0.0

        if customer_tier == "PREMIUM":
            discount = 0.10
        elif customer_tier == "VIP":
            discount = 0.20

        if quantity >= 10:
            discount += 0.05

        return base_price.multiply(1 - discount)
```

## Ubiquitous Language

- Use domain terms in code (e.g., `Order`, `Customer`, not `OrderData`, `CustomerInfo`)
- Method names reflect business operations (e.g., `confirm_order()`, not `set_status()`)
- Module names match bounded contexts

## Bounded Context

Organize code by bounded contexts:

```
ordering/
├── domain/
│   ├── order.py
│   ├── customer.py
│   └── events.py
├── application/
│   └── services.py
└── infrastructure/
    └── repositories.py

shipping/
├── domain/
│   ├── shipment.py
│   └── events.py
└── ...
```

## Rules

1. **Aggregate Boundaries**: Only reference other aggregates by ID, not object reference
2. **Immutability**: Value objects must be immutable (use `frozen=True`)
3. **Encapsulation**: Aggregate state changes only through methods
4. **Domain Events**: Use events for cross-aggregate consistency
5. **Repository per Aggregate**: One repository per aggregate root
6. **No Anemic Domain Model**: Entities must contain business logic

## Anti-Patterns to Avoid

❌ **Anemic Domain Model**

```python
# Bad: No behavior, just data
@dataclass
class Order:
    id: UUID
    items: List[OrderItem]
    status: str
```

✅ **Rich Domain Model**

```python
# Good: Behavior and invariants
@dataclass
class Order:
    id: UUID
    items: List[OrderItem]
    status: str

    def add_item(self, item: OrderItem) -> None:
        if self.status != "PENDING":
            raise ValueError("Cannot modify confirmed order")
        self.items.append(item)
```

## Testing

- Test domain logic without infrastructure dependencies
- Use example-based tests for business rules
- Use property-based testing (hypothesis) for invariants

```python
def test_order_cannot_be_confirmed_when_empty():
    order = Order(id=uuid4(), customer_id=uuid4())

    with pytest.raises(ValueError, match="Cannot confirm empty order"):
        order.confirm()
```

## Validation Checklist

- [ ] Entities have identity and behavior
- [ ] Value objects are immutable
- [ ] Aggregates enforce invariants
- [ ] Domain events record state changes
- [ ] Repositories use protocols (interfaces)
- [ ] Ubiquitous language is used consistently
- [ ] No infrastructure dependencies in domain layer
