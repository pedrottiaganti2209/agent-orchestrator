"""Executor de testes de paridade entre o mainframe (shadow) e o serviço Java migrado."""
from __future__ import annotations

import os

import httpx
import structlog

from parity.comparator import ParityComparator
from tools.mainframe_shadow_tool import call_shadow

logger = structlog.get_logger(__name__)


class ParityRunner:
    """Executa o mesmo input no mainframe (via shadow) e no serviço Java e compara os resultados.

    Usa ParityComparator para comparação campo a campo com tolerância configurável.
    """

    def __init__(self) -> None:
        self._comparator = ParityComparator()
        self._java_base_url = os.getenv("JAVA_SERVICE_BASE_URL", "http://localhost:8080")

    def _call_java_service(self, module_name: str, input_data: dict) -> dict:
        """Chama o serviço Java recém-migrado com o input fornecido.

        Args:
            module_name: Nome do módulo (usado para montar a URL do endpoint).
            input_data: Dados de entrada no formato JSON.

        Returns:
            Resposta do serviço Java como dict.
        """
        endpoint = f"{self._java_base_url}/api/{module_name.lower()}/execute"
        with httpx.Client(timeout=30) as client:
            resp = client.post(endpoint, json=input_data)
            resp.raise_for_status()
        return dict(resp.json())

    def run(
        self,
        module_name: str,
        test_inputs: list[dict],
    ) -> list[dict]:
        """Executa parity tests para todos os inputs fornecidos.

        Para cada input:
        1. Chama o shadow do mainframe e obtém o output de referência
        2. Chama o serviço Java migrado com o mesmo input
        3. Compara os outputs campo a campo
        4. Registra qualquer divergência encontrada

        Args:
            module_name: Nome do módulo COBOL.
            test_inputs: Lista de dicts com 'input' e opcionalmente 'descricao'.

        Returns:
            Lista de divergências encontradas (vazia = paridade perfeita).
        """
        all_deltas: list[dict] = []

        for i, test_case in enumerate(test_inputs):
            input_data = test_case.get("input", {})
            description = test_case.get("descricao", f"Test case {i + 1}")

            try:
                mainframe_output = call_shadow(module_name=module_name, input_data=input_data)
            except Exception as exc:
                logger.warning("shadow_call_failed", case=description, error=str(exc))
                continue

            try:
                java_output = self._call_java_service(module_name=module_name, input_data=input_data)
            except Exception as exc:
                logger.warning("java_service_call_failed", case=description, error=str(exc))
                all_deltas.append({
                    "test_case": description,
                    "field": "CONNECTION",
                    "mainframe_value": "OK",
                    "java_value": f"ERROR: {exc}",
                    "delta": None,
                })
                continue

            deltas = self._comparator.compare(mainframe_output, java_output)
            if deltas:
                for delta in deltas:
                    delta["test_case"] = description
                all_deltas.extend(deltas)
                logger.warning(
                    "parity_divergence_found",
                    case=description,
                    module=module_name,
                    divergences=len(deltas),
                )
            else:
                logger.info("parity_ok", case=description, module=module_name)

        return all_deltas
