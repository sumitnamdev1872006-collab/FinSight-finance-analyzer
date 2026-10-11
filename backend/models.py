"""
FinSight — models.py
Pydantic models used to validate incoming request data.
"""

from pydantic import BaseModel, field_validator
from typing import Optional


class Transaction(BaseModel):
    date:        str
    description: str
    amount:      float
    type:        str          # "income" or "expense"
    category:    Optional[str] = "Other"

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return round(v, 2)

    @field_validator("type")
    @classmethod
    def type_must_be_valid(cls, v):
        if v not in ("income", "expense"):
            raise ValueError("Type must be 'income' or 'expense'")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Description cannot be empty")
        return v.strip()

    @field_validator("date")
    @classmethod
    def date_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Date cannot be empty")
        return v.strip()
