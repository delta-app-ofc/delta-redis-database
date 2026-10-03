from typing import Optional

from pydantic import BaseModel


class PropertyIn(BaseModel):
    organizationId: int
    propertyId: int
    name: str
    classificationGroup: str
    areaM2: Optional[float] = None


class DayEntry(BaseModel):
    date: str   # formato YYYY-MM-DD
    liters: float


class ConsumptionIn(BaseModel):
    propertyId: int
    days: list[DayEntry]
