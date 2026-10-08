#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null || { echo '请先安装并启动 Docker。'; exit 1; }
docker info >/dev/null
if [ ! -f .env ]; then cp .env.example .env; fi
docker compose config --quiet
docker compose up --build -d
task_port=$(sed -n 's/^WEB_PORT=\([0-9]*\)$/\1/p' .env | head -n 1)
task_port=${task_port:-8080}
task_url="http://localhost:$task_port"
for i in $(seq 1 60); do
  if curl --fail --silent "$task_url/api/health" >/dev/null; then
    echo "智学已就绪：$task_url。首次使用请注册账号。"
    exit 0
  fi
  sleep 2
done
echo '服务未就绪，请执行 docker compose logs。'
exit 1
