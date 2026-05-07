"""Testes unitários para o AnalysisAgent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.analysis_agent import AnalysisAgent
from orchestrator.state import MigrationState


@pytest.fixture
def sample_state() -> MigrationState:
    return {
        "module_name": "CALCJURO",
        "cobol_source": "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. CALCJURO.",
        "jcl_source": "//CALCJURO JOB (ACCT),'TESTE'",
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
        "execution_id": "test-exec-001",
        "started_at": "2026-01-01T00:00:00Z",
        "retry_count": 0,
        "status": "IN_PROGRESS",
    }


@pytest.fixture
def agent() -> AnalysisAgent:
    return AnalysisAgent()


@pytest.fixture
def valid_llm_response() -> str:
    data = {
        "business_rules": [
            {
                "name": "calculo_juros_compostos",
                "description": "Calcula montante final com juros compostos",
                "paragraph": "4000-CALCULAR-MONTANTE",
                "inputs": ["LS-PRINCIPAL", "LS-TAXA-ANUAL", "LS-PRAZO-MESES"],
                "outputs": ["LS-MONTANTE-FINAL", "LS-JUROS-TOTAL"],
                "calculations": "M = P * (1 + i)^n",
                "risks": ["COMP-3 requer BigDecimal em Java", "precisão de 6 casas decimais"],
                "cobol_specifics": "PIC 9(13)V9(02) COMP-3",
            }
        ],
        "bdd_specs": [
            "Feature: Cálculo de Juros Compostos\n  Scenario: Cálculo básico\n    Given um principal de 1000.00\n    When taxa anual de 12% e prazo de 12 meses\n    Then montante final deve ser 1126.83"
        ],
        "dependencies": [],
        "data_flow": {
            "inputs": ["LS-PRINCIPAL", "LS-TAXA-ANUAL", "LS-PRAZO-MESES"],
            "outputs": ["LS-MONTANTE-FINAL", "LS-JUROS-TOTAL", "LS-PARCELA-MENSAL"],
            "calculated": ["WS-TAXA-MENSAL", "WS-FATOR-ACUM"],
        },
        "migration_risks": ["Uso de COMP-3", "Cálculo por loop PERFORM"],
    }
    return f"```json\n{json.dumps(data)}\n```"


class TestAnalysisAgent:
    def test_build_messages_includes_cobol_source(self, agent, sample_state):
        messages = agent.build_messages(sample_state)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "CALCJURO" in messages[0]["content"]
        assert "IDENTIFICATION DIVISION" in messages[0]["content"]

    def test_build_messages_includes_jcl(self, agent, sample_state):
        messages = agent.build_messages(sample_state)
        assert "CALCJURO JOB" in messages[0]["content"]

    def test_parse_response_extracts_business_rules(self, agent, sample_state, valid_llm_response):
        result = agent.parse_response(valid_llm_response, sample_state)

        assert len(result["business_rules"]) == 1
        rule = result["business_rules"][0]
        assert rule["name"] == "calculo_juros_compostos"
        assert "COMP-3" in rule["risks"][0]

    def test_parse_response_extracts_bdd_specs(self, agent, sample_state, valid_llm_response):
        result = agent.parse_response(valid_llm_response, sample_state)

        assert len(result["bdd_specs"]) == 1
        assert "Feature:" in result["bdd_specs"][0]
        assert "Scenario:" in result["bdd_specs"][0]

    def test_parse_response_handles_invalid_json(self, agent, sample_state):
        result = agent.parse_response("resposta sem JSON válido", sample_state)

        assert result["business_rules"] == []
        assert result["bdd_specs"] == []
        assert len(result["errors"]) > 0
        assert "AnalysisAgent" in result["errors"][0]

    def test_run_populates_state_via_llm(self, agent, sample_state, valid_llm_response):
        with patch.object(agent, "_call_llm", return_value=valid_llm_response):
            result = agent.run(sample_state)

        assert result["business_rules"]
        assert result["bdd_specs"]
        assert result["errors"] == []

    def test_run_handles_llm_error_gracefully(self, agent, sample_state):
        with patch.object(agent, "_call_llm", side_effect=Exception("API timeout")):
            result = agent.run(sample_state)

        assert len(result["errors"]) > 0
        assert "AnalysisAgent" in result["errors"][0]
        assert result["module_name"] == "CALCJURO"

    def test_system_prompt_is_not_empty(self, agent):
        prompt = agent.get_system_prompt()
        assert len(prompt) > 100
        assert "COBOL" in prompt

    def test_extract_json_from_fence(self, agent):
        text = '```json\n{"key": "value"}\n```'
        result = agent.extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_raw(self, agent):
        text = 'Aqui está o resultado: {"key": 42}'
        result = agent.extract_json(text)
        assert result == {"key": 42}

    def test_extract_json_raises_on_no_json(self, agent):
        with pytest.raises(ValueError, match="Nenhum JSON"):
            agent.extract_json("texto sem json algum")
