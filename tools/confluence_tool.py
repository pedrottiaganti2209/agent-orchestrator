"""Ferramenta para publicar documentação no Confluence."""
from __future__ import annotations

import os

import requests
import structlog

logger = structlog.get_logger(__name__)

CONFLUENCE_TOOL_DEFINITION = {
    "name": "confluence_publish_page",
    "description": "Publica ou atualiza uma página de documentação no Confluence.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Título da página"},
            "content": {"type": "string", "description": "Conteúdo da página em Confluence wiki markup"},
            "space_key": {"type": "string", "description": "Chave do espaço Confluence"},
            "parent_id": {"type": "string", "description": "ID da página pai (opcional)"},
        },
        "required": ["title", "content"],
    },
}


def _get_headers() -> dict[str, str]:
    token = os.environ["CONFLUENCE_TOKEN"]
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _find_existing_page(base_url: str, space_key: str, title: str, headers: dict) -> str | None:
    """Busca uma página existente pelo título no espaço."""
    url = f"{base_url}/rest/api/content"
    params = {"spaceKey": space_key, "title": title, "expand": "version"}
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    if resp.status_code == 200:
        results = resp.json().get("results", [])
        if results:
            return str(results[0]["id"])
    return None


def publish_page(
    title: str,
    content: str,
    space_key: str | None = None,
    parent_id: str | None = None,
) -> str:
    """Publica ou atualiza uma página no Confluence.

    Se já existir uma página com o mesmo título no espaço, ela é atualizada.
    Caso contrário, uma nova página é criada.

    Args:
        title: Título da página.
        content: Conteúdo em formato Confluence Storage Format (XML-like).
        space_key: Chave do espaço (padrão: CONFLUENCE_SPACE_KEY do .env).
        parent_id: ID opcional da página pai para organização hierárquica.

    Returns:
        URL da página criada ou atualizada.
    """
    base_url = os.environ["CONFLUENCE_URL"]
    space = space_key or os.environ["CONFLUENCE_SPACE_KEY"]
    headers = _get_headers()

    existing_id = _find_existing_page(base_url, space, title, headers)

    body_content = {"storage": {"value": content, "representation": "storage"}}

    if existing_id:
        get_url = f"{base_url}/rest/api/content/{existing_id}?expand=version"
        get_resp = requests.get(get_url, headers=headers, timeout=30)
        version = get_resp.json().get("version", {}).get("number", 1) + 1

        url = f"{base_url}/rest/api/content/{existing_id}"
        payload = {"version": {"number": version}, "title": title, "type": "page", "body": body_content}
        resp = requests.put(url, json=payload, headers=headers, timeout=30)
    else:
        url = f"{base_url}/rest/api/content"
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space},
            "body": body_content,
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]
        resp = requests.post(url, json=payload, headers=headers, timeout=30)

    resp.raise_for_status()
    page_url: str = resp.json().get("_links", {}).get("webui", "")
    logger.info("confluence_page_published", title=title, url=page_url)
    return page_url
