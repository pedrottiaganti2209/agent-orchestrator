"""Definição do grafo LangGraph para orquestração da migração de mainframe."""
from __future__ import annotations

import structlog
from langgraph.graph import END, StateGraph

from agents.analysis_agent import AnalysisAgent
from agents.deployment_agent import DeploymentAgent
from agents.development_agent import DevelopmentAgent
from agents.documentation_agent import DocumentationAgent
from agents.observability_agent import ObservabilityAgent
from agents.packaging_agent import PackagingAgent
from agents.testing_agent import TestingAgent
from memory.cosmos_history import CosmosHistory
from orchestrator.router import route_after_deployment, route_after_tests
from orchestrator.state import MigrationState

logger = structlog.get_logger(__name__)


def build_migration_graph():
    """Constrói e compila o grafo LangGraph de migração.

    Fluxo:
        análise → desenvolvimento + documentação (paralelo) → testes
        → condicional (empacotamento | retry | falha)
        → implantação → observabilidade

    Retorna um CompiledGraph pronto para invocar com um MigrationState inicial.
    """
    _analysis = AnalysisAgent()
    _documentation = DocumentationAgent()
    _development = DevelopmentAgent()
    _testing = TestingAgent()
    _packaging = PackagingAgent()
    _deployment = DeploymentAgent()
    _observability = ObservabilityAgent()
    _cosmos = CosmosHistory()

    def run_analysis(state: MigrationState) -> MigrationState:
        logger.info("node_start", node="analysis", module=state.get("module_name"))
        return _analysis.run(state)

    def run_development(state: MigrationState) -> MigrationState:
        retry = state.get("retry_count", 0)
        logger.info("node_start", node="development", module=state.get("module_name"), attempt=retry + 1)
        result = _development.run(state)
        result["retry_count"] = retry + 1
        return result

    def run_documentation(state: MigrationState) -> MigrationState:
        logger.info("node_start", node="documentation", module=state.get("module_name"))
        return _documentation.run(state)

    def run_testing(state: MigrationState) -> MigrationState:
        logger.info("node_start", node="testing", module=state.get("module_name"))
        return _testing.run(state)

    def run_packaging(state: MigrationState) -> MigrationState:
        logger.info("node_start", node="packaging", module=state.get("module_name"))
        return _packaging.run(state)

    def run_deployment(state: MigrationState) -> MigrationState:
        logger.info("node_start", node="deployment", module=state.get("module_name"))
        return _deployment.run(state)

    def run_observability(state: MigrationState) -> MigrationState:
        logger.info("node_start", node="observability", module=state.get("module_name"))
        result = _observability.run(state)
        result["status"] = "SUCCESS"
        _cosmos.save_execution(result)
        logger.info("migration_complete", module=state.get("module_name"), status="SUCCESS")
        return result

    def handle_failure(state: MigrationState) -> MigrationState:
        logger.error(
            "migration_failed",
            module=state.get("module_name"),
            retry_count=state.get("retry_count", 0),
            errors=state.get("errors"),
        )
        state["status"] = "FAILED"
        _cosmos.save_execution(state)
        return state

    graph = StateGraph(MigrationState)

    graph.add_node("analysis", run_analysis)
    graph.add_node("development", run_development)
    graph.add_node("documentation", run_documentation)
    graph.add_node("testing", run_testing)
    graph.add_node("packaging", run_packaging)
    graph.add_node("deployment", run_deployment)
    graph.add_node("observability", run_observability)
    graph.add_node("end_failed", handle_failure)

    graph.set_entry_point("analysis")

    # Após análise: desenvolvimento e documentação em paralelo
    graph.add_edge("analysis", "development")
    graph.add_edge("analysis", "documentation")

    # Ambos convergem para testes (fan-in)
    graph.add_edge("development", "testing")
    graph.add_edge("documentation", "testing")

    # Roteamento condicional após testes
    graph.add_conditional_edges(
        "testing",
        route_after_tests,
        {
            "packaging": "packaging",
            "development": "development",
            "end_failed": "end_failed",
        },
    )

    graph.add_edge("packaging", "deployment")

    # Roteamento condicional após deploy
    graph.add_conditional_edges(
        "deployment",
        route_after_deployment,
        {
            "observability": "observability",
            "end_failed": "end_failed",
        },
    )

    graph.add_edge("observability", END)
    graph.add_edge("end_failed", END)

    return graph.compile()


MIGRATION_GRAPH = build_migration_graph()
