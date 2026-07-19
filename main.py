import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.routes import download, library, log, search, system

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5000

app = FastAPI(title="YouTube Local Downloader")
app.mount("/static", StaticFiles(directory="src/static"), name="static")
app.include_router(system.router)
app.include_router(search.router)
app.include_router(download.router)
app.include_router(library.router)
app.include_router(log.router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", DEFAULT_HOST),
        port=int(os.getenv("APP_PORT", DEFAULT_PORT)),
        reload=True,
    )
