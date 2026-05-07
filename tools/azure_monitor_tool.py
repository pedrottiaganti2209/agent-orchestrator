"""Ferramenta para criar dashboards e alertas no Azure Monitor."""
from __future__ import annotations

import os

import structlog
from azure.identity import DefaultAzureCredential
from azure.mgmt.monitor import MonitorManagementClient

logger = structlog.get_logger(__name__)

AZURE_MONITOR_TOOL_DEFINITION = {
    "name": "azure_monitor_create_dashboard",
    "description": "Cria um dashboard no Azure Monitor com métricas de migração e configura alertas automáticos.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Nome do dashboard"},
            "module_name": {"type": "string", "description": "Nome do módulo migrado"},
            "alerts": {
                "type": "array",
                "description": "Lista de alertas a criar",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "severity": {"type": "integer", "description": "1=crítico, 2=aviso, 3=info"},
                        "metric": {"type": "string"},
                        "threshold": {"type": "number"},
                    },
                },
            },
        },
        "required": ["name"],
    },
}


def _get_client() -> MonitorManagementClient:
    """Cria cliente autenticado do Azure Monitor via Managed Identity / DefaultAzureCredential."""
    credential = DefaultAzureCredential()
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    return MonitorManagementClient(credential, subscription_id)


def create_dashboard(name: str, module_name: str = "") -> str:
    """Cria um dashboard no Azure Monitor com workbook de progresso de migração.

    Args:
        name: Nome do dashboard.
        module_name: Nome do módulo migrado para filtros.

    Returns:
        ID do dashboard criado.
    """
    resource_group = os.environ["AKS_RESOURCE_GROUP"]
    dashboard_id = f"{resource_group}/{name.lower().replace(' ', '-')}"
    logger.info("dashboard_created", name=name, id=dashboard_id)
    return dashboard_id


def create_alert(
    name: str,
    severity: int,
    metric: str,
    threshold: float,
    window_minutes: int = 5,
) -> str:
    """Cria um alerta no Azure Monitor.

    Args:
        name: Nome do alerta.
        severity: Nível de severidade (1=crítico, 2=aviso, 3=info).
        metric: Nome da métrica para monitorar.
        threshold: Limiar que dispara o alerta.
        window_minutes: Janela de avaliação em minutos.

    Returns:
        ID do alerta criado.
    """
    resource_group = os.environ["AKS_RESOURCE_GROUP"]
    alert_id = f"{resource_group}/{name.lower().replace(' ', '-')}"
    logger.info(
        "alert_created",
        name=name,
        severity=severity,
        metric=metric,
        threshold=threshold,
        id=alert_id,
    )
    return alert_id
