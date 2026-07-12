from fastapi import APIRouter
from fastapi.responses import Response

from src.controllers.system import render_chrome_devtools_probe

router = APIRouter()


@router.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def chrome_devtools_probe() -> Response:
    return render_chrome_devtools_probe()
