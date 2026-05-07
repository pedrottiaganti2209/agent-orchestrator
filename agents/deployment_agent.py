"""Agente responsável por implantar o serviço migrado no Azure Kubernetes Service."""
from __future__ import annotations

import structlog

from agents.base_agent import BaseAgent
from orchestrator.state import MigrationState
from prompts.deployment_prompt import DEPLOYMENT_SYSTEM_PROMPT
from tools.azure_devops_tool import trigger_pipeline, wait_for_pipeline

logger = structlog.get_logger(__name__)


class DeploymentAgent(BaseAgent):
    """Implanta o serviço no AKS via Azure DevOps pipeline com rollback automático.

    Popula `deploy_status` no estado: 'SUCCESS' ou 'FAILED'.
    """

    def get_system_prompt(self) -> str:
        return DEPLOYMENT_SYSTEM_PROMPT

    def build_messages(self, state: MigrationState) -> list[dict]:
        """Constrói prompt com detalhes da imagem e configurações de deploy."""
        user_content = f"""Gere o manifesto Kubernetes para deploy do módulo {state.get('module_name')} no AKS.

IMAGEM ACR: {state.get('acr_image_tag', 'image:latest')}
VERSÃO: {state.get('artifact_version', '1.0.0')}
MÓDULO: {state.get('module_name')}

Retorne um JSON com:
{{
  "namespace": "migration",
  "deployment_name": "{state.get('module_name', 'app').lower()}-svc",
  "replicas": 2,
  "canary_percentage": 10,
  "health_check_path": "/actuator/health",
  "error_rate_threshold": 0.01,
  "rollback_on_error": true,
  "pipeline_name": "deploy-to-aks",
  "pipeline_parameters": {{
    "imageTag": "{state.get('acr_image_tag', '')}",
    "namespace": "migration",
    "moduleName": "{state.get('module_name', '')}"
  }}
}}"""
        return [{"role": "user", "content": user_content}]

    def parse_response(self, response_text: str, state: MigrationState) -> MigrationState:
        """Extrai configurações de deploy, aciona pipeline e monitora resultado."""
        try:
            data = self.extract_json(response_text)
            pipeline_name = data.get("pipeline_name", "deploy-to-aks")
            parameters = data.get("pipeline_parameters", {})

            try:
                run_id = trigger_pipeline(pipeline_name=pipeline_name, parameters=parameters)
                logger.info("deploy_pipeline_triggered", run_id=run_id, module=state.get("module_name"))

                success = wait_for_pipeline(run_id=run_id)
                deploy_status = "SUCCESS" if success else "FAILED"
                logger.info("deploy_completed", status=deploy_status, module=state.get("module_name"))
            except Exception as exc:
                logger.error("deploy_pipeline_error", error=str(exc))
                errors = list(state.get("errors") or [])
                errors.append(f"[DeploymentAgent] Falha no deploy: {exc}")
                return {**state, "errors": errors, "deploy_status": "FAILED"}

            return {**state, "deploy_status": deploy_status}
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("deployment_parse_error", error=str(exc))
            errors = list(state.get("errors") or [])
            errors.append(f"[DeploymentAgent] Falha no processamento do deploy: {exc}")
            return {**state, "errors": errors, "deploy_status": "FAILED"}
