"""Gerador de relatórios de divergências de paridade entre mainframe e Java."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ParityReporter:
    """Gera relatórios estruturados de divergências encontradas no parity testing.

    Suporta exportação em JSON (para ingestão em dashboards) e texto (para logs).
    """

    def generate(
        self,
        module_name: str,
        execution_id: str,
        deltas: list[dict],
        total_test_cases: int,
    ) -> dict:
        """Gera relatório completo de paridade para uma execução.

        Args:
            module_name: Nome do módulo testado.
            execution_id: ID da execução do orquestrador.
            deltas: Lista de divergências retornada pelo ParityComparator.
            total_test_cases: Total de casos de teste executados.

        Returns:
            Dict com o relatório estruturado, pronto para serialização JSON.
        """
        fields_with_divergence = list({d["field"] for d in deltas})
        test_cases_with_divergence = list({d.get("test_case", "unknown") for d in deltas})

        report = {
            "module_name": module_name,
            "execution_id": execution_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_test_cases": total_test_cases,
                "passed_test_cases": total_test_cases - len(test_cases_with_divergence),
                "failed_test_cases": len(test_cases_with_divergence),
                "total_divergences": len(deltas),
                "divergent_fields": fields_with_divergence,
                "parity_rate": round(
                    (total_test_cases - len(test_cases_with_divergence)) / max(total_test_cases, 1) * 100,
                    2,
                ),
            },
            "divergences": deltas,
            "status": "APPROVED" if not deltas else "DIVERGENT",
        }

        if deltas:
            logger.warning(
                "parity_report_divergent",
                module=module_name,
                total_divergences=len(deltas),
                parity_rate=report["summary"]["parity_rate"],
            )
        else:
            logger.info(
                "parity_report_approved",
                module=module_name,
                total_test_cases=total_test_cases,
            )

        return report

    def to_text(self, report: dict) -> str:
        """Formata o relatório como texto legível para logs e alertas."""
        summary = report["summary"]
        lines = [
            f"=== RELATÓRIO DE PARIDADE: {report['module_name']} ===",
            f"Status: {report['status']}",
            f"Gerado em: {report['generated_at']}",
            f"Total de casos: {summary['total_test_cases']}",
            f"Aprovados: {summary['passed_test_cases']}",
            f"Com divergência: {summary['failed_test_cases']}",
            f"Taxa de paridade: {summary['parity_rate']}%",
            f"Total de divergências: {summary['total_divergences']}",
        ]

        if report["divergences"]:
            lines.append("\nDIVERGÊNCIAS DETALHADAS:")
            for div in report["divergences"][:20]:
                delta_str = f" (delta={div['delta']:.6f})" if div.get("delta") is not None else ""
                lines.append(
                    f"  [{div.get('test_case', '?')}] {div['field']}: "
                    f"mainframe={div['mainframe_value']} | java={div['java_value']}{delta_str}"
                )
            if len(report["divergences"]) > 20:
                lines.append(f"  ... e mais {len(report['divergences']) - 20} divergências")

        return "\n".join(lines)

    def to_json(self, report: dict) -> str:
        """Serializa o relatório como JSON formatado."""
        return json.dumps(report, indent=2, ensure_ascii=False, default=str)
