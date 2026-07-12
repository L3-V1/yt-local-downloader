from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from src.controllers.logs import handle_clear_logs, render_logs_page

router = APIRouter()


@router.get("/logs")
async def logs(request: Request) -> Response:
    return render_logs_page(request)


@router.post("/logs/clear")
async def clear_logs() -> RedirectResponse:
    return handle_clear_logs()
