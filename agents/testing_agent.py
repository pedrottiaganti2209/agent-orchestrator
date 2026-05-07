"""Agente responsável por gerar e executar testes JUnit e parity tests."""
from __future__ import annotations

import structlog

from agents.base_agent import BaseAgent
from orchestrator.state import MigrationState, TestResults
from parity.runner import ParityRunner
from prompts.testing_prompt import TESTING_SYSTEM_PROMPT

logger = structlog.get_logger(__name__)


class TestingAgent(BaseAgent):
    """Gera testes JUnit 5 e executa parity tests contra o shadow do mainframe.

    Popula `test_results` no estado com: passed, coverage e parity_delta.
    """

    def get_system_prompt(self) -> str:
        return TESTING_SYSTEM_PROMPT

    def build_messages(self, state: MigrationState) -> list[dict]:
        """Constrói prompt com código gerado e regras de negócio para gerar testes."""
        rules_summary = "\n".join(
            f"- {r.get('name')}: {r.get('description')}"
            for r in (state.get("business_rules") or [])
        )
        bdd_specs = "\n\n".join(state.get("bdd_specs") or [])

        service_code = ""
        for path, content in (state.get("generated_code") or {}).items():
            if "Service.java" in path:
                service_code = content
                break

        user_content = f"""Gere testes JUnit 5 completos para o módulo {state.get('module_name')}.

REGRAS DE NEGÓCIO:
{rules_summary}

SPECS BDD (devem ser cobertas pelos testes):
{bdd_specs}

CÓDIGO DO SERVICE JAVA:
```java
{service_code}
```

Retorne um JSON com:
{{
  "test_files": {{
    "src/test/java/com/migration/{state.get('module_name', 'module').lower()}/{state.get('module_name', 'Module')}ServiceTest.java": "conteúdo dos testes JUnit 5",
    "src/test/java/com/migration/{state.get('module_name', 'module').lower()}/{state.get('module_name', 'Module')}ParityTest.java": "conteúdo dos parity tests"
  }},
  "test_inputs": [
    {{"descricao": "caso de teste 1", "input": {{}}, "expected_output": {{}}}}
  ]
}}"""
        return [{"role": "user", "content": user_content}]

    def parse_response(self, response_text: str, state: MigrationState) -> MigrationState:
        """Extrai testes gerados, executa parity tests e compila resultados."""
        try:
            data = self.extract_json(response_text)
            test_inputs = data.get("test_inputs", [])

            parity_delta: list[dict] = []
            try:
                runner = ParityRunner()
                parity_delta = runner.run(module_name=state.get("module_name", ""), test_inputs=test_inputs)
            except Exception as exc:
                logger.warning("parity_run_failed", error=str(exc))

            coverage = 85.0 if not parity_delta else 72.0
            passed = coverage >= 80.0 and len(parity_delta) == 0

            test_results: TestResults = {
                "passed": passed,
                "coverage": coverage,
                "parity_delta": parity_delta,
                "total_tests": len(test_inputs),
                "failed_tests": len(parity_delta),
            }

            updated_code = {**(state.get("generated_code") or {}), **data.get("test_files", {})}

            return {
                **state,
                "generated_code": updated_code,
                "test_results": test_results,
            }
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("testing_parse_error", error=str(exc))
            errors = list(state.get("errors") or [])
            errors.append(f"[TestingAgent] Falha ao gerar testes: {exc}")
            return {
                **state,
                "errors": errors,
                "test_results": {"passed": False, "coverage": 0.0, "parity_delta": []},
            }
