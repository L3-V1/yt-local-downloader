from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from src.controllers.search import handle_search, render_index_page

router = APIRouter()


@router.get("/")
async def index(request: Request) -> Response:
    return render_index_page(request)


@router.post("/search")
async def search(
    request: Request,
    query: str = Form(...),
    page: int = Form(1),
    accumulated_results: str = Form(""),
) -> Response:
    return handle_search(
        request,
        query=query,
        page=page,
        accumulated_results=accumulated_results,
    )
