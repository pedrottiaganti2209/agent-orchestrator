"""Script de exemplo para execução end-to-end de uma migração."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import structlog
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger(__name__)


def configure_logging(log_level: str = "INFO") -> None:
    """Configura logging estruturado em JSON."""
    import logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=getattr(logging, log_level.upper(), logging.INFO))


def run_migration(
    cobol_path: str,
    jcl_path: str,
    module_name: str,
    execution_id: str | None = None,
) -> dict:
    """Executa a migração completa de um módulo COBOL.

    Args:
        cobol_path: Caminho para o arquivo .cbl.
        jcl_path: Caminho para o arquivo .jcl.
        module_name: Nome do módulo (usado como identificador único).
        execution_id: ID opcional para retomada de execução interrompida.

    Returns:
        Estado final da migração com todos os artefatos produzidos.
    """
    from orchestrator.graph import MIGRATION_GRAPH
    from orchestrator.state import MigrationState

    cobol_source = Path(cobol_path).read_text(encoding="utf-8")
    jcl_source = Path(jcl_path).read_text(encoding="utf-8")

    exec_id = execution_id or str(uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    initial_state: MigrationState = {
        "module_name": module_name,
        "cobol_source": cobol_source,
        "jcl_source": jcl_source,
        "business_rules": [],
        "bdd_specs": [],
        "generated_code": {},
        "pr_url": "",
        "test_results": {"passed": False, "coverage": 0.0, "parity_delta": []},
        "artifact_version": "",
        "acr_image_tag": "",
        "deploy_status": "",
        "observability_config": {},
        "errors": [],
        "execution_id": exec_id,
        "started_at": started_at,
        "retry_count": 0,
        "status": "IN_PROGRESS",
    }

    logger.info(
        "migration_started",
        module=module_name,
        execution_id=exec_id,
        cobol_path=cobol_path,
    )

    final_state = MIGRATION_GRAPH.invoke(initial_state)

    logger.info(
        "migration_finished",
        module=module_name,
        execution_id=exec_id,
        status=final_state.get("status"),
        pr_url=final_state.get("pr_url"),
        acr_image_tag=final_state.get("acr_image_tag"),
        errors_count=len(final_state.get("errors") or []),
    )

    return final_state


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orquestrador multi-agente para migração COBOL → Java/Spring Boot"
    )
    parser.add_argument("--cobol", required=True, help="Caminho para o arquivo .cbl")
    parser.add_argument("--jcl", required=True, help="Caminho para o arquivo .jcl")
    parser.add_argument("--module-name", required=True, help="Nome do módulo COBOL")
    parser.add_argument("--execution-id", help="ID para retomada de execução interrompida")
    parser.add_argument("--log-level", default="INFO", help="Nível de log (INFO, DEBUG, WARNING)")
    parser.add_argument("--output-json", help="Caminho para salvar o estado final em JSON")

    args = parser.parse_args()
    configure_logging(args.log_level)

    try:
        result = run_migration(
            cobol_path=args.cobol,
            jcl_path=args.jcl,
            module_name=args.module_name,
            execution_id=args.execution_id,
        )

        if args.output_json:
            Path(args.output_json).write_text(
                json.dumps(result, indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Estado final salvo em: {args.output_json}")

        status = result.get("status", "UNKNOWN")
        print(f"\nStatus: {status}")
        print(f"PR URL: {result.get('pr_url', 'N/A')}")
        print(f"Imagem ACR: {result.get('acr_image_tag', 'N/A')}")

        if result.get("errors"):
            print(f"\nErros encontrados ({len(result['errors'])}):",
                  file=sys.stderr)
            for err in result["errors"]:
                print(f"  - {err}", file=sys.stderr)

        sys.exit(0 if status == "SUCCESS" else 1)

    except KeyboardInterrupt:
        print("\nMigração interrompida pelo usuário.")
        sys.exit(1)
    except Exception as exc:
        logger.error("migration_unexpected_error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
