from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class PropertyIn(BaseModel):
    organizationId: int
    propertyId: int
    name: str
    classificationGroup: str
    areaM2: Optional[float] = None


class DayEntry(BaseModel):
    date: date
    liters: float = Field(ge=0)


class ConsumptionIn(BaseModel):
    propertyId: int
    days: list[DayEntry]


class SyncError(BaseModel):
    propertyId: int
    error: str


class SyncResult(BaseModel):
    synced: int
    total: int
    errors: list[SyncError]
