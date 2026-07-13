from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from src.controllers.library import (
    handle_delete_library_video,
    handle_delete_library_videos,
    handle_open_library_video,
    handle_rename_library_video,
    handle_transfer_library_video,
    handle_transfer_library_videos,
    render_library_page,
    stream_library_video,
)

router = APIRouter()


@router.get("/library")
async def library(request: Request) -> Response:
    return render_library_page(request)


@router.post("/library/open")
async def open_library_video(file_name: str = Form(...)) -> RedirectResponse:
    return handle_open_library_video(file_name=file_name)


@router.get("/library/media")
async def library_media(file_name: str = Query(...)) -> FileResponse:
    return stream_library_video(file_name=file_name)


@router.post("/library/rename")
async def rename_library_video(
    file_name: str = Form(...),
    new_file_name: str = Form(...),
) -> RedirectResponse:
    return handle_rename_library_video(file_name=file_name, new_file_name=new_file_name)


@router.post("/library/transfer")
async def transfer_library_video(file_name: str = Form(...)) -> Response:
    return handle_transfer_library_video(file_name=file_name)


@router.post("/library/transfer-batch")
async def transfer_library_videos(
    file_names: Annotated[list[str], Form(...)],
) -> Response:
    return handle_transfer_library_videos(file_names=file_names)


@router.post("/library/delete")
async def delete_library_video(file_name: str = Form(...)) -> RedirectResponse:
    return handle_delete_library_video(file_name=file_name)


@router.post("/library/delete-batch")
async def delete_library_videos(
    file_names: Annotated[list[str], Form(...)],
) -> RedirectResponse:
    return handle_delete_library_videos(file_names=file_names)
