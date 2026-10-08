#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
chat_model=${1:-qwen3:0.6b}
embedding_model=${2:-qwen3-embedding:0.6b}
for model in "$chat_model" "$embedding_model"; do
  [[ "$model" =~ ^[a-zA-Z0-9._:/-]+$ ]] || { echo '模型名称格式无效'; exit 1; }
done
if [ ! -f .env ]; then cp .env.example .env; fi
docker compose --profile models up -d ollama
ready=false
for i in $(seq 1 30); do
  if docker compose exec -T ollama ollama list >/dev/null 2>&1; then ready=true; break; fi
  sleep 2
done
$ready || { echo 'Ollama 未就绪'; exit 1; }
docker compose exec -T ollama ollama pull "$chat_model"
docker compose exec -T ollama ollama pull "$embedding_model"
cp .env .env.before-models
sed '/^\(CHAT_MODEL\|EMBEDDING_MODEL\|OLLAMA_URL\)=/d' .env > .env.next
printf 'CHAT_MODEL=%s\nEMBEDDING_MODEL=%s\nOLLAMA_URL=http://ollama:11434\n' "$chat_model" "$embedding_model" >> .env.next
mv .env.next .env
bash scripts/start.sh
