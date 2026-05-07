"""Ferramenta para verificação do quality gate no SonarQube."""
from __future__ import annotations

import os
import time

import requests
import structlog

logger = structlog.get_logger(__name__)

SONARQUBE_TOOL_DEFINITION = {
    "name": "sonarqube_check_quality_gate",
    "description": "Verifica o status do quality gate de um projeto no SonarQube após análise.",
    "input_schema": {
        "type": "object",
        "properties": {
            "project_key": {"type": "string", "description": "Chave única do projeto no SonarQube"},
            "branch": {"type": "string", "description": "Branch a verificar (padrão: main)"},
        },
        "required": ["project_key"],
    },
}


def _get_auth() -> tuple[str, str]:
    return (os.environ["SONARQUBE_TOKEN"], "")


def check_quality_gate(project_key: str | None = None, branch: str = "main") -> dict:
    """Verifica o status do quality gate do projeto no SonarQube.

    Args:
        project_key: Chave do projeto (padrão: SONARQUBE_PROJECT_KEY do .env).
        branch: Branch a verificar.

    Returns:
        Dict com keys: 'passed' (bool), 'status' (str), 'conditions' (list).
    """
    base_url = os.environ["SONARQUBE_URL"]
    key = project_key or os.getenv("SONARQUBE_PROJECT_KEY", "mainframe-migration")
    auth = _get_auth()

    url = f"{base_url}/api/qualitygates/project_status"
    params = {"projectKey": key, "branch": branch}

    resp = requests.get(url, params=params, auth=auth, timeout=30)
    resp.raise_for_status()

    data = resp.json().get("projectStatus", {})
    status = data.get("status", "ERROR")
    passed = status == "OK"

    logger.info("quality_gate_checked", project=key, status=status, passed=passed)

    return {
        "passed": passed,
        "status": status,
        "conditions": data.get("conditions", []),
    }
