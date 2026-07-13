from __future__ import annotations

import logging
from typing import Any, Iterable, TypedDict, cast
from urllib.parse import urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

PAGE_SIZE = 10
MAX_QUERY_LENGTH = 100
ALLOWED_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
LOGGER = logging.getLogger(__name__)


class SearchResult(TypedDict):
    title: str
    channel: str
    duration_display: str
    url: str
    thumbnail: str


class SearchPage(TypedDict):
    items: list[SearchResult]
    has_more: bool
    page: int
    page_size: int


class SearchServiceError(Exception):
    """Raised when the video search request cannot be fulfilled."""


def search_videos(query: str, page: int = 1, page_size: int = PAGE_SIZE) -> SearchPage:
    """Search public YouTube videos or resolve a direct video URL.

    Args:
        query: User-provided search text or public YouTube URL.
        page: 1-based page number.
        page_size: Number of items per page.

    Returns:
        A paginated set of normalized public video results for the UI.
    """
    normalized_query = _validate_query(query)
    normalized_page = _validate_page(page)
    normalized_page_size = _validate_page_size(page_size)

    if _is_supported_youtube_url(normalized_query):
        return _search_direct_video(normalized_query)

    return _search_by_term(normalized_query, normalized_page, normalized_page_size)


def _search_by_term(query: str, page: int, page_size: int) -> SearchPage:
    fetch_count = page * page_size + 1

    try:
        with YoutubeDL(cast(Any, _build_ydl_options())) as ydl:
            raw_result = cast(dict[str, Any], ydl.extract_info(f"ytsearch{fetch_count}:{query}", download=False))
    except DownloadError as exc:
        LOGGER.warning("yt-dlp search failed for query=%r page=%s: %s", query, page, exc)
        raise SearchServiceError("Não foi possível buscar vídeos agora. Tente novamente em instantes.") from exc

    normalized_items = _normalize_entries(raw_result.get("entries", []))
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    page_items = normalized_items[start_index:end_index]
    has_more = len(normalized_items) > end_index

    return {
        "items": page_items,
        "has_more": has_more,
        "page": page,
        "page_size": page_size,
    }


def _search_direct_video(video_url: str) -> SearchPage:
    try:
        with YoutubeDL(cast(Any, _build_ydl_options())) as ydl:
            raw_result = cast(dict[str, Any], ydl.extract_info(video_url, download=False))
    except DownloadError as exc:
        LOGGER.warning("yt-dlp direct lookup failed for url=%r: %s", video_url, exc)
        raise SearchServiceError("Não foi possível carregar esse vídeo do YouTube agora. Tente novamente em instantes.") from exc

    normalized_items = _normalize_direct_result(raw_result, video_url)
    return {
        "items": normalized_items,
        "has_more": False,
        "page": 1,
        "page_size": PAGE_SIZE,
    }


def _build_ydl_options() -> dict[str, bool]:
    return {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "noplaylist": True,
    }


def _validate_query(query: str) -> str:
    normalized_query = query.strip()
    if not normalized_query:
        raise SearchServiceError("Informe um termo de pesquisa ou um link do YouTube para continuar.")
    if not _is_supported_youtube_url(normalized_query) and len(normalized_query) > MAX_QUERY_LENGTH:
        raise SearchServiceError("Use uma pesquisa com até 100 caracteres.")
    return normalized_query


def _validate_page(page: int) -> int:
    if page < 1:
        raise SearchServiceError("A página informada é inválida.")
    return page


def _validate_page_size(page_size: int) -> int:
    if page_size < 1 or page_size > PAGE_SIZE:
        raise SearchServiceError("O tamanho da página é inválido.")
    return page_size


def _normalize_entries(entries: Iterable[dict[str, Any]]) -> list[SearchResult]:
    results: list[SearchResult] = []

    for entry in entries:
        normalized_result = _normalize_entry(entry)
        if normalized_result is None:
            continue
        results.append(normalized_result)

    return results


def _normalize_direct_result(raw_result: dict[str, Any], fallback_url: str) -> list[SearchResult]:
    normalized_result = _normalize_entry(raw_result, fallback_url=fallback_url)
    if normalized_result is None:
        raise SearchServiceError("Não foi possível identificar um vídeo válido a partir desse link.")
    return [normalized_result]


def _normalize_entry(entry: dict[str, Any], *, fallback_url: str = "") -> SearchResult | None:
    video_id = str(entry.get("id") or "").strip()
    raw_url = str(entry.get("url") or fallback_url).strip()
    webpage_url = _build_video_url(video_id, raw_url)
    if not webpage_url:
        return None

    return {
        "title": str(entry.get("title") or "Sem título"),
        "channel": str(
            entry.get("channel")
            or entry.get("uploader")
            or entry.get("uploader_id")
            or "Canal desconhecido"
        ),
        "duration_display": _build_duration_display(entry),
        "url": webpage_url,
        "thumbnail": _build_thumbnail_url(video_id, entry),
    }


def _build_video_url(video_id: str, fallback_url: str) -> str:
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    if fallback_url.startswith("http://") or fallback_url.startswith("https://"):
        return fallback_url
    return ""


def _build_thumbnail_url(video_id: str, entry: dict[str, Any]) -> str:
    thumbnail = str(entry.get("thumbnail") or "").strip()
    if thumbnail:
        return thumbnail
    if not video_id:
        return "https://placehold.co/640x360/212121/ffffff?text=Sem+Thumbnail"
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _build_duration_display(entry: dict[str, Any]) -> str:
    duration_string = str(entry.get("duration_string") or "").strip()
    if duration_string:
        return duration_string

    raw_duration = entry.get("duration")
    if isinstance(raw_duration, bool) or raw_duration is None:
        return "Não informado"

    try:
        total_seconds = int(float(raw_duration))
    except (TypeError, ValueError):
        return "Não informado"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _is_supported_youtube_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    return parsed.netloc.lower() in ALLOWED_YOUTUBE_HOSTS and bool(parsed.path.strip("/"))
