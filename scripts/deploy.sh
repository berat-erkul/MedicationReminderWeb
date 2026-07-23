#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — home-server IP'ni NEXT_PUBLIC_API_URL olarak güncelle."
fi

mkdir -p data/backend data/whatsapp data/ollama data/ntfy

echo "Building & starting stack..."
docker compose up -d --build

echo ""
echo "Servisler:"
echo "  Frontend : http://localhost:${FRONTEND_PORT:-3000}"
echo "  Backend  : http://localhost:${BACKEND_PORT:-8000}/docs"
echo "  WhatsApp : http://localhost:${WHATSAPP_PORT:-3001}/status"
echo "  ntfy     : http://localhost:${NTFY_PORT:-8080}"
echo ""
echo "WhatsApp QR için  : docker compose logs -f whatsapp"
echo "Push test için    : curl -X POST http://localhost:${BACKEND_PORT:-8000}/api/notify/test"
