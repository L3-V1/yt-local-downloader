from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import RedirectResponse, Response

from src.controllers.downloads import (
    get_downloads_status,
    handle_clear_downloads,
    handle_delete_download,
    handle_download_video,
    handle_download_video_async,
    handle_retry_download,
    render_downloads_page,
)

router = APIRouter()


@router.post("/download")
async def download_video(
    request: Request,
    background_tasks: BackgroundTasks,
    video_url: str = Form(...),
    video_format: str = Form("mp4"),
    video_quality: str = Form("best"),
) -> Response:
    if _prefers_json_response(request):
        return handle_download_video_async(
            background_tasks,
            video_url=video_url,
            video_format=video_format,
            video_quality=video_quality,
        )

    return handle_download_video(
        background_tasks,
        video_url=video_url,
        video_format=video_format,
        video_quality=video_quality,
    )


@router.get("/downloads")
async def downloads(request: Request) -> Response:
    return render_downloads_page(request)


@router.get("/downloads/status")
async def downloads_status() -> Response:
    return get_downloads_status()


@router.post("/downloads/{download_id}/delete")
async def delete_download(download_id: str) -> RedirectResponse:
    return handle_delete_download(download_id)


@router.post("/downloads/{download_id}/retry")
async def retry_download(background_tasks: BackgroundTasks, download_id: str) -> RedirectResponse:
    return handle_retry_download(background_tasks, download_id)


@router.post("/downloads/clear")
async def clear_downloads() -> RedirectResponse:
    return handle_clear_downloads()


def _prefers_json_response(request: Request) -> bool:
    accept_header = request.headers.get("accept", "")
    requested_with = request.headers.get("x-requested-with", "")
    return "application/json" in accept_header.lower() or requested_with.lower() == "xmlhttprequest"
