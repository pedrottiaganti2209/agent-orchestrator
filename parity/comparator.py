"""Comparador campo a campo de outputs do mainframe vs serviço Java."""
from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_TOLERANCE = float(os.getenv("PARITY_TOLERANCE", "0.001"))

IGNORED_FIELDS = {
    "timestamp",
    "created_at",
    "updated_at",
    "sequence_number",
    "seq_num",
    "process_date",
    "run_id",
}

DATE_FORMATS = [
    "%Y%m%d",
    "%d%m%Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%Y%j",
]


class ParityComparator:
    """Compara outputs do mainframe e do serviço Java campo a campo.

    Suporta:
    - Tolerância configurável para valores numéricos (padrão: 0.001)
    - Normalização de datas (múltiplos formatos COBOL)
    - Lista de campos a ignorar (timestamps, sequence numbers)
    - Comparação recursiva de objetos aninhados
    """

    def __init__(
        self,
        tolerance: float = DEFAULT_TOLERANCE,
        ignored_fields: set[str] | None = None,
    ) -> None:
        self.tolerance = tolerance
        self.ignored_fields = ignored_fields or IGNORED_FIELDS

    def compare(self, mainframe_output: dict, java_output: dict) -> list[dict]:
        """Compara dois outputs campo a campo e retorna lista de divergências.

        Args:
            mainframe_output: Saída de referência do mainframe (via shadow).
            java_output: Saída do serviço Java migrado.

        Returns:
            Lista de dicts com: field, mainframe_value, java_value, delta.
            Lista vazia indica paridade perfeita.
        """
        return self._compare_recursive(mainframe_output, java_output, prefix="")

    def _compare_recursive(
        self,
        mainframe: Any,
        java: Any,
        prefix: str,
    ) -> list[dict]:
        """Compara recursivamente estruturas aninhadas."""
        deltas: list[dict] = []

        if isinstance(mainframe, dict) and isinstance(java, dict):
            all_keys = set(mainframe.keys()) | set(java.keys())
            for key in sorted(all_keys):
                field_name = f"{prefix}.{key}" if prefix else key
                if key.lower() in {f.lower() for f in self.ignored_fields}:
                    continue

                m_val = mainframe.get(key)
                j_val = java.get(key)

                if m_val is None and j_val is None:
                    continue

                sub_deltas = self._compare_recursive(m_val, j_val, field_name)
                deltas.extend(sub_deltas)

        elif isinstance(mainframe, list) and isinstance(java, list):
            for i, (m_item, j_item) in enumerate(zip(mainframe, java)):
                sub_deltas = self._compare_recursive(m_item, j_item, f"{prefix}[{i}]")
                deltas.extend(sub_deltas)

            if len(mainframe) != len(java):
                deltas.append({
                    "field": prefix,
                    "mainframe_value": f"list[{len(mainframe)}]",
                    "java_value": f"list[{len(java)}]",
                    "delta": abs(len(mainframe) - len(java)),
                })
        else:
            delta = self._compare_values(mainframe, java, prefix)
            if delta:
                deltas.append(delta)

        return deltas

    def _compare_values(self, mainframe_val: Any, java_val: Any, field: str) -> dict | None:
        """Compara dois valores escalares com normalização e tolerância."""
        if mainframe_val == java_val:
            return None

        normalized_m = self._normalize_date(mainframe_val)
        normalized_j = self._normalize_date(java_val)
        if normalized_m and normalized_j and normalized_m == normalized_j:
            return None

        try:
            m_decimal = Decimal(str(mainframe_val).replace(",", "."))
            j_decimal = Decimal(str(java_val).replace(",", "."))
            delta = float(abs(m_decimal - j_decimal))
            if delta <= self.tolerance:
                return None
            return {"field": field, "mainframe_value": str(mainframe_val), "java_value": str(java_val), "delta": delta}
        except (InvalidOperation, ValueError, TypeError):
            pass

        m_str = str(mainframe_val).strip().upper()
        j_str = str(java_val).strip().upper()
        if m_str == j_str:
            return None

        return {"field": field, "mainframe_value": mainframe_val, "java_value": java_val, "delta": None}

    @staticmethod
    def _normalize_date(value: Any) -> datetime | None:
        """Tenta normalizar um valor como data em múltiplos formatos COBOL."""
        if not isinstance(value, str) or len(value) < 6:
            return None
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None
