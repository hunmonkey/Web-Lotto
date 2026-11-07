"""설정. .env (또는 환경변수)에서 읽는다. 보기틀은 .env.example."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = ""            # 쿠키 서명용 비밀값
    login_password_hash: str = ""   # 로그인 비밀번호의 bcrypt 해시
    session_max_hours: int = 12
    session_cookie_secure: bool = True   # https 에서만 쿠키. 개발 PC 의 http 에서만 false
    data_dir: Path = Path("data")        # SQLite 파일이 쌓이는 곳


settings = Settings()
