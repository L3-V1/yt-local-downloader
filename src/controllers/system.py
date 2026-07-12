from fastapi import status
from fastapi.responses import Response


def render_chrome_devtools_probe() -> Response:
    """Respond to the Chrome DevTools local probe without logging application noise."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)
