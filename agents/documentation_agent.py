"""Agente responsável por gerar documentação técnica da migração."""
from __future__ import annotations

import structlog

from agents.base_agent import BaseAgent
from orchestrator.state import MigrationState
from prompts.observability_prompt import OBSERVABILITY_SYSTEM_PROMPT
from tools.confluence_tool import publish_page

logger = structlog.get_logger(__name__)

DOCUMENTATION_SYSTEM_PROMPT = """Você é um arquiteto de software especialista em documentação técnica de migrações de mainframe.
Gere documentação clara, precisa e útil para a equipe de engenharia.
Sempre use português do Brasil. Siga o padrão ADR (Architecture Decision Record) para decisões arquiteturais."""


class DocumentationAgent(BaseAgent):
    """Gera ADR, README técnico e publica páginas no Confluence.

    Opera em paralelo ao DevelopmentAgent após o AnalysisAgent concluir.
    """

    def get_system_prompt(self) -> str:
        return DOCUMENTATION_SYSTEM_PROMPT

    def build_messages(self, state: MigrationState) -> list[dict]:
        """Constrói prompt com regras de negócio para gerar documentação."""
        rules_summary = "\n".join(
            f"- {r.get('name')}: {r.get('description')}"
            for r in (state.get("business_rules") or [])
        )
        bdd_summary = "\n\n".join(state.get("bdd_specs") or [])

        user_content = f"""Gere a documentação técnica completa para a migração do módulo {state.get('module_name')}.

REGRAS DE NEGÓCIO IDENTIFICADAS:
{rules_summary}

SPECS BDD:
{bdd_summary}

Retorne um JSON com:
{{
  "adr": "conteúdo completo do ADR em markdown",
  "readme": "README técnico do serviço migrado em markdown",
  "confluence_page": {{
    "title": "título da página",
    "content": "conteúdo em formato Confluence wiki markup"
  }}
}}"""
        return [{"role": "user", "content": user_content}]

    def parse_response(self, response_text: str, state: MigrationState) -> MigrationState:
        """Extrai documentação gerada e publica no Confluence."""
        try:
            data = self.extract_json(response_text)

            confluence_data = data.get("confluence_page", {})
            if confluence_data:
                try:
                    publish_page(
                        title=confluence_data.get("title", f"Migração {state.get('module_name')}"),
                        content=confluence_data.get("content", ""),
                    )
                    logger.info("confluence_page_published", module=state.get("module_name"))
                except Exception as exc:
                    logger.warning("confluence_publish_failed", error=str(exc))

            return {
                **state,
                "observability_config": {
                    **(state.get("observability_config") or {}),
                    "documentation": {
                        "adr": data.get("adr", ""),
                        "readme": data.get("readme", ""),
                    },
                },
            }
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("documentation_parse_error", error=str(exc))
            errors = list(state.get("errors") or [])
            errors.append(f"[DocumentationAgent] Falha ao gerar documentação: {exc}")
            return {**state, "errors": errors}
