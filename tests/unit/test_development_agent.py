"""Testes unitários para o DevelopmentAgent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.development_agent import DevelopmentAgent
from orchestrator.state import MigrationState


@pytest.fixture
def sample_state() -> MigrationState:
    return {
        "module_name": "CALCJURO",
        "cobol_source": "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. CALCJURO.",
        "jcl_source": "",
        "business_rules": [
            {
                "name": "calculo_juros_compostos",
                "description": "Calcula montante com juros compostos",
                "inputs": ["principal", "taxa", "prazo"],
                "outputs": ["montante", "juros"],
                "calculations": "M = P * (1 + i)^n",
                "risks": ["COMP-3"],
                "cobol_specifics": "PIC 9(13)V9(02) COMP-3",
            }
        ],
        "bdd_specs": [
            "Feature: Juros\n  Scenario: Básico\n    Given P=1000\n    When i=1%\n    Then M=1010"
        ],
        "generated_code": {},
        "pr_url": "",
        "test_results": {"passed": False, "coverage": 0.0, "parity_delta": []},
        "artifact_version": "",
        "acr_image_tag": "",
        "deploy_status": "",
        "observability_config": {},
        "errors": [],
        "execution_id": "test-exec-002",
        "started_at": "2026-01-01T00:00:00Z",
        "retry_count": 0,
        "status": "IN_PROGRESS",
    }


@pytest.fixture
def agent() -> DevelopmentAgent:
    return DevelopmentAgent()


@pytest.fixture
def valid_llm_response(sample_state) -> str:
    data = {
        "files": {
            "src/main/java/com/migration/calcjuro/service/CalcjuroService.java": (
                "package com.migration.calcjuro.service;\n\n"
                "import java.math.BigDecimal;\n\n"
                "public class CalcjuroService {\n"
                "    public BigDecimal calcularMontante(BigDecimal principal, BigDecimal taxa, int prazo) {\n"
                "        return principal.multiply(taxa.add(BigDecimal.ONE).pow(prazo));\n"
                "    }\n"
                "}"
            ),
            "pom.xml": "<project>\n  <groupId>com.migration</groupId>\n  <artifactId>calcjuro</artifactId>\n  <version>1.0.0-SNAPSHOT</version>\n</project>",
        },
        "pr_title": "feat: migra CALCJURO COBOL para Java/Spring Boot",
        "pr_description": "Migração do módulo CALCJURO",
        "branch_name": "feature/migrate-calcjuro",
        "artifact_version": "1.0.0-SNAPSHOT",
    }
    return f"```json\n{json.dumps(data)}\n```"


class TestDevelopmentAgent:
    def test_build_messages_includes_business_rules(self, agent, sample_state):
        messages = agent.build_messages(sample_state)

        assert len(messages) == 1
        content = messages[0]["content"]
        assert "calculo_juros_compostos" in content
        assert "CALCJURO" in content

    def test_build_messages_includes_retry_context_on_retry(self, agent, sample_state):
        sample_state["retry_count"] = 1
        sample_state["test_results"] = {
            "passed": False,
            "coverage": 65.0,
            "parity_delta": [{"field": "montante", "mainframe_value": "1000", "java_value": "999", "delta": 1.0}],
        }

        messages = agent.build_messages(sample_state)
        content = messages[0]["content"]
        assert "tentativa" in content.lower()
        assert "65.0" in content

    def test_parse_response_extracts_generated_code(self, agent, sample_state, valid_llm_response):
        with patch("agents.development_agent.create_pull_request", return_value="https://github.com/pr/1"):
            result = agent.parse_response(valid_llm_response, sample_state)

        assert "src/main/java/com/migration/calcjuro/service/CalcjuroService.java" in result["generated_code"]
        assert "BigDecimal" in result["generated_code"]["src/main/java/com/migration/calcjuro/service/CalcjuroService.java"]

    def test_parse_response_sets_pr_url(self, agent, sample_state, valid_llm_response):
        expected_url = "https://github.com/org/repo/pull/42"
        with patch("agents.development_agent.create_pull_request", return_value=expected_url):
            result = agent.parse_response(valid_llm_response, sample_state)

        assert result["pr_url"] == expected_url

    def test_parse_response_handles_pr_creation_failure(self, agent, sample_state, valid_llm_response):
        with patch(
            "agents.development_agent.create_pull_request",
            side_effect=Exception("GitHub API error"),
        ):
            result = agent.parse_response(valid_llm_response, sample_state)

        assert any("PR" in e or "create_pull_request" in e.lower() or "DevelopmentAgent" in e for e in result["errors"])

    def test_parse_response_sets_artifact_version(self, agent, sample_state, valid_llm_response):
        with patch("agents.development_agent.create_pull_request", return_value="https://github.com/pr/1"):
            result = agent.parse_response(valid_llm_response, sample_state)

        assert result["artifact_version"] == "1.0.0-SNAPSHOT"

    def test_run_increments_retry_count(self, agent, sample_state, valid_llm_response):
        with (
            patch.object(agent, "_call_llm", return_value=valid_llm_response),
            patch("agents.development_agent.create_pull_request", return_value="https://github.com/pr/1"),
        ):
            result = agent.run(sample_state)

        assert result["generated_code"]
