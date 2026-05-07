"""Agente responsável por analisar código COBOL/JCL e extrair regras de negócio."""
from __future__ import annotations

import structlog

from agents.base_agent import BaseAgent
from orchestrator.state import MigrationState
from prompts.analysis_prompt import ANALYSIS_SYSTEM_PROMPT

logger = structlog.get_logger(__name__)


class AnalysisAgent(BaseAgent):
    """Analisa código COBOL/JCL e extrai regras de negócio e specs BDD em Gherkin.

    Popula os campos `business_rules` e `bdd_specs` no estado compartilhado.
    """

    def get_system_prompt(self) -> str:
        return ANALYSIS_SYSTEM_PROMPT

    def build_messages(self, state: MigrationState) -> list[dict]:
        """Constrói prompt com o código COBOL e JCL para análise."""
        user_content = f"""Analise o seguinte programa COBOL e JCL e extraia TODAS as informações solicitadas.

NOME DO MÓDULO: {state.get('module_name', 'DESCONHECIDO')}

CÓDIGO COBOL:
```cobol
{state.get('cobol_source', '')}
```

JCL:
```jcl
{state.get('jcl_source', '')}
```

Retorne um JSON com exatamente esta estrutura:
{{
  "business_rules": [
    {{
      "name": "nome_da_regra",
      "description": "descrição em português",
      "paragraph": "nome_do_parágrafo_cobol",
      "inputs": ["campo1", "campo2"],
      "outputs": ["campo_resultado"],
      "calculations": "fórmula ou lógica descrita",
      "risks": ["risco de arredondamento", "formato de data"],
      "cobol_specifics": "uso de COMP-3, PIC, etc."
    }}
  ],
  "bdd_specs": [
    "Feature: ...
Scenario: ...\n  Given ...\n  When ...\n  Then ..."
  ],
  "dependencies": ["COPYBOOK1", "SUBPROG1"],
  "data_flow": {{
    "inputs": ["campo_entrada"],
    "outputs": ["campo_saida"],
    "calculated": ["campo_calculado"]
  }},
  "migration_risks": ["risco1", "risco2"]
}}"""
        return [{"role": "user", "content": user_content}]

    def parse_response(self, response_text: str, state: MigrationState) -> MigrationState:
        """Extrai regras de negócio e specs BDD da resposta do LLM."""
        try:
            data = self.extract_json(response_text)
            return {
                **state,
                "business_rules": data.get("business_rules", []),
                "bdd_specs": data.get("bdd_specs", []),
            }
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("analysis_parse_error", error=str(exc))
            errors = list(state.get("errors") or [])
            errors.append(f"[AnalysisAgent] Falha ao parsear resposta: {exc}")
            return {**state, "errors": errors, "business_rules": [], "bdd_specs": []}
