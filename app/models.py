from datetime import date as Date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PropertyIn(BaseModel):
    organizationId: int = Field(description="Identificador da organização no PostgreSQL", examples=[3])
    propertyId: int = Field(description="Identificador da instalação no PostgreSQL", examples=[42])
    name: str = Field(description="Nome exibido para a instalação", examples=["Loja Swift · Moema"])
    classificationGroup: str = Field(description="Grupo da classificação; somente valores iniciados por COMERCIAL são aceitos", examples=["COMERCIAL_VAREJO"])
    areaM2: Optional[float] = Field(default=None, gt=0, description="Área construída em metros quadrados. Sem área, a instalação não participa do critério perm2.", examples=[650.0])


class DayEntry(BaseModel):
    date: Date = Field(description="Dia do consumo no formato AAAA-MM-DD", examples=["2026-10-01"])
    liters: float = Field(ge=0, description="Consumo registrado no dia, em litros", examples=[130.0])


class ConsumptionIn(BaseModel):
    propertyId: int = Field(description="Identificador da instalação previamente cadastrada", examples=[42])
    days: list[DayEntry] = Field(description="Leituras diárias. Reenviar a mesma data substitui o valor anterior.")


class SyncError(BaseModel):
    propertyId: int = Field(description="Instalação que falhou durante a sincronização")
    error: str = Field(description="Motivo informado para a falha")


class SyncResult(BaseModel):
    synced: int = Field(description="Quantidade de instalações sincronizadas com sucesso")
    total: int = Field(description="Quantidade de instalações comerciais selecionadas")
    errors: list[SyncError] = Field(description="Falhas individuais; vazio quando todas sincronizam")


class StatusResult(BaseModel):
    status: Literal["ok"] = Field(description="Resultado da operação", examples=["ok"])


class RankingItem(BaseModel):
    position: int = Field(description="Posição no ranking; 1 é a melhor colocação")
    propertyId: int = Field(description="Identificador da instalação")
    name: str = Field(description="Nome da instalação")
    areaM2: Optional[float] = Field(description="Área construída em m²; null quando não cadastrada")
    consumptionLiters: float = Field(description="Consumo total nos dias fechados com leitura, em litros")
    litersPerM2: Optional[float] = Field(description="Consumo total dividido pela área, em L/m²; null sem área")
    litersPerM2PerDay: Optional[float] = Field(description="Consumo médio diário dividido pela área, em L/m²·dia; null sem área")
    closedDaysWithReading: int = Field(description="Quantidade de dias fechados com leitura")


class PropertyWithoutArea(BaseModel):
    propertyId: int = Field(description="Identificador da instalação sem área cadastrada")
    name: str = Field(description="Nome da instalação")


class RankingResult(BaseModel):
    organizationId: int = Field(description="Organização consultada")
    period: str = Field(description="Mês consultado no formato AAAA-MM", examples=["2026-10"])
    criterion: Literal["perm2", "consumo"] = Field(description="Critério usado: perm2 (L/m²·dia) ou consumo (média diária em litros)")
    items: list[RankingItem] = Field(description="Instalações classificadas em ordem crescente do score")
    withoutArea: list[PropertyWithoutArea] = Field(description="Instalações da organização que não têm área e não entram em perm2")


class PositionResult(BaseModel):
    propertyId: int = Field(description="Identificador da instalação")
    period: str = Field(description="Mês consultado no formato AAAA-MM")
    criterion: Literal["perm2", "consumo"] = Field(description="Critério consultado")
    position: int = Field(description="Posição da instalação; 1 é a melhor colocação")
    totalInRanking: int = Field(description="Quantidade de instalações no ranking")
    score: Optional[float] = Field(description="Score usado para classificar a instalação, apresentado com quatro casas decimais")


class BestResult(BaseModel):
    organizationId: int = Field(description="Organização consultada")
    period: str = Field(description="Mês consultado no formato AAAA-MM")
    criterion: Literal["perm2", "consumo"] = Field(description="Critério consultado")
    best: RankingItem = Field(description="Instalação na primeira posição")
