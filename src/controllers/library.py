from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse, Response

from src.controllers.utils import extract_flash, redirect_with_flash, render_template
from src.services.library import (
    LibraryServiceError,
    delete_video_file,
    delete_video_files,
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
    """Open a downloaded video with the system default player.

    Args:
        file_name: File selected by the user in the video library.

    Returns:
        Redirect with a one-time success or error message.
    """
    try:
        open_video_file(file_name)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    return redirect_with_flash(
        LIBRARY_PAGE_URL,
        message="Vídeo aberto no reprodutor padrão do sistema.",
        level="success",
    )


def handle_transfer_library_video(*, file_name: str) -> RedirectResponse:
    """Move a downloaded video to a user-selected directory.

    Args:
        file_name: File selected by the user in the video library.

    Returns:
        Redirect with a one-time success or error message.
    """
    try:
        transfer_video_file(file_name)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    return redirect_with_flash(
        LIBRARY_PAGE_URL,
        message="Vídeo transferido com sucesso para o diretório selecionado.",
        level="success",
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


def handle_transfer_library_videos(*, file_names: list[str]) -> RedirectResponse:
    """Move multiple downloaded videos to a user-selected directory.

    Args:
        file_names: Selected files from the video library.

    Returns:
        Redirect with a one-time success or error message.
    """
    try:
        moved_paths = transfer_video_files(file_names)
    except LibraryServiceError as exc:
        return _redirect_library_error(str(exc))

    quantity = len(moved_paths)
    message = _pluralize_video_message(
        quantity,
        singular="1 vídeo foi transferido com sucesso para o diretório selecionado.",
        plural_template="{count} vídeos foram transferidos com sucesso para o diretório selecionado.",
    )
    return redirect_with_flash(LIBRARY_PAGE_URL, message=message, level="success")


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
