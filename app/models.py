from datetime import date
from typing import Optional

from pydantic import BaseModel


class PropertyIn(BaseModel):
    organizationId: int
    propertyId: int
    name: str
    classificationGroup: str
    areaM2: Optional[float] = None


class DayEntry(BaseModel):
    date: date       # Pydantic valida formato YYYY-MM-DD automaticamente
    liters: float


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
