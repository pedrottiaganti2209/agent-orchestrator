"""Definição do estado compartilhado entre todos os agentes do orquestrador."""
from __future__ import annotations

from typing import TypedDict


class TestResults(TypedDict, total=False):
    """Resultado de execução dos testes de qualidade e paridade."""

    passed: bool
    coverage: float
    parity_delta: list[dict]
    junit_report: str
    total_tests: int
    failed_tests: int


class MigrationState(TypedDict, total=False):
    """Estado compartilhado entre todos os agentes durante a migração.

    Campos obrigatórios na criação inicial:
        module_name: Nome do módulo COBOL sendo migrado.
        cobol_source: Código-fonte COBOL completo.
        jcl_source: JCL correspondente ao programa.
        execution_id: UUID único desta execução.
        started_at: Timestamp ISO 8601 de início.

    Campos preenchidos progressivamente pelos agentes:
        business_rules: Regras de negócio extraídas pelo AnalysisAgent.
        bdd_specs: Specs Gherkin geradas pelo AnalysisAgent.
        generated_code: Mapa arquivo → conteúdo gerado pelo DevelopmentAgent.
        pr_url: URL do Pull Request aberto pelo DevelopmentAgent.
        test_results: Resultado dos testes pelo TestingAgent.
        artifact_version: Versão Maven do artefato (ex: 1.0.0-SNAPSHOT).
        acr_image_tag: Tag da imagem Docker no ACR.
        deploy_status: 'SUCCESS' | 'FAILED' | 'PENDING'.
        observability_config: Configuração de dashboards e alertas criados.
        errors: Lista de erros acumulados (não interrompe o grafo).
        retry_count: Número de tentativas de desenvolvimento realizadas.
        status: Status final: 'SUCCESS' | 'FAILED' | 'IN_PROGRESS'.
    """

    module_name: str
    cobol_source: str
    jcl_source: str
    business_rules: list[dict]
    bdd_specs: list[str]
    generated_code: dict[str, str]
    pr_url: str
    test_results: TestResults
    artifact_version: str
    acr_image_tag: str
    deploy_status: str
    observability_config: dict
    errors: list[str]
    execution_id: str
    started_at: str
    retry_count: int
    status: str
