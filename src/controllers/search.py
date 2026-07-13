from __future__ import annotations

import json
import logging

from fastapi import Request
from fastapi.responses import Response

from src.controllers.utils import extract_flash, render_template
from src.services.search import PAGE_SIZE, SearchResult, SearchServiceError, search_videos

LOGGER = logging.getLogger(__name__)


def render_index_page(request: Request) -> Response:
    """Render the initial search page."""
    flash_message, flash_level = extract_flash(request)
    return _render_index(
        request=request,
        query="",
        results=[],
        flash_message=flash_message,
        flash_level=flash_level,
        page=1,
        has_more=False,
    )


def handle_search(
    request: Request,
    *,
    query: str,
    page: int,
    accumulated_results: str,
) -> Response:
    """Execute a video search and render the paginated result list."""
    normalized_query = query.strip()
    existing_results = _deserialize_accumulated_results(accumulated_results)

    try:
        search_page = search_videos(normalized_query, page=page, page_size=PAGE_SIZE)
        results = _merge_results(
            existing_results=existing_results,
            new_results=search_page["items"],
        )
        current_page = search_page["page"]
        has_more = search_page["has_more"]
        flash_level = "success"
        flash_message = (
            f"{len(search_page['items'])} vídeo(s) carregado(s)."
            if current_page == 1
            else f"Mais {len(search_page['items'])} vídeo(s) carregado(s)."
        )
        if not search_page["items"]:
            flash_level = "warning"
            flash_message = "Nenhum vídeo adicional foi encontrado para esta pesquisa."
    except SearchServiceError as exc:
        LOGGER.warning("Search request failed for query=%r page=%s: %s", normalized_query, page, exc)
        results = existing_results
        current_page = max(page, 1)
        has_more = False
        flash_level = "error"
        flash_message = str(exc)

    return _render_index(
        request=request,
        query=normalized_query,
        results=results,
        flash_message=flash_message,
        flash_level=flash_level,
        page=current_page,
        has_more=has_more,
    )


def _render_index(
    *,
    request: Request,
    query: str,
    results: list[SearchResult],
    flash_message: str | None,
    flash_level: str | None,
    page: int,
    has_more: bool,
) -> Response:
    return render_template(
        request=request,
        template_name="index.html",
        context={
            "query": query,
            "results": results,
            "accumulated_results": results,
            "flash_message": flash_message,
            "flash_level": flash_level,
            "page": page,
            "next_page": page + 1,
            "has_more": has_more,
        },
    )


def _deserialize_accumulated_results(raw_payload: str) -> list[SearchResult]:
    if not raw_payload.strip():
        return []

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, list):
        return []

    results: list[SearchResult] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        channel = str(item.get("channel") or "").strip()
        duration_display = str(item.get("duration_display") or "").strip()
        url = str(item.get("url") or "").strip()
        thumbnail = str(item.get("thumbnail") or "").strip()
        if not title or not url:
            continue
        results.append(
            {
                "title": title,
                "channel": channel or "Canal desconhecido",
                "duration_display": duration_display or "Não informado",
                "url": url,
                "thumbnail": thumbnail or "https://placehold.co/640x360/212121/ffffff?text=Sem+Thumbnail",
            }
        )
    return results


def _merge_results(existing_results: list[SearchResult], new_results: list[SearchResult]) -> list[SearchResult]:
    merged_results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for item in [*existing_results, *new_results]:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        merged_results.append(item)

    return merged_results
