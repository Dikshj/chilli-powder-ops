from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from .pipeline import WorkbookData, load_workbook
from .workflow import CanonicalProductionRecord, ClientCapabilities
from .workflow_service import output_row_to_record


class ProductionDataAdapter(ABC):
    """Adapter boundary shared by manual, ERP, and sensor inputs."""
    source_name: str

    @abstractmethod
    def records(self, client: ClientCapabilities) -> Iterable[CanonicalProductionRecord]:
        raise NotImplementedError


class ManualExcelAdapter(ProductionDataAdapter):
    source_name = "excel"

    def __init__(self, workbook: WorkbookData | None = None):
        self.workbook = workbook

    def records(self, client: ClientCapabilities) -> Iterable[CanonicalProductionRecord]:
        data = self.workbook or load_workbook()
        for row_number, row in enumerate(data.rows.get("1_Output", []), 2):
            yield output_row_to_record({**row, "_row": row_number}, client=client.client_id, source=self.source_name)


class ERPAdapter(ProductionDataAdapter):
    source_name = "erp"

    def records(self, client: ClientCapabilities) -> Iterable[CanonicalProductionRecord]:
        raise RuntimeError("ERP adapter configured but no ERP credentials or API specification is available")


class SensorAdapter(ProductionDataAdapter):
    source_name = "sensor"

    def records(self, client: ClientCapabilities) -> Iterable[CanonicalProductionRecord]:
        raise RuntimeError("Sensor adapter configured but no PLC/sensor protocol is available")


def adapter_for(client: ClientCapabilities, workbook: WorkbookData | None = None) -> ProductionDataAdapter:
    if client.input_tier == "manual":
        return ManualExcelAdapter(workbook)
    if client.input_tier == "erp":
        return ERPAdapter()
    return SensorAdapter()