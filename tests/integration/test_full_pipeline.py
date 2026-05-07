"""Testes de integração para o pipeline completo de migração."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orchestrator.state import MigrationState
from parity.comparator import ParityComparator
from parity.reporter import ParityReporter


@pytest.fixture
def cobol_source() -> str:
    sample_path = Path("examples/sample_cobol/CALCJURO.cbl")
    if sample_path.exists():
        return sample_path.read_text(encoding="utf-8")
    return "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. CALCJURO."


@pytest.fixture
def jcl_source() -> str:
    sample_path = Path("examples/sample_cobol/CALCJURO.jcl")
    if sample_path.exists():
        return sample_path.read_text(encoding="utf-8")
    return "//CALCJURO JOB (ACCT),'TESTE'"


@pytest.fixture
def base_state(cobol_source, jcl_source) -> MigrationState:
    return {
        "module_name": "CALCJURO",
        "cobol_source": cobol_source,
        "jcl_source": jcl_source,
        "business_rules": [],
        "bdd_specs": [],
        "generated_code": {},
        "pr_url": "",
        "test_results": {"passed": False, "coverage": 0.0, "parity_delta": []},
        "artifact_version": "",
        "acr_image_tag": "",
        "deploy_status": "",
        "observability_config": {},
        "errors": [],
        "execution_id": "integration-test-001",
        "started_at": "2026-01-01T00:00:00Z",
        "retry_count": 0,
        "status": "IN_PROGRESS",
    }


class TestRouterLogic:
    """Testa a lógica de roteamento do orquestrador sem chamar LLMs."""

    def test_route_after_tests_passes_to_packaging_when_tests_pass(self):
        from orchestrator.router import route_after_tests

        state: MigrationState = {
            "test_results": {"passed": True, "coverage": 85.0, "parity_delta": []},
            "retry_count": 0,
        }

        assert route_after_tests(state) == "packaging"

    def test_route_after_tests_retries_on_failure(self):
        from orchestrator.router import route_after_tests

        state: MigrationState = {
            "test_results": {"passed": False, "coverage": 60.0, "parity_delta": []},
            "retry_count": 1,
        }

        assert route_after_tests(state) == "development"

    def test_route_after_tests_fails_after_max_retries(self):
        from orchestrator.router import MAX_RETRY_ATTEMPTS, route_after_tests

        state: MigrationState = {
            "test_results": {"passed": False, "coverage": 0.0, "parity_delta": []},
            "retry_count": MAX_RETRY_ATTEMPTS,
        }

        assert route_after_tests(state) == "end_failed"

    def test_route_after_deployment_success(self):
        from orchestrator.router import route_after_deployment

        state: MigrationState = {"deploy_status": "SUCCESS"}
        assert route_after_deployment(state) == "observability"

    def test_route_after_deployment_failure(self):
        from orchestrator.router import route_after_deployment

        state: MigrationState = {"deploy_status": "FAILED"}
        assert route_after_deployment(state) == "end_failed"


class TestParityPipeline:
    """Testa o pipeline de parity testing de ponta a ponta (sem chamadas externas)."""

    def test_parity_report_approved_when_no_deltas(self):
        reporter = ParityReporter()
        report = reporter.generate(
            module_name="CALCJURO",
            execution_id="test-001",
            deltas=[],
            total_test_cases=10,
        )

        assert report["status"] == "APPROVED"
        assert report["summary"]["parity_rate"] == 100.0
        assert report["summary"]["total_divergences"] == 0

    def test_parity_report_divergent_with_deltas(self):
        reporter = ParityReporter()
        deltas = [
            {
                "field": "montante",
                "mainframe_value": "1000.00",
                "java_value": "999.50",
                "delta": 0.50,
                "test_case": "Caso 1",
            }
        ]
        report = reporter.generate(
            module_name="CALCJURO",
            execution_id="test-002",
            deltas=deltas,
            total_test_cases=5,
        )

        assert report["status"] == "DIVERGENT"
        assert report["summary"]["total_divergences"] == 1
        assert report["summary"]["parity_rate"] < 100.0

    def test_parity_report_to_text_includes_module_name(self):
        reporter = ParityReporter()
        report = reporter.generate("CALCJURO", "test-003", [], 3)
        text = reporter.to_text(report)

        assert "CALCJURO" in text
        assert "APROVADO" in text.upper() or "APPROVED" in text.upper()

    def test_parity_report_to_json_is_valid(self):
        reporter = ParityReporter()
        report = reporter.generate("CALCJURO", "test-004", [], 5)
        json_str = reporter.to_json(report)

        parsed = json.loads(json_str)
        assert parsed["module_name"] == "CALCJURO"
        assert "summary" in parsed

    def test_comparator_end_to_end_calcjuro(self):
        comparator = ParityComparator(tolerance=0.01)

        mainframe_output = {
            "montante_final": "1126.83",
            "juros_total": "126.83",
            "parcela_mensal": "88.85",
            "data_vencimento": "20270101",
            "status_retorno": "00",
        }

        java_output = {
            "montante_final": "1126.825",
            "juros_total": "126.825",
            "parcela_mensal": "88.849",
            "data_vencimento": "2027-01-01",
            "status_retorno": "00",
        }

        deltas = comparator.compare(mainframe_output, java_output)
        assert deltas == [], f"Divergências inesperadas: {deltas}"
