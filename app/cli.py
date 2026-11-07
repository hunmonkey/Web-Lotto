"""명령줄 도구.  쓰는 법:  .venv/Scripts/python.exe -m app.cli hash-password"""
import getpass
import sys

from app.auth import hash_password


def main(argv: list[str]) -> int:
    if argv[:1] == ["hash-password"]:
        pw = getpass.getpass("새 비밀번호(8자 이상): ")
        if len(pw) < 8:
            print("8자 이상으로 해 주세요.")
            return 1
        if pw != getpass.getpass("한 번 더: "):
            print("두 번 입력이 달라요.")
            return 1
        print(".env 의 LOGIN_PASSWORD_HASH 에 아래 한 줄을 붙이세요(작은따옴표까지 그대로. $ 가 많아 따옴표가 없으면 깨집니다):")
        print(f"LOGIN_PASSWORD_HASH='{hash_password(pw)}'")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
