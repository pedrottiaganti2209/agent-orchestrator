"""Lógica de roteamento condicional entre os nós do grafo LangGraph."""
from __future__ import annotations

import os

from orchestrator.state import MigrationState

MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))


def route_after_tests(state: MigrationState) -> str:
    """Determina o próximo nó após execução dos testes.

    Retorna 'packaging' se os testes passaram, 'development' para retry
    (com contexto do erro), ou 'end_failed' se excedeu o limite de tentativas.
    """
    test_results = state.get("test_results") or {}
    retry_count = state.get("retry_count", 0)

    if test_results.get("passed"):
        return "packaging"

    if retry_count >= MAX_RETRY_ATTEMPTS:
        return "end_failed"

    return "development"


def route_after_deployment(state: MigrationState) -> str:
    """Determina o próximo nó após a implantação no AKS.

    Retorna 'observability' em sucesso, 'end_failed' em falha.
    """
    if state.get("deploy_status") == "SUCCESS":
        return "observability"
    return "end_failed"
