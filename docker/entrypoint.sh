#!/bin/sh
# 컨테이너가 켜질 때 하는 일. 줄끝은 LF 여야 한다(.gitattributes).
#
# 웹 서버는 root 로 돌지 않는다. Unraid 관례대로 nobody(99):users(100) 로 돈다(MEW · QnA 와 같다).
# 자료 폴더(/srv/data)에는 SQLite(lotto.sqlite)가 쌓인다. 켤 때마다 주인을 맞춘다.
set -e

mkdir -p /srv/data
chown -R 99:100 /srv/data 2>/dev/null || true

echo "[Lotto] 웹 서버를 켭니다. (안쪽 7682 · 바깥 포트는 .env 의 APP_PORT)"

# --proxy-headers · --forwarded-allow-ips: 앞의 NPM 이 https 를 받고 http 로 넘겨준다. 도커 사설 대역만 믿는다.
# --workers 1: 로그인 잠금 횟수를 프로세스 메모리에 두므로 일꾼을 늘리면 횟수가 프로세스마다 따로 센다. 한 사람이 쓰는 사이트라 하나로 충분하다.
exec setpriv --reuid=99 --regid=100 --clear-groups \
    uvicorn app.main:app --host 0.0.0.0 --port 7682 --workers 1 --proxy-headers \
    --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-172.16.0.0/12}" --no-server-header
