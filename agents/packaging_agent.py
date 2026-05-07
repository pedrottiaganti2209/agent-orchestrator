"""Agente responsável por empacotar o artefato e publicar no Azure Container Registry."""
from __future__ import annotations

import structlog

from agents.base_agent import BaseAgent
from orchestrator.state import MigrationState
from prompts.packaging_prompt import PACKAGING_SYSTEM_PROMPT
from tools.azure_acr_tool import push_image_to_acr
from tools.azure_devops_tool import trigger_pipeline

logger = structlog.get_logger(__name__)


class PackagingAgent(BaseAgent):
    """Executa Maven build, cria imagem Docker e faz push para o ACR.

    Popula `acr_image_tag` no estado compartilhado.
    """

    def get_system_prompt(self) -> str:
        return PACKAGING_SYSTEM_PROMPT

    def build_messages(self, state: MigrationState) -> list[dict]:
        """Constrói prompt com informações do artefato para gerar Dockerfile e configurações."""
        user_content = f"""Gere o Dockerfile e as configurações de empacotamento para o módulo {state.get('module_name')}.

VERSÃO DO ARTEFATO: {state.get('artifact_version', '1.0.0-SNAPSHOT')}
MÓDULO: {state.get('module_name')}

Retorne um JSON com:
{{
  "dockerfile": "conteúdo do Dockerfile multi-stage",
  "image_name": "nome-da-imagem-em-lowercase",
  "image_tag": "versão-da-tag (ex: 1.0.0)",
  "build_args": {{
    "JAVA_VERSION": "17",
    "APP_VERSION": "{state.get('artifact_version', '1.0.0-SNAPSHOT')}"
  }},
  "pipeline_name": "nome-da-pipeline-azure-devops"
}}"""
        return [{"role": "user", "content": user_content}]

    def parse_response(self, response_text: str, state: MigrationState) -> MigrationState:
        """Extrai configurações de empacotamento, aciona pipeline e atualiza estado."""
        try:
            data = self.extract_json(response_text)
            image_name = data.get("image_name", state.get("module_name", "app").lower())
            image_tag = data.get("image_tag", "1.0.0")

            acr_image_tag = ""
            try:
                acr_image_tag = push_image_to_acr(image_name=image_name, image_tag=image_tag)
                logger.info("acr_push_success", image=acr_image_tag, module=state.get("module_name"))
            except Exception as exc:
                logger.warning("acr_push_failed", error=str(exc))
                errors = list(state.get("errors") or [])
                errors.append(f"[PackagingAgent] Falha no push ACR: {exc}")
                return {**state, "errors": errors}

            try:
                pipeline_name = data.get("pipeline_name", f"migrate-{image_name}")
                trigger_pipeline(pipeline_name=pipeline_name, parameters={"imageTag": image_tag})
                logger.info("pipeline_triggered", pipeline=pipeline_name)
            except Exception as exc:
                logger.warning("pipeline_trigger_failed", error=str(exc))

            updated_code = {
                **(state.get("generated_code") or {}),
                "Dockerfile": data.get("dockerfile", ""),
            }

            return {
                **state,
                "generated_code": updated_code,
                "acr_image_tag": acr_image_tag,
            }
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("packaging_parse_error", error=str(exc))
            errors = list(state.get("errors") or [])
            errors.append(f"[PackagingAgent] Falha no empacotamento: {exc}")
            return {**state, "errors": errors}
