from __future__ import annotations

from dataclasses import dataclass

from fastapi import BackgroundTasks, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from src.controllers.utils import FlashLevel, extract_flash, redirect_with_flash, render_template
from src.services.download import (
    DownloadRequestError,
    download_registry,
    enqueue_download,
    enqueue_retry_download,
)


@dataclass(slots=True)
class DownloadSubmissionResult:
    success: bool
    message: str
    level: FlashLevel
    download_id: str | None = None


def handle_download_video(
    background_tasks: BackgroundTasks,
    *,
    video_url: str,
    video_format: str,
    video_quality: str,
) -> RedirectResponse:
    """Validate and queue a new download request.

    Args:
        background_tasks: Request-scoped background task registry.
        video_url: Public YouTube URL selected by the user.
        video_format: Preferred output format selected by the user.
        video_quality: Preferred maximum quality selected by the user.

    Returns:
        Redirect response with a one-time success or error message.
    """
    submission = submit_download_video(
        background_tasks,
        video_url=video_url,
        video_format=video_format,
        video_quality=video_quality,
    )
    return redirect_with_flash("/downloads", message=submission.message, level=submission.level)


def handle_download_video_async(
    background_tasks: BackgroundTasks,
    *,
    video_url: str,
    video_format: str,
    video_quality: str,
) -> JSONResponse:
    """Validate and queue a new asynchronous download request.

    Args:
        background_tasks: Request-scoped background task registry.
        video_url: Public YouTube URL selected by the user.
        video_format: Preferred output format selected by the user.
        video_quality: Preferred maximum quality selected by the user.

    Returns:
        JSON payload describing whether the download was queued successfully.
    """
    submission = submit_download_video(
        background_tasks,
        video_url=video_url,
        video_format=video_format,
        video_quality=video_quality,
    )
    return JSONResponse(
        status_code=200 if submission.success else 400,
        content={
            "success": submission.success,
            "message": submission.message,
            "level": submission.level,
            "download_id": submission.download_id,
        },
    )


def submit_download_video(
    background_tasks: BackgroundTasks,
    *,
    video_url: str,
    video_format: str,
    video_quality: str,
) -> DownloadSubmissionResult:
    """Validate and queue a new download request.

    Args:
        background_tasks: Request-scoped background task registry.
        video_url: Public YouTube URL selected by the user.
        video_format: Preferred output format selected by the user.
        video_quality: Preferred maximum quality selected by the user.

    Returns:
        Structured result that can be rendered as redirect feedback or JSON.
    """
    try:
        download_id = enqueue_download(
            background_tasks=background_tasks,
            video_url=video_url,
            video_format=video_format,
            video_quality=video_quality,
        )
    except DownloadRequestError:
        return DownloadSubmissionResult(
            success=False,
            message="Informe uma URL válida do YouTube e selecione um formato compatível.",
            level="error",
        )

    return DownloadSubmissionResult(
        success=True,
        message="Download enviado para a fila de processamento em segundo plano.",
        level="success",
        download_id=download_id,
    )


def render_downloads_page(request: Request) -> Response:
    """Render the download history and in-memory status list."""
    flash_message, flash_level = extract_flash(request)
    downloads = download_registry.list_downloads()

    return render_template(
        request=request,
        template_name="downloads.html",
        context={
            "downloads": downloads,
            "downloads_payload": [item.to_dict() for item in downloads],
            "flash_message": flash_message,
            "flash_level": flash_level,
        },
    )


def get_downloads_status() -> JSONResponse:
    """Return the current in-memory download state as JSON."""
    downloads = download_registry.list_downloads()
    return JSONResponse(
        content={
            "downloads": [item.to_dict() for item in downloads],
        }
    )


def handle_delete_download(download_id: str) -> RedirectResponse:
    """Remove a single download item from the in-memory history."""
    deleted = download_registry.remove(download_id)
    if not deleted:
        return redirect_with_flash(
            "/downloads",
            message="O item selecionado não foi encontrado no histórico.",
            level="error",
        )
    return redirect_with_flash(
        "/downloads",
        message="Item removido do histórico com sucesso.",
        level="success",
    )


def handle_retry_download(background_tasks: BackgroundTasks, download_id: str) -> RedirectResponse:
    """Queue a new download attempt using the same URL and preferences of a failed item."""
    try:
        new_download_id = enqueue_retry_download(background_tasks, download_id=download_id)
    except DownloadRequestError as exc:
        return redirect_with_flash("/downloads", message=str(exc), level="error")

    return redirect_with_flash(
        "/downloads",
        message=f"Novo download enviado para a fila com a referência {new_download_id}.",
        level="success",
    )


def handle_clear_downloads() -> RedirectResponse:
    """Remove all items from the in-memory download history."""
    download_registry.clear()
    return redirect_with_flash(
        "/downloads",
        message="Todo o histórico de downloads foi removido.",
        level="success",
    )
