"""Ferramenta para acionar e monitorar pipelines no Azure DevOps."""
from __future__ import annotations

import os
import time

import requests
import structlog

logger = structlog.get_logger(__name__)

AZURE_DEVOPS_TOOL_DEFINITION = {
    "name": "azure_devops_trigger_pipeline",
    "description": "Aciona uma pipeline do Azure DevOps e monitora até a conclusão, retornando logs em caso de falha.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pipeline_name": {"type": "string", "description": "Nome da pipeline no Azure DevOps"},
            "parameters": {
                "type": "object",
                "description": "Parâmetros para a pipeline",
                "additionalProperties": {"type": "string"},
            },
            "timeout_minutes": {
                "type": "integer",
                "description": "Timeout em minutos (padrão: 20)",
                "default": 20,
            },
        },
        "required": ["pipeline_name"],
    },
}


def _get_headers() -> dict[str, str]:
    """Retorna headers de autenticação para a API do Azure DevOps."""
    import base64
    pat = os.environ["AZURE_DEVOPS_PAT"]
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _base_url() -> str:
    org = os.environ["AZURE_DEVOPS_ORG"]
    project = os.environ["AZURE_DEVOPS_PROJECT"]
    return f"{org}/{project}/_apis"


def _get_pipeline_id(pipeline_name: str, headers: dict) -> int:
    """Obtém o ID numérico da pipeline pelo nome."""
    url = f"{_base_url()}/pipelines?api-version=7.1"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    for pipeline in resp.json().get("value", []):
        if pipeline["name"] == pipeline_name:
            return int(pipeline["id"])
    raise ValueError(f"Pipeline '{pipeline_name}' não encontrada no projeto")


def trigger_pipeline(
    pipeline_name: str,
    parameters: dict[str, str] | None = None,
) -> str:
    """Aciona uma pipeline do Azure DevOps e retorna o ID da execução.

    Args:
        pipeline_name: Nome exato da pipeline no Azure DevOps.
        parameters: Parâmetros opcionais para a execução.

    Returns:
        ID da execução como string.
    """
    headers = _get_headers()
    pipeline_id = _get_pipeline_id(pipeline_name, headers)

    url = f"{_base_url()}/pipelines/{pipeline_id}/runs?api-version=7.1"
    payload: dict = {"resources": {"repositories": {"self": {"refName": "refs/heads/main"}}}}
    if parameters:
        payload["templateParameters"] = parameters

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()

    run_id = str(resp.json()["id"])
    logger.info("pipeline_triggered", pipeline=pipeline_name, run_id=run_id)
    return run_id


def wait_for_pipeline(
    run_id: str,
    timeout_minutes: int | None = None,
    poll_interval_seconds: int = 30,
) -> bool:
    """Monitora uma execução de pipeline até conclusão ou timeout.

    Args:
        run_id: ID da execução retornado por `trigger_pipeline`.
        timeout_minutes: Timeout em minutos (padrão: PIPELINE_TIMEOUT_MINUTES do .env).
        poll_interval_seconds: Intervalo de polling em segundos.

    Returns:
        True se a pipeline completou com sucesso, False em caso de falha ou timeout.
    """
    timeout_min = timeout_minutes or int(os.getenv("PIPELINE_TIMEOUT_MINUTES", "20"))
    timeout_sec = timeout_min * 60
    headers = _get_headers()

    start = time.time()
    while time.time() - start < timeout_sec:
        url = f"{_base_url()}/pipelines/runs/{run_id}?api-version=7.1"
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()

        state = resp.json().get("state", "")
        result = resp.json().get("result", "")

        logger.debug("pipeline_status", run_id=run_id, state=state, result=result)

        if state == "completed":
            success = result == "succeeded"
            logger.info("pipeline_completed", run_id=run_id, success=success, result=result)
            return success

        time.sleep(poll_interval_seconds)

    logger.error("pipeline_timeout", run_id=run_id, timeout_minutes=timeout_min)
    return False
