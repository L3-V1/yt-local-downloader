from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse, Response

from src.controllers.utils import extract_flash, redirect_with_flash, render_template
from src.services.log import log_registry


def render_logs_page(request: Request) -> Response:
    """Render the in-memory application logs page."""
    flash_message, flash_level = extract_flash(request)
    logs = log_registry.list_logs()
    return render_template(
        request=request,
        template_name="logs.html",
        context={
            "logs": logs,
            "logs_payload": [item.to_dict() for item in logs],
            "flash_message": flash_message,
            "flash_level": flash_level,
        },
    )


def handle_clear_logs() -> RedirectResponse:
    """Remove all log entries from the in-memory registry."""
    log_registry.clear()
    return redirect_with_flash(
        "/logs",
        message="A pilha de logs foi limpa com sucesso.",
        level="success",
    )
