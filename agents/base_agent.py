"""Classe base abstrata para todos os agentes de migração."""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import structlog
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from orchestrator.state import MigrationState

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """Base para todos os agentes, com retry automático, logging JSON e timeout.

    Subclasses devem implementar `build_messages` e `parse_response`.
    Opcionalmente, sobrescrever `get_system_prompt` para customizar o comportamento do LLM.
    """

    def __init__(self, timeout_seconds: int = 300) -> None:
        self.client = Anthropic()
        self.model = "claude-sonnet-4-6"
        self.max_tokens = 8192
        self.timeout_seconds = timeout_seconds

    def get_system_prompt(self) -> str:
        """Retorna o system prompt padrão. Subclasses devem sobrescrever."""
        return (
            "Você é um engenheiro sênior especialista em migração de sistemas COBOL/Mainframe "
            "para arquiteturas modernas em cloud Azure. Responda sempre em português do Brasil. "
            "Quando solicitado a retornar JSON, retorne APENAS o JSON válido sem markdown extra."
        )

    @abstractmethod
    def build_messages(self, state: MigrationState) -> list[dict]:
        """Constrói a lista de mensagens para enviar ao LLM.

        Args:
            state: Estado atual da migração com todos os dados acumulados.

        Returns:
            Lista de dicts no formato {role: str, content: str}.
        """
        ...

    @abstractmethod
    def parse_response(self, response_text: str, state: MigrationState) -> MigrationState:
        """Extrai dados estruturados da resposta do LLM e atualiza o estado.

        Args:
            response_text: Texto bruto retornado pelo LLM.
            state: Estado atual da migração.

        Returns:
            Novo estado com os campos atualizados pelo agente.
        """
        ...

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_llm(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
    ) -> str:
        """Chama a API da Anthropic com retry automático em caso de falha transitória."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)
        return response.content[0].text

    def run(self, state: MigrationState) -> MigrationState:
        """Executa o agente: constrói mensagens, chama LLM e atualiza estado.

        Em caso de erro, popula `state['errors']` sem quebrar o grafo.
        """
        agent_name = self.__class__.__name__
        start = time.time()

        try:
            messages = self.build_messages(state)
            system = self.get_system_prompt()

            logger.info(
                "agent_calling_llm",
                agent=agent_name,
                module=state.get("module_name"),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            response_text = self._call_llm(messages, system=system)
            elapsed = round(time.time() - start, 2)

            logger.info(
                "agent_completed",
                agent=agent_name,
                module=state.get("module_name"),
                duration_seconds=elapsed,
            )

            return self.parse_response(response_text, state)

        except Exception as exc:
            elapsed = round(time.time() - start, 2)
            logger.error(
                "agent_error",
                agent=agent_name,
                module=state.get("module_name"),
                error=str(exc),
                duration_seconds=elapsed,
            )
            errors = list(state.get("errors") or [])
            errors.append(f"[{agent_name}] {exc}")
            return {**state, "errors": errors}

    @staticmethod
    def extract_json(text: str) -> dict | list:
        """Extrai o primeiro bloco JSON válido encontrado na resposta do LLM."""
        fence_start = text.find("```json")
        if fence_start != -1:
            content_start = fence_start + 7
            content_end = text.find("```", content_start)
            if content_end != -1:
                return json.loads(text[content_start:content_end].strip())

        for open_ch, close_ch in [("{" , "}"), ("[", "]")]:
            idx = text.find(open_ch)
            if idx != -1:
                end_idx = text.rfind(close_ch) + 1
                if end_idx > idx:
                    return json.loads(text[idx:end_idx])

        raise ValueError(f"Nenhum JSON encontrado na resposta do LLM: {text[:200]}")
