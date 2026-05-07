"""Agente responsável por configurar observabilidade no Azure Monitor após deploy."""
from __future__ import annotations

import structlog

from agents.base_agent import BaseAgent
from orchestrator.state import MigrationState
from prompts.observability_prompt import OBSERVABILITY_SYSTEM_PROMPT
from tools.azure_monitor_tool import create_dashboard, create_alert

logger = structlog.get_logger(__name__)


class ObservabilityAgent(BaseAgent):
    """Cria dashboards, alertas e workbooks no Azure Monitor.

    Popula `observability_config` no estado com referências aos recursos criados.
    """

    def get_system_prompt(self) -> str:
        return OBSERVABILITY_SYSTEM_PROMPT

    def build_messages(self, state: MigrationState) -> list[dict]:
        """Constrói prompt com informações do serviço para configurar observabilidade."""
        parity_delta = (state.get("test_results") or {}).get("parity_delta", [])
        user_content = f"""Configure a observabilidade completa para o serviço {state.get('module_name')} recém-implantado.

METADADOS DO SERVIÇO:
- Módulo: {state.get('module_name')}
- Imagem ACR: {state.get('acr_image_tag')}
- PR: {state.get('pr_url')}
- Divergências de paridade: {len(parity_delta)}

Retorne um JSON com:
{{
  "dashboard_name": "Migration-{state.get('module_name')}-Dashboard",
  "alerts": [
    {{
      "name": "nome-do-alerta",
      "description": "descrição",
      "severity": 1,
      "metric": "nome_da_metrica",
      "threshold": 0.01,
      "operator": "GreaterThan",
      "window_minutes": 5
    }}
  ],
  "workbook_name": "Migration-Progress",
  "custom_metrics": [
    {{"name": "parity_delta_count", "value": {len(parity_delta)}}}
  ]
}}"""
        return [{"role": "user", "content": user_content}]

    def parse_response(self, response_text: str, state: MigrationState) -> MigrationState:
        """Cria recursos de observabilidade no Azure Monitor e atualiza estado."""
        try:
            data = self.extract_json(response_text)

            dashboard_id = ""
            try:
                dashboard_id = create_dashboard(name=data.get("dashboard_name", "Migration-Dashboard"))
                logger.info("dashboard_created", id=dashboard_id, module=state.get("module_name"))
            except Exception as exc:
                logger.warning("dashboard_creation_failed", error=str(exc))

            alert_ids: list[str] = []
            for alert_config in data.get("alerts", []):
                try:
                    alert_id = create_alert(
                        name=alert_config["name"],
                        severity=alert_config.get("severity", 2),
                        metric=alert_config.get("metric", ""),
                        threshold=alert_config.get("threshold", 1.0),
                    )
                    alert_ids.append(alert_id)
                except Exception as exc:
                    logger.warning("alert_creation_failed", alert=alert_config.get("name"), error=str(exc))

            observability_config = {
                **(state.get("observability_config") or {}),
                "dashboard_id": dashboard_id,
                "alert_ids": alert_ids,
                "workbook_name": data.get("workbook_name", ""),
                "custom_metrics": data.get("custom_metrics", []),
            }

            return {**state, "observability_config": observability_config}
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("observability_parse_error", error=str(exc))
            errors = list(state.get("errors") or [])
            errors.append(f"[ObservabilityAgent] Falha na configuração de observabilidade: {exc}")
            return {**state, "errors": errors}
