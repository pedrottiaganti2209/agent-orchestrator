"""Testes unitários para o ParityComparator."""
from __future__ import annotations

import pytest

from parity.comparator import ParityComparator


@pytest.fixture
def comparator() -> ParityComparator:
    return ParityComparator(tolerance=0.001)


class TestParityComparator:
    def test_identical_outputs_return_no_deltas(self, comparator):
        mainframe = {"montante": "1126.83", "juros": "126.83"}
        java = {"montante": "1126.83", "juros": "126.83"}

        deltas = comparator.compare(mainframe, java)
        assert deltas == []

    def test_numeric_within_tolerance_returns_no_delta(self, comparator):
        mainframe = {"montante": "1126.830"}
        java = {"montante": "1126.8305"}

        deltas = comparator.compare(mainframe, java)
        assert deltas == []

    def test_numeric_exceeding_tolerance_returns_delta(self, comparator):
        mainframe = {"montante": "1000.00"}
        java = {"montante": "1001.50"}

        deltas = comparator.compare(mainframe, java)
        assert len(deltas) == 1
        assert deltas[0]["field"] == "montante"
        assert deltas[0]["delta"] == pytest.approx(1.50, abs=0.01)

    def test_date_normalization_yyyymmdd(self, comparator):
        mainframe = {"data_vencimento": "20261231"}
        java = {"data_vencimento": "2026-12-31"}

        deltas = comparator.compare(mainframe, java)
        assert deltas == []

    def test_date_normalization_ddmmyyyy(self, comparator):
        mainframe = {"data": "31122026"}
        java = {"data": "31/12/2026"}

        deltas = comparator.compare(mainframe, java)
        assert deltas == []

    def test_ignored_fields_are_skipped(self, comparator):
        mainframe = {"timestamp": "2026-01-01T00:00:00Z", "montante": "1000.00"}
        java = {"timestamp": "2026-12-31T23:59:59Z", "montante": "1000.00"}

        deltas = comparator.compare(mainframe, java)
        assert deltas == []

    def test_nested_objects_compared_recursively(self, comparator):
        mainframe = {"resultado": {"montante": "1000.00", "juros": "100.00"}}
        java = {"resultado": {"montante": "1000.00", "juros": "200.00"}}

        deltas = comparator.compare(mainframe, java)
        assert len(deltas) == 1
        assert deltas[0]["field"] == "resultado.juros"

    def test_list_comparison(self, comparator):
        mainframe = {"parcelas": ["100.00", "100.00", "100.00"]}
        java = {"parcelas": ["100.00", "100.00", "100.00"]}

        deltas = comparator.compare(mainframe, java)
        assert deltas == []

    def test_list_length_mismatch_reported(self, comparator):
        mainframe = {"parcelas": ["100.00", "100.00"]}
        java = {"parcelas": ["100.00"]}

        deltas = comparator.compare(mainframe, java)
        assert any(d.get("delta") == 1 for d in deltas)

    def test_string_comparison_case_insensitive(self, comparator):
        mainframe = {"status": "OK"}
        java = {"status": "ok"}

        deltas = comparator.compare(mainframe, java)
        assert deltas == []

    def test_none_values_no_delta(self, comparator):
        mainframe = {"campo_opcional": None}
        java = {"campo_opcional": None}

        deltas = comparator.compare(mainframe, java)
        assert deltas == []

    def test_custom_tolerance(self):
        strict_comparator = ParityComparator(tolerance=0.0001)
        mainframe = {"valor": "100.00"}
        java = {"valor": "100.0005"}

        deltas = strict_comparator.compare(mainframe, java)
        assert len(deltas) == 1

    def test_custom_ignored_fields(self):
        custom_comparator = ParityComparator(ignored_fields={"campo_custom"})
        mainframe = {"campo_custom": "A", "valor": "100"}
        java = {"campo_custom": "B", "valor": "100"}

        deltas = custom_comparator.compare(mainframe, java)
        assert deltas == []
