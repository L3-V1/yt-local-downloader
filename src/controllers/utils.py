from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

from fastapi import Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

FlashLevel = Literal["success", "warning", "error", "info"]
ALLOWED_FLASH_LEVELS = {"success", "warning", "error", "info"}
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def render_template(
    *,
    request: Request,
    template_name: str,
    context: dict[str, object] | None = None,
) -> Response:
    """Render a Jinja template with the request-bound context."""
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context or {},
    )


def redirect_with_flash(base_url: str, *, message: str, level: FlashLevel) -> RedirectResponse:
    """Redirect to a page and attach a one-time flash message via query params."""
    query_string = urlencode({"flash_message": message, "flash_level": level})
    return RedirectResponse(url=f"{base_url}?{query_string}", status_code=status.HTTP_303_SEE_OTHER)


def extract_flash(request: Request) -> tuple[str | None, FlashLevel | None]:
    """Extract the flash payload from the current request query string."""
    flash_message = request.query_params.get("flash_message")
    flash_level = request.query_params.get("flash_level")
    if flash_level not in ALLOWED_FLASH_LEVELS:
        flash_level = "info" if flash_level else None
    return flash_message, flash_level
