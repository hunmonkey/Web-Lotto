#!/bin/sh
# 운영 서버(Unraid 환인)에서 새 판을 올리는 한 묶음. Rule_Project_Etc.txt 0장의 정본.
#
# 쓰는 법 - 서버의 /mnt/user/appdata/Web-Lotto 에서, git 을 origin/main 에 맞춘 '뒤에':
#     git fetch && git reset --hard origin/main && sh scripts/deploy.sh
# ★ git 맞추기는 이 파일 밖에서 한다. 돌고 있는 스크립트 파일을 git 이 덮어쓰면 셸이 엉뚱한 줄을 읽는다.
#
# 하는 일: 이미지 굽기 → 올리기 → healthy 기다리기 → 굽고 남은 이름 없는 옛 lotto 이미지 걷기.
set -eu
cd "$(dirname "$0")/.."

docker compose build app
docker compose up -d app

i=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' Web-Lotto-app)" = healthy ]; do
  i=$((i + 1))
  if [ "$i" -gt 24 ]; then
    echo '!!! 2분이 지나도 Web-Lotto-app 이 healthy 가 아닙니다. docker logs Web-Lotto-app 를 보세요.'
    exit 1
  fi
  sleep 5
done
echo "Web-Lotto-app healthy ($((i * 5))초)"

docker image prune -f --filter label=com.docker.compose.project=lotto
echo "남은 댕글링 이미지(서버 전체): $(docker images -f dangling=true -q | wc -l)개"
