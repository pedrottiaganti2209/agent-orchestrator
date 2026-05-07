"""Ferramenta de integração com GitHub para criação de branches, commits e Pull Requests."""
from __future__ import annotations

import os

import requests
import structlog

logger = structlog.get_logger(__name__)

GITHUB_TOOL_DEFINITION = {
    "name": "github_create_pr",
    "description": "Cria um Pull Request no GitHub com o código migrado, incluindo todos os arquivos gerados.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Título do Pull Request"},
            "body": {"type": "string", "description": "Descrição detalhada do PR em markdown"},
            "branch": {"type": "string", "description": "Nome da branch com as alterações"},
            "base": {"type": "string", "description": "Branch base (padrão: main)", "default": "main"},
            "files": {
                "type": "object",
                "description": "Mapa de caminho → conteúdo dos arquivos a commitar",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["title", "body", "branch", "files"],
    },
}


def _get_headers() -> dict[str, str]:
    token = os.environ["GITHUB_TOKEN"]
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_default_branch_sha(repo: str, base_branch: str, headers: dict) -> str:
    """Obtém o SHA atual do branch base."""
    url = f"https://api.github.com/repos/{repo}/git/ref/heads/{base_branch}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()["object"]["sha"]


def _create_branch(repo: str, branch: str, sha: str, headers: dict) -> None:
    """Cria um novo branch a partir do SHA fornecido."""
    url = f"https://api.github.com/repos/{repo}/git/refs"
    payload = {"ref": f"refs/heads/{branch}", "sha": sha}
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code not in (201, 422):
        resp.raise_for_status()


def _commit_files(repo: str, branch: str, files: dict[str, str], headers: dict) -> None:
    """Commita múltiplos arquivos em um branch via API do GitHub."""
    for file_path, content in files.items():
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        get_resp = requests.get(url, params={"ref": branch}, headers=headers, timeout=30)

        import base64
        payload: dict = {
            "message": f"feat: add {file_path.split('/')[-1]}",
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if get_resp.status_code == 200:
            payload["sha"] = get_resp.json()["sha"]

        put_resp = requests.put(url, json=payload, headers=headers, timeout=30)
        put_resp.raise_for_status()


def create_pull_request(
    title: str,
    body: str,
    branch: str,
    files: dict[str, str],
    base: str | None = None,
) -> str:
    """Cria uma branch, commita arquivos e abre um Pull Request no GitHub.

    Args:
        title: Título do PR.
        body: Descrição do PR em markdown.
        branch: Nome do branch a criar com as alterações.
        files: Mapa de caminho → conteúdo dos arquivos.
        base: Branch base do PR (padrão: GITHUB_DEFAULT_BRANCH ou 'main').

    Returns:
        URL do Pull Request criado.
    """
    repo = os.environ["GITHUB_REPO"]
    base_branch = base or os.getenv("GITHUB_DEFAULT_BRANCH", "main")
    headers = _get_headers()

    sha = _get_default_branch_sha(repo, base_branch, headers)
    _create_branch(repo, branch, sha, headers)
    _commit_files(repo, branch, files, headers)

    url = f"https://api.github.com/repos/{repo}/pulls"
    payload = {"title": title, "body": body, "head": branch, "base": base_branch}
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()

    pr_url: str = resp.json()["html_url"]
    logger.info("pr_created", url=pr_url, branch=branch)
    return pr_url
