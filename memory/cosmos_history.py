"""Persistência de histórico auditável de execuções no Azure Cosmos DB."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import structlog
from azure.cosmos import CosmosClient, PartitionKey, exceptions

from orchestrator.state import MigrationState

logger = structlog.get_logger(__name__)


class CosmosHistory:
    """Armazena histórico imutável de todas as execuções do orquestrador no Cosmos DB.

    Cada execução (sucesso ou falha) é registrada com todos os artefatos produzidos,
    permettindo auditoria, debug e análise de tendências.

    Partition key: execution_id (distribuição uniforme de dados).
    """

    def __init__(self) -> None:
        endpoint = os.environ["COSMOS_ENDPOINT"]
        key = os.environ["COSMOS_KEY"]
        db_name = os.getenv("COSMOS_DATABASE", "migration-db")
        container_name = os.getenv("COSMOS_CONTAINER", "migration-history")

        client = CosmosClient(endpoint, key)
        database = client.create_database_if_not_exists(db_name)
        self._container = database.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/execution_id"),
            offer_throughput=400,
        )

    def save_execution(self, state: MigrationState) -> str:
        """Salva o estado final de uma execução no Cosmos DB.

        O documento é enriquecido com metadados de auditoria antes de persistir.

        Args:
            state: Estado final da execução (sucesso ou falha).

        Returns:
            ID do documento criado no Cosmos DB.
        """
        execution_id = state.get("execution_id", "")
        if not execution_id:
            logger.warning("cosmos_save_skipped", reason="execution_id vazio")
            return ""

        document = {
            "id": execution_id,
            "execution_id": execution_id,
            "module_name": state.get("module_name"),
            "status": state.get("status", "UNKNOWN"),
            "started_at": state.get("started_at"),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "pr_url": state.get("pr_url"),
            "acr_image_tag": state.get("acr_image_tag"),
            "artifact_version": state.get("artifact_version"),
            "deploy_status": state.get("deploy_status"),
            "test_results": state.get("test_results"),
            "business_rules_count": len(state.get("business_rules") or []),
            "bdd_specs_count": len(state.get("bdd_specs") or []),
            "errors": state.get("errors") or [],
            "retry_count": state.get("retry_count", 0),
            "observability_config": state.get("observability_config"),
        }

        self._container.upsert_item(document)
        logger.info(
            "cosmos_execution_saved",
            execution_id=execution_id,
            module=state.get("module_name"),
            status=state.get("status"),
        )
        return execution_id

    def get_execution(self, execution_id: str) -> dict | None:
        """Recupera uma execução pelo ID.

        Args:
            execution_id: ID único da execução.

        Returns:
            Documento da execução ou None se não encontrado.
        """
        try:
            item = self._container.read_item(item=execution_id, partition_key=execution_id)
            return dict(item)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def list_executions(
        self,
        module_name: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Lista execuções com filtros opcionais.

        Args:
            module_name: Filtrar por nome do módulo.
            status: Filtrar por status ('SUCCESS', 'FAILED').
            limit: Número máximo de resultados.

        Returns:
            Lista de documentos de execução.
        """
        conditions = []
        params: list[dict] = []

        if module_name:
            conditions.append("c.module_name = @module_name")
            params.append({"name": "@module_name", "value": module_name})

        if status:
            conditions.append("c.status = @status")
            params.append({"name": "@status", "value": status})

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT TOP {limit} * FROM c {where_clause} ORDER BY c.completed_at DESC"

        items = list(self._container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
        return [dict(item) for item in items]
