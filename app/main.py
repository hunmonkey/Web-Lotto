"""앱을 세운다. 첫 화면(/) 과 상태 확인(/healthz). 기능은 여기서부터 더한다."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Web-Lotto", docs_url=None, redoc_url=None, openapi_url=None)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
