"""Gerenciamento de estado ativo de execuções via Azure Cache for Redis."""
from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any

import redis
import structlog

from orchestrator.state import MigrationState

logger = structlog.get_logger(__name__)

STATE_TTL_HOURS = 24


class RedisStateManager:
    """Persiste e recupera o estado de execuções em andamento no Redis.

    Usa TTL de 24 horas para garantir que estados orphãos sejam limpos automaticamente.
    Ideal para retomada de execuções interrompidas (fault tolerance).
    """

    def __init__(self) -> None:
        connection_string = os.environ["REDIS_CONNECTION_STRING"]
        self._client = redis.from_url(connection_string, decode_responses=True)

    def _key(self, execution_id: str) -> str:
        return f"migration:state:{execution_id}"

    def save(self, state: MigrationState) -> None:
        """Salva ou atualiza o estado de uma execução no Redis.

        Args:
            state: Estado atual da migração. Deve conter 'execution_id'.
        """
        execution_id = state.get("execution_id", "")
        if not execution_id:
            logger.warning("redis_save_skipped", reason="execution_id vazio")
            return

        key = self._key(execution_id)
        serialized = json.dumps(state, default=str)
        self._client.setex(key, timedelta(hours=STATE_TTL_HOURS), serialized)
        logger.debug("redis_state_saved", execution_id=execution_id, module=state.get("module_name"))

    def load(self, execution_id: str) -> MigrationState | None:
        """Carrega o estado de uma execução pelo ID.

        Args:
            execution_id: ID único da execução.

        Returns:
            MigrationState se encontrado, None caso contrário.
        """
        key = self._key(execution_id)
        data = self._client.get(key)
        if not data:
            return None
        state: MigrationState = json.loads(data)
        logger.debug("redis_state_loaded", execution_id=execution_id)
        return state

    def delete(self, execution_id: str) -> None:
        """Remove o estado de uma execução ao final (sucesso ou falha definitiva).

        Args:
            execution_id: ID da execução a remover.
        """
        self._client.delete(self._key(execution_id))
        logger.debug("redis_state_deleted", execution_id=execution_id)

    def list_active(self) -> list[str]:
        """Lista IDs de todas as execuções ativas (com estado no Redis)."""
        keys = self._client.keys("migration:state:*")
        return [k.split(":")[-1] for k in keys]
