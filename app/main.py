"""앱을 세운다. 화면(/ · /login) · 상태 확인(/healthz) · JSON 길(/api/...)."""
import io
import time
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from app import auth, store
from app.config import settings
from app.services import excel, generate

if not settings.secret_key or not settings.login_password_hash:
    raise RuntimeError(".env 에 SECRET_KEY 와 LOGIN_PASSWORD_HASH 를 채워 주세요 (.env.example 참고)")

BASE = Path(__file__).parent
STATIC_V = str(int(time.time()))  # 정적 파일 주소에 붙여 새 판을 바로 받게 한다
MAX_UPLOAD = 5 * 1024 * 1024

app = FastAPI(title="Web-Lotto", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
store.init()

CSP = "default-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    h = resp.headers
    h["Content-Security-Policy"] = CSP
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "same-origin"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    h["X-Robots-Tag"] = "noindex, nofollow"
    if settings.session_cookie_secure:
        h["Strict-Transport-Security"] = "max-age=31536000"
    if not request.url.path.startswith("/static/"):
        h["Cache-Control"] = "no-store"
    return resp


# ---------- 화면 ----------
@app.get("/healthz", response_class=PlainTextResponse)
def healthz() -> str:
    return "ok"


def _login_page(request: Request, error: str = "", status_code: int = 200):
    return templates.TemplateResponse(request, "login.html", {"error": error, "v": STATIC_V}, status_code=status_code)


@app.get("/login")
def login_page(request: Request):
    if auth.is_logged_in(request):
        return RedirectResponse("/", 303)
    return _login_page(request)


@app.post("/login")
def login(request: Request, password: str = Form("")):
    ip = auth.client_ip(request)
    if auth.is_locked(ip):
        return _login_page(request, "실패가 많아 잠시 막았어요. 10분 뒤에 다시 시도해 주세요.", 429)
    if not auth.check_password(password):
        auth.record_fail(ip)
        return _login_page(request, "비밀번호가 맞지 않아요.", 401)
    auth.clear_fails(ip)
    resp = RedirectResponse("/", 303)
    resp.set_cookie(
        auth.COOKIE, auth.make_session(), max_age=settings.session_max_hours * 3600,
        httponly=True, samesite="lax", secure=settings.session_cookie_secure,
    )
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", 303)
    resp.delete_cookie(auth.COOKIE)
    return resp


@app.get("/")
def index(request: Request):
    if not auth.is_logged_in(request):
        return RedirectResponse("/login", 303)
    boot = {"favs": store.list_favs(), "historyTotal": store.round_stats()["total"]}
    return templates.TemplateResponse(request, "index.html", {"boot": boot, "v": STATIC_V})


# ---------- JSON 길 (로그인 필요) ----------
guard = [Depends(auth.api_guard)]


def _check_nums(v: list[int]) -> list[int]:
    if any(not 1 <= n <= 45 for n in v) or len(set(v)) != len(v):
        raise ValueError("번호는 1~45 에서 서로 다르게 골라야 해요")
    return sorted(v)


class GameIn(BaseModel):
    nums: list[int] = Field(default_factory=list, max_length=6)
    _ok = field_validator("nums")(classmethod(lambda cls, v: _check_nums(v)))


class GenerateIn(BaseModel):
    mode: Literal["random", "stats", "wish"]
    kind: Literal["random", "hot", "cold", "mix"] = "random"
    games: list[GameIn] = Field(min_length=1, max_length=5)


class FavIn(BaseModel):
    nums: list[int] = Field(min_length=6, max_length=6)
    _ok = field_validator("nums")(classmethod(lambda cls, v: _check_nums(v)))


@app.post("/api/generate", dependencies=guard)
def api_generate(body: GenerateIn):
    try:
        games, fallback = generate.make(
            body.mode, body.kind, [g.nums for g in body.games], store.frequency(), store.round_stats()["total"] > 0
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"games": games, "fallback": fallback}


@app.get("/api/history", dependencies=guard)
def api_history(limit: int = Query(100, ge=1, le=500)):
    return {"total": store.round_stats()["total"], "rows": store.list_rounds(limit)}


@app.post("/api/history/upload", dependencies=guard)
def api_upload(file: UploadFile):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, ".xlsx 파일만 올릴 수 있어요. 다른 형식이면 엑셀에서 '다른 이름으로 저장'으로 xlsx 로 바꿔 주세요.")
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "파일이 너무 커요(5MB 까지).")
    try:
        rows, skipped = excel.read_rounds(io.BytesIO(data))
    except ValueError as e:
        raise HTTPException(400, str(e))
    added, updated = store.upsert_rounds(rows)
    return {
        "added": added, "updated": updated, "skipped": skipped, "total": store.round_stats()["total"],
        "first": rows[0]["round"], "last": rows[-1]["round"],
    }


@app.get("/api/favorites", dependencies=guard)
def api_favs():
    return {"favs": store.list_favs()}


@app.post("/api/favorites", dependencies=guard)
def api_fav_add(body: FavIn):
    store.add_fav(body.nums)
    return {"favs": store.list_favs()}


@app.delete("/api/favorites/{fav_id}", dependencies=guard)
def api_fav_del(fav_id: int):
    store.del_fav(fav_id)
    return {"favs": store.list_favs()}
