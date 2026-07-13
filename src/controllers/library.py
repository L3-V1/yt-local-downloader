from __future__ import annotations

import os
from urllib.parse import urlencode

from fastapi import Request
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse, RedirectResponse, Response

from src.controllers.utils import extract_flash, redirect_with_flash, render_template
from src.services.library import (
    build_transfer_archive,
    LibraryServiceError,
    delete_video_file,
    delete_video_files,
    get_video_media_type,
    list_downloaded_videos,
    open_video_file,
    rename_video_file,
    transfer_video_file,
    transfer_video_files,
)

LIBRARY_PAGE_URL = "/library"


def render_library_page(request: Request) -> Response:
    """Render the local video library page."""
    flash_message, flash_level = extract_flash(request)
    return render_template(
        request=request,
        template_name="library.html",
        context={
            "videos": list_downloaded_videos(),
            "flash_message": flash_message,
            "flash_level": flash_level,
        },
    )


def handle_open_library_video(*, file_name: str) -> RedirectResponse:
    """Redirect to browser playback for a downloaded video.

    Args:
        file_name: File selected by the user in the video library.

    Returns:
        Redirect to the media URL or back to the library on error.
    """
    try:
        file_path = open_video_file(file_name)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    query_string = urlencode({"file_name": file_path.name})
    return RedirectResponse(url=f"/library/media?{query_string}", status_code=303)


def stream_library_video(*, file_name: str) -> FileResponse:
    """Serve a downloaded video file for browser playback or download."""
    file_path = open_video_file(file_name)
    return FileResponse(
        path=file_path,
        media_type=get_video_media_type(file_path),
        filename=file_path.name,
        content_disposition_type="inline",
    )


def handle_transfer_library_video(*, file_name: str) -> Response:
    """Return a downloaded video file as an attachment.

    Args:
        file_name: File selected by the user in the video library.

    Returns:
        Attachment response or redirect with an error message.
    """
    try:
        file_path = transfer_video_file(file_name)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    return FileResponse(
        path=file_path,
        media_type=get_video_media_type(file_path),
        filename=file_path.name,
        content_disposition_type="attachment",
    )


def handle_rename_library_video(*, file_name: str, new_file_name: str) -> RedirectResponse:
    """Rename a downloaded video inside the local library.

    Args:
        file_name: Current file selected by the user in the video library.
        new_file_name: New file name requested by the user.

    Returns:
        Redirect with a one-time success or error message.
    """
    try:
        renamed_path = rename_video_file(file_name, new_file_name)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    return redirect_with_flash(
        LIBRARY_PAGE_URL,
        message=f"Vídeo renomeado com sucesso para {renamed_path.name}.",
        level="success",
    )


def handle_transfer_library_videos(*, file_names: list[str]) -> Response:
    """Return selected downloaded videos as a zip attachment.

    Args:
        file_names: Selected files from the video library.

    Returns:
        Attachment response or redirect with an error message.
    """
    try:
        selected_files = transfer_video_files(file_names)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    if len(selected_files) == 1:
        file_path = selected_files[0]
        return FileResponse(
            path=file_path,
            media_type=get_video_media_type(file_path),
            filename=file_path.name,
            content_disposition_type="attachment",
        )

    try:
        archive_path = build_transfer_archive(selected_files)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    return FileResponse(
        path=archive_path,
        media_type="application/zip",
        filename="videos-selecionados.zip",
        content_disposition_type="attachment",
        background=BackgroundTask(_delete_temporary_file, archive_path),
    )


def handle_delete_library_video(*, file_name: str) -> RedirectResponse:
    """Delete a local video file from the downloads library.

    Args:
        file_name: File selected by the user in the video library.

    Returns:
        Redirect with a one-time success or error message.
    """
    try:
        delete_video_file(file_name)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    return redirect_with_flash(
        LIBRARY_PAGE_URL,
        message="Vídeo removido da biblioteca com sucesso.",
        level="success",
    )


def handle_delete_library_videos(*, file_names: list[str]) -> RedirectResponse:
    """Delete multiple local video files from the downloads library.

    Args:
        file_names: Selected files from the video library.

    Returns:
        Redirect with a one-time success or error message.
    """
    try:
        removed_count = delete_video_files(file_names)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    message = _pluralize_video_message(
        removed_count,
        singular="1 vídeo foi removido da biblioteca com sucesso.",
        plural_template="{count} vídeos foram removidos da biblioteca com sucesso.",
    )
    return redirect_with_flash(LIBRARY_PAGE_URL, message=message, level="success")


def _redirect_library_error(message: str) -> RedirectResponse:
    return redirect_with_flash(LIBRARY_PAGE_URL, message=message, level="error")


def _pluralize_video_message(quantity: int, *, singular: str, plural_template: str) -> str:
    if quantity == 1:
        return singular
    return plural_template.format(count=quantity)


def _delete_temporary_file(file_path: str | os.PathLike[str]) -> None:
    try:
        os.unlink(file_path)
    except FileNotFoundError:
        return
