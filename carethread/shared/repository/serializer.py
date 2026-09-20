"""DynamoDB serializer and deserializer helpers.

Handles conversion between Pydantic models and DynamoDB items,
specifically converting Python float to Decimal and vice versa,
preserving complete nested structures such as provenance citations.
"""

from decimal import Decimal
from enum import Enum
from typing import Any, Dict
from pydantic import BaseModel


def to_dynamodb_friendly(val: Any) -> Any:
    """Recursively convert values into DynamoDB-compatible types.

    Floats are converted to Decimal(str(val)).
    Enums are converted to their underlying string values.
    Pydantic models are converted via model_dump().
    """
    if isinstance(val, BaseModel):
        return to_dynamodb_friendly(val.model_dump())
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, float):
        return Decimal(str(val))
    if isinstance(val, dict):
        return {k: to_dynamodb_friendly(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [to_dynamodb_friendly(item) for item in val]
    return val


def from_dynamodb_friendly(val: Any) -> Any:
    """Recursively convert DynamoDB types back into Python primitives.

    Decimals are converted to int if whole number, otherwise float.
    """
    if isinstance(val, Decimal):
        if val % 1 == 0:
            return int(val)
        return float(val)
    if isinstance(val, dict):
        return {k: from_dynamodb_friendly(v) for k, v in val.items()}
    if isinstance(val, list):
        return [from_dynamodb_friendly(item) for item in val]
    return val
