"""Ferramenta para chamar o endpoint shadow do mainframe (parity testing)."""
from __future__ import annotations

import os

import httpx
import structlog

logger = structlog.get_logger(__name__)

MAINFRAME_SHADOW_TOOL_DEFINITION = {
    "name": "mainframe_shadow_call",
    "description": "Envia um input ao endpoint shadow do mainframe e retorna o output para comparação de paridade.",
    "input_schema": {
        "type": "object",
        "properties": {
            "module_name": {"type": "string", "description": "Nome do módulo COBOL a chamar"},
            "input_data": {
                "type": "object",
                "description": "Dados de entrada no formato esperado pelo módulo",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Timeout em segundos (padrão: 30)",
                "default": 30,
            },
        },
        "required": ["module_name", "input_data"],
    },
}


def call_shadow(
    module_name: str,
    input_data: dict,
    timeout_seconds: int = 30,
) -> dict:
    """Chama o endpoint shadow do mainframe com o input fornecido.

    O endpoint shadow executa o programa COBOL original e retorna o output
    para comparação com o serviço Java migrado.

    Args:
        module_name: Nome do módulo COBOL (ex: 'CALCJURO').
        input_data: Dict com os dados de entrada.
        timeout_seconds: Timeout em segundos.

    Returns:
        Dict com o output do mainframe, campo a campo.
    """
    base_url = os.environ["MAINFRAME_SHADOW_ENDPOINT"]
    api_key = os.environ["MAINFRAME_SHADOW_API_KEY"]

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {"module": module_name, "input": input_data}

    with httpx.Client(timeout=timeout_seconds) as client:
        resp = client.post(f"{base_url}/execute", json=payload, headers=headers)
        resp.raise_for_status()

    result: dict = resp.json()
    logger.info(
        "shadow_call_success",
        module=module_name,
        input_keys=list(input_data.keys()),
        output_keys=list(result.keys()),
    )
    return result
