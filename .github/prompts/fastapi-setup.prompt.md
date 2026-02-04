---
description: "Generate FastAPI application with best practices"
---

# FastAPI Application Setup

## Overview

This prompt helps you create a FastAPI application following clean architecture and DDD principles.

## Project Structure

```
project/
├── src/
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── entities/
│   │   ├── value_objects/
│   │   └── events.py
│   ├── application/
│   │   ├── __init__.py
│   │   ├── use_cases/
│   │   └── repositories.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── database/
│   │   ├── repositories/
│   │   └── config.py
│   └── api/
│       ├── __init__.py
│       ├── main.py
│       ├── routes/
│       ├── dependencies.py
│       └── schemas/
├── tests/
├── pyproject.toml
└── README.md
```

## main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routes import orders, customers
from infrastructure.database import engine, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown
    engine.dispose()

app = FastAPI(
    title="Order Management API",
    description="RESTful API for order management system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(customers.router, prefix="/api/v1/customers", tags=["customers"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

## API Route Example

```python
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from api.schemas.order import CreateOrderRequest, OrderResponse
from api.dependencies import get_order_use_case
from application.use_cases.create_order import CreateOrderUseCase

router = APIRouter()

@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order"
)
async def create_order(
    request: CreateOrderRequest,
    use_case: CreateOrderUseCase = Depends(get_order_use_case)
):
    """
    Create a new order for a customer.

    - **customer_id**: UUID of the customer
    - **items**: List of order items
    """
    try:
        order = use_case.execute(
            customer_id=UUID(request.customer_id),
            items=request.items
        )
        return OrderResponse.from_domain(order)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    use_case: CreateOrderUseCase = Depends(get_order_use_case)
):
    """Get order by ID."""
    order = use_case.get_by_id(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    return OrderResponse.from_domain(order)
```

## Pydantic Schemas

```python
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class OrderItemSchema(BaseModel):
    product_id: str = Field(..., description="Product UUID")
    quantity: int = Field(gt=0, description="Item quantity")
    price: float = Field(gt=0, description="Item price")

class CreateOrderRequest(BaseModel):
    customer_id: str = Field(..., description="Customer UUID")
    items: List[OrderItemSchema] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "123e4567-e89b-12d3-a456-426614174000",
                "items": [
                    {
                        "product_id": "prod-001",
                        "quantity": 2,
                        "price": 29.99
                    }
                ]
            }
        }

class OrderResponse(BaseModel):
    id: str
    customer_id: str
    status: str
    total_amount: float
    created_at: datetime

    @classmethod
    def from_domain(cls, order: Order) -> 'OrderResponse':
        """Convert domain entity to API response."""
        return cls(
            id=str(order.id),
            customer_id=str(order.customer_id),
            status=order.status,
            total_amount=order.calculate_total().amount,
            created_at=order.created_at
        )
```

## Dependencies

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from infrastructure.database import get_db_session
from infrastructure.repositories.order_repository import SqlAlchemyOrderRepository
from application.use_cases.create_order import CreateOrderUseCase

def get_order_repository(
    session: Session = Depends(get_db_session)
) -> SqlAlchemyOrderRepository:
    return SqlAlchemyOrderRepository(session)

def get_order_use_case(
    repository: SqlAlchemyOrderRepository = Depends(get_order_repository)
) -> CreateOrderUseCase:
    return CreateOrderUseCase(repository)
```

## Testing

```python
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_create_order():
    response = client.post(
        "/api/v1/orders/",
        json={
            "customer_id": "123e4567-e89b-12d3-a456-426614174000",
            "items": [
                {"product_id": "p1", "quantity": 2, "price": 10.0}
            ]
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "PENDING"
```

## Running the Application

```bash
# Install dependencies
pip install fastapi uvicorn sqlalchemy pydantic

# Development mode with auto-reload
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Environment Variables

```python
# infrastructure/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    secret_key: str
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

```bash
# .env
DATABASE_URL=postgresql://user:pass@localhost/dbname
SECRET_KEY=your-secret-key
DEBUG=True
```
