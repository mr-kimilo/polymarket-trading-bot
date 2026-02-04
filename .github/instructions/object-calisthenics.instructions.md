---
description: "Object Calisthenics rules for better object-oriented design in Python"
applyTo: "**/*.py"
---

# Object Calisthenics Instructions

## Overview

Object Calisthenics is a set of programming exercises designed to improve code quality through strict constraints. These rules help create more maintainable, testable, and readable object-oriented code.

## The Nine Rules

### 1. Only One Level of Indentation Per Method

Keep methods simple with minimal nesting.

✅ **Good:**

```python
def process_orders(orders: List[Order]) -> List[ProcessedOrder]:
    return [self._process_single_order(order) for order in orders]

def _process_single_order(self, order: Order) -> ProcessedOrder:
    validated = self._validate_order(order)
    return self._apply_processing(validated)
```

❌ **Bad:**

```python
def process_orders(orders: List[Order]) -> List[ProcessedOrder]:
    results = []
    for order in orders:
        if order.is_valid():
            if order.has_items():
                for item in order.items:
                    if item.in_stock():
                        results.append(process_item(item))
    return results
```

### 2. Don't Use the ELSE Keyword

Use early returns and guard clauses instead.

✅ **Good:**

```python
def calculate_discount(customer: Customer, amount: float) -> float:
    if not customer.is_premium():
        return amount

    if amount < 100:
        return amount * 0.95

    return amount * 0.90
```

❌ **Bad:**

```python
def calculate_discount(customer: Customer, amount: float) -> float:
    if customer.is_premium():
        if amount >= 100:
            return amount * 0.90
        else:
            return amount * 0.95
    else:
        return amount
```

### 3. Wrap All Primitives and Strings

Encapsulate primitives in value objects.

✅ **Good:**

```python
@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self):
        if '@' not in self.value:
            raise ValueError("Invalid email format")

@dataclass(frozen=True)
class CustomerId:
    value: str

class Customer:
    def __init__(self, id: CustomerId, email: Email):
        self.id = id
        self.email = email
```

❌ **Bad:**

```python
class Customer:
    def __init__(self, id: str, email: str):
        self.id = id  # Primitive obsession
        self.email = email
```

### 4. First Class Collections

Collections should be wrapped in their own class.

✅ **Good:**

```python
@dataclass
class OrderItems:
    _items: List[OrderItem] = field(default_factory=list)

    def add(self, item: OrderItem) -> None:
        if self._contains(item.product_id):
            self._update_quantity(item)
        else:
            self._items.append(item)

    def total(self) -> Money:
        return sum((item.price.multiply(item.quantity) for item in self._items))

    def _contains(self, product_id: str) -> bool:
        return any(item.product_id == product_id for item in self._items)

class Order:
    def __init__(self, items: OrderItems):
        self.items = items
```

❌ **Bad:**

```python
class Order:
    def __init__(self):
        self.items: List[OrderItem] = []  # Exposed collection

    def add_item(self, item: OrderItem):
        self.items.append(item)  # No encapsulation
```

### 5. One Dot Per Line

Avoid method chaining violations of Law of Demeter.

✅ **Good:**

```python
class Order:
    def get_customer_email(self) -> Email:
        return self._customer.email

    def notify_customer(self) -> None:
        email = self.get_customer_email()
        self._notifier.send(email)
```

❌ **Bad:**

```python
class Order:
    def notify_customer(self) -> None:
        # Multiple dots - violates Law of Demeter
        self._notifier.send(self._customer.get_contact().get_email())
```

### 6. Don't Abbreviate

Use full, descriptive names.

✅ **Good:**

```python
class CustomerRepository:
    def find_by_email(self, email: Email) -> Optional[Customer]:
        pass

def calculate_total_amount(items: List[OrderItem]) -> Money:
    pass
```

❌ **Bad:**

```python
class CustRepo:  # Abbreviated
    def find_by_em(self, em: Email) -> Optional[Customer]:  # Unclear
        pass

def calc_tot_amt(itms: List[OrderItem]) -> Money:  # Hard to read
    pass
```

### 7. Keep All Entities Small

Classes should be focused and cohesive.

**Rules:**

- Maximum 50 lines per class
- Maximum 10 public methods
- Maximum 5 instance variables

✅ **Good:**

```python
@dataclass
class Money:
    """Small, focused value object."""
    amount: float
    currency: str

    def add(self, other: 'Money') -> 'Money':
        self._check_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def multiply(self, factor: float) -> 'Money':
        return Money(self.amount * factor, self.currency)
```

❌ **Bad:**

```python
class OrderManager:
    """God class with too many responsibilities."""
    def create_order(self): pass
    def update_order(self): pass
    def delete_order(self): pass
    def validate_order(self): pass
    def calculate_total(self): pass
    def apply_discount(self): pass
    def process_payment(self): pass
    def send_confirmation(self): pass
    def handle_shipping(self): pass
    def generate_invoice(self): pass
    # ... 20 more methods
```

### 8. No Classes with More Than Two Instance Variables

Promotes high cohesion and single responsibility.

✅ **Good:**

```python
@dataclass(frozen=True)
class Address:
    street: str
    city: str

@dataclass(frozen=True)
class Contact:
    email: Email
    phone: Phone

@dataclass
class Customer:
    id: CustomerId
    contact: Contact  # Grouped related data
```

❌ **Bad:**

```python
@dataclass
class Customer:
    id: str
    email: str
    phone: str
    street: str
    city: str
    country: str  # Too many instance variables
```

### 9. No Getters/Setters/Properties (Tell, Don't Ask)

Objects should do work, not expose data.

✅ **Good:**

```python
@dataclass
class Order:
    id: OrderId
    items: OrderItems
    status: OrderStatus

    def confirm(self) -> None:
        """Tell the object what to do."""
        if self.items.is_empty():
            raise ValueError("Cannot confirm empty order")
        self.status = OrderStatus.CONFIRMED

    def is_ready_to_ship(self) -> bool:
        """Behavioral query."""
        return self.status == OrderStatus.CONFIRMED and not self.items.is_empty()
```

❌ **Bad:**

```python
@dataclass
class Order:
    id: OrderId
    items: List[OrderItem]
    status: str

    # Just data exposure
    def get_status(self) -> str:
        return self.status

    def set_status(self, status: str) -> None:
        self.status = status

# Client has to make decisions
if order.get_status() == "CONFIRMED" and len(order.items) > 0:
    order.set_status("READY_TO_SHIP")
```

## Practical Application

These rules are strict and may not always be practical. Use them as guidelines:

- **Learning**: Practice all rules strictly to understand principles
- **Production**: Apply pragmatically based on context
- **Code Reviews**: Use as discussion points for improvement

## Benefits

1. **Simplicity**: Smaller, focused components
2. **Testability**: Easy to test isolated behaviors
3. **Readability**: Clear intent and responsibilities
4. **Maintainability**: Changes are localized
5. **Design**: Forces good OO design thinking

## Validation Checklist

- [ ] Methods have one level of indentation
- [ ] No else keywords (use early returns)
- [ ] Primitives wrapped in value objects
- [ ] Collections are first-class
- [ ] One dot per line (Law of Demeter)
- [ ] No abbreviations in names
- [ ] Classes under 50 lines
- [ ] Max 2 instance variables per class
- [ ] Behavior over data access
