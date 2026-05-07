"""Agente responsável por converter COBOL em Java/Spring Boot e abrir Pull Request."""
from __future__ import annotations

import structlog

from agents.base_agent import BaseAgent
from orchestrator.state import MigrationState
from prompts.development_prompt import DEVELOPMENT_SYSTEM_PROMPT
from tools.github_tool import create_pull_request

logger = structlog.get_logger(__name__)


class DevelopmentAgent(BaseAgent):
    """Converte código COBOL em Java 17 + Spring Boot 3 e abre PR no GitHub.

    Utiliza as regras de negócio extraídas pelo AnalysisAgent como contrato.
    Popula `generated_code` e `pr_url` no estado compartilhado.
    """

    def get_system_prompt(self) -> str:
        return DEVELOPMENT_SYSTEM_PROMPT

    def build_messages(self, state: MigrationState) -> list[dict]:
        """Constrói prompt com regras de negócio e contexto de erros anteriores."""
        rules_json = "\n".join(
            f"  - {r.get('name')}: {r.get('description')} | cálculos: {r.get('calculations')}"
            for r in (state.get("business_rules") or [])
        )
        bdd_specs = "\n\n".join(state.get("bdd_specs") or [])

        retry_context = ""
        if state.get("retry_count", 0) > 0 and state.get("test_results"):
            results = state["test_results"]
            deltas = results.get("parity_delta", [])
            retry_context = f"""

ATENÇÃO - Esta é a tentativa {state['retry_count']} de desenvolvimento.
Os testes anteriores falharam com os seguintes problemas:
- Cobertura obtida: {results.get('coverage', 0):.1f}% (mínimo: 80%)
- Divergências de paridade: {len(deltas)} campos diferentes
- Detalhes das divergências: {deltas[:5]}

Corrija especificamente esses problemas no código gerado.
"""

        user_content = f"""Converta o módulo COBOL '{state.get('module_name')}' para Java 17 + Spring Boot 3.

REGRAS DE NEGÓCIO:
{rules_json}

SPECS BDD (contrato a ser respeitado):
{bdd_specs}

CÓDIGO COBOL ORIGINAL:
```cobol
{state.get('cobol_source', '')}
```
{retry_context}

Retorne um JSON com:
{{
  "files": {{
    "src/main/java/com/migration/{state.get('module_name', 'Module').lower()}/controller/{state.get('module_name', 'Module')}Controller.java": "conteúdo do arquivo",
    "src/main/java/com/migration/{state.get('module_name', 'Module').lower()}/service/{state.get('module_name', 'Module')}Service.java": "conteúdo do arquivo",
    "src/main/java/com/migration/{state.get('module_name', 'Module').lower()}/dto/{state.get('module_name', 'Module')}RequestDTO.java": "conteúdo do arquivo",
    "src/main/java/com/migration/{state.get('module_name', 'Module').lower()}/dto/{state.get('module_name', 'Module')}ResponseDTO.java": "conteúdo do arquivo",
    "pom.xml": "conteúdo do pom.xml com dependências"
  }},
  "pr_title": "feat: migra {state.get('module_name')} COBOL para Java/Spring Boot",
  "pr_description": "descrição detalhada do PR em markdown",
  "branch_name": "feature/migrate-{state.get('module_name', 'module').lower()}",
  "artifact_version": "1.0.0-SNAPSHOT"
}}"""
        return [{"role": "user", "content": user_content}]

    def parse_response(self, response_text: str, state: MigrationState) -> MigrationState:
        """Extrai código gerado, abre PR e atualiza estado."""
        try:
            data = self.extract_json(response_text)
            generated_files: dict[str, str] = data.get("files", {})

            pr_url = ""
            try:
                pr_url = create_pull_request(
                    title=data.get("pr_title", f"Migração {state.get('module_name')}"),
                    body=data.get("pr_description", ""),
                    branch=data.get("branch_name", f"feature/migrate-{state.get('module_name', '').lower()}"),
                    files=generated_files,
                )
                logger.info("pr_created", url=pr_url, module=state.get("module_name"))
            except Exception as exc:
                logger.warning("pr_creation_failed", error=str(exc))
                errors = list(state.get("errors") or [])
                errors.append(f"[DevelopmentAgent] Falha ao criar PR: {exc}")
                return {**state, "errors": errors, "generated_code": generated_files}

            return {
                **state,
                "generated_code": generated_files,
                "pr_url": pr_url,
                "artifact_version": data.get("artifact_version", "1.0.0-SNAPSHOT"),
            }
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("development_parse_error", error=str(exc))
            errors = list(state.get("errors") or [])
            errors.append(f"[DevelopmentAgent] Falha ao parsear código gerado: {exc}")
            return {**state, "errors": errors}
