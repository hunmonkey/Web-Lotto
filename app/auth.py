"""비밀번호 하나로 들어오는 로그인. 서명한 쿠키 한 개가 세션이다(서버에 두지 않는다)."""
import threading
import time

import bcrypt
from fastapi import HTTPException, Request
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import settings

COOKIE = "lotto_session"
FAIL_WINDOW = 600   # 초. 이 안에 실패가 이만큼 쌓이면 잠근다
FAIL_PER_IP = 5
FAIL_TOTAL = 30     # 주소가 달라도 전체가 이만큼이면 잠근다(여러 주소로 두드리는 것을 막는다)

_signer = URLSafeTimedSerializer(settings.secret_key or "unset", salt="lotto-session")
_fails: dict[str, list[float]] = {}
_lock = threading.Lock()


def _pw_bytes(pw: str) -> bytes:
    return pw.encode()[:72]  # bcrypt 는 앞 72바이트만 본다(5.x 는 더 길면 오류)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(_pw_bytes(pw), bcrypt.gensalt()).decode()


def check_password(pw: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(pw), settings.login_password_hash.encode())
    except ValueError:  # 해시가 깨졌을 때
        return False


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def is_locked(ip: str) -> bool:
    now = time.time()
    with _lock:
        for k in list(_fails):
            _fails[k] = [t for t in _fails[k] if now - t < FAIL_WINDOW]
            if not _fails[k]:
                del _fails[k]
        return len(_fails.get(ip, [])) >= FAIL_PER_IP or sum(map(len, _fails.values())) >= FAIL_TOTAL


def record_fail(ip: str) -> None:
    with _lock:
        _fails.setdefault(ip, []).append(time.time())


def clear_fails(ip: str) -> None:
    with _lock:
        _fails.pop(ip, None)


def make_session() -> str:
    return _signer.dumps({"u": 1})


def is_logged_in(request: Request) -> bool:
    token = request.cookies.get(COOKIE)
    if not token:
        return False
    try:
        _signer.loads(token, max_age=settings.session_max_hours * 3600)
        return True
    except BadSignature:  # 만료(SignatureExpired)도 여기 든다
        return False


def api_guard(request: Request) -> None:
    """JSON 길 공통 문지기. 로그인했는지, 그리고 바꾸는 요청은 우리 화면에서 보냈는지(X-Requested-With)."""
    if not is_logged_in(request):
        raise HTTPException(401, "로그인이 필요해요")
    if request.method not in ("GET", "HEAD") and request.headers.get("x-requested-with") != "fetch":
        raise HTTPException(403, "요청이 올바르지 않아요")
