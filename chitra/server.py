"""Local web UI + JSON API. Binds to 127.0.0.1 only."""

import io
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .config import BROWSER_EXTS
from .imaging import to_jpeg_bytes
from .search import Searcher

STATIC = Path(__file__).parent / "static"


def reveal_in_file_manager(path: Path) -> None:
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


def create_app(searcher: Searcher) -> FastAPI:
    app = FastAPI(title="Chitra", docs_url="/api/docs")
    store = searcher.store
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def get_or_404(image_id: int) -> dict:
        info = store.get(image_id)
        if not info:
            raise HTTPException(404, "Image not found")
        return info

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/stats")
    def stats():
        return {"root": str(store.root), "count": len(searcher), "failed": store.failure_count(), "model": searcher.model_name}

    @app.get("/api/search")
    def search(q: str, k: int = 60, year_from: Optional[int] = None, year_to: Optional[int] = None):
        q = q.strip()
        if not q:
            return {"results": []}
        return {"results": searcher.search_text(q, k, year_from=year_from, year_to=year_to)}

    @app.post("/api/search-image")
    async def search_image(file: UploadFile = File(...), k: int = 60):
        try:
            image = Image.open(io.BytesIO(await file.read()))
        except Exception:
            raise HTTPException(400, "Could not read that image")
        return {"results": searcher.search_image(image, k)}

    @app.get("/api/similar/{image_id}")
    def similar(image_id: int, k: int = 60):
        get_or_404(image_id)
        return {"results": searcher.similar(image_id, k)}

    @app.get("/api/thumb/{image_id}")
    def thumb(image_id: int):
        path = store.thumb_path(get_or_404(image_id)["path"])
        if not path.exists():
            raise HTTPException(404, "Thumbnail missing")
        return FileResponse(path, headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/image/{image_id}")
    def image(image_id: int):
        path = store.abspath(get_or_404(image_id)["path"])
        if not path.exists():
            raise HTTPException(404, "File is no longer on disk")
        if path.suffix.lower() in BROWSER_EXTS:
            return FileResponse(path)
        return Response(to_jpeg_bytes(path), media_type="image/jpeg")

    @app.post("/api/open/{image_id}")
    def open_in_folder(image_id: int):
        path = store.abspath(get_or_404(image_id)["path"])
        if not path.exists():
            raise HTTPException(404, "File is no longer on disk")
        reveal_in_file_manager(path)
        return {"ok": True}

    return app
