"""Ferramenta para push de imagens Docker no Azure Container Registry."""
from __future__ import annotations

import os
import subprocess

import structlog
from azure.identity import DefaultAzureCredential
from azure.mgmt.containerregistry import ContainerRegistryManagementClient

logger = structlog.get_logger(__name__)

ACR_TOOL_DEFINITION = {
    "name": "acr_push_image",
    "description": "Faz push de uma imagem Docker para o Azure Container Registry.",
    "input_schema": {
        "type": "object",
        "properties": {
            "image_name": {"type": "string", "description": "Nome da imagem (sem registry prefix)"},
            "image_tag": {"type": "string", "description": "Tag da imagem (ex: 1.0.0)"},
            "dockerfile_path": {"type": "string", "description": "Caminho para o Dockerfile", "default": "."},
        },
        "required": ["image_name", "image_tag"],
    },
}


def push_image_to_acr(image_name: str, image_tag: str, dockerfile_path: str = ".") -> str:
    """Autentica no ACR, builda e faz push da imagem Docker.

    Args:
        image_name: Nome da imagem sem o registry prefix.
        image_tag: Tag da versão (ex: '1.0.0').
        dockerfile_path: Diretório com o Dockerfile (padrão: diretório atual).

    Returns:
        Full image reference no formato 'registry/image:tag'.
    """
    acr_server = os.environ["ACR_LOGIN_SERVER"]
    full_image = f"{acr_server}/{image_name}:{image_tag}"

    subprocess.run(
        ["az", "acr", "login", "--name", os.environ["ACR_NAME"]],
        check=True,
        capture_output=True,
    )
    logger.info("acr_login_success", registry=acr_server)

    subprocess.run(
        ["docker", "build", "-t", full_image, dockerfile_path],
        check=True,
        capture_output=True,
    )
    logger.info("docker_build_success", image=full_image)

    subprocess.run(
        ["docker", "push", full_image],
        check=True,
        capture_output=True,
    )
    logger.info("docker_push_success", image=full_image)

    return full_image
