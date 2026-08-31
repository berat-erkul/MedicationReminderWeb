#!/usr/bin/env bash
# ntfy'de 'family' kullanıcısı + kalıcı erişim token'ı oluşturur.
#
# VPS'te, stack ayaktayken BİR KEZ çalıştır:
#   docker compose --profile remote up -d
#   bash scripts/ntfy-setup.sh
#
# Çıktıdaki tk_... token'ını:
#   1) .env  → NTFY_TOKEN=tk_...
#   2) docker compose --profile remote up -d backend   (backend yeniden başlar)
#   3) mobil app Setup ekranı → "ntfy token" alanı
set -euo pipefail
cd "$(dirname "$0")/.."

TOPIC="${NTFY_TOPIC:-medication-reminders}"
NTFY_USER="${NTFY_USER:-family}"

dc() { docker compose "$@"; }

if ! dc exec -T ntfy true 2>/dev/null; then
  echo "HATA: ntfy container ayakta değil. Önce: docker compose --profile remote up -d" >&2
  exit 1
fi

if dc exec -T ntfy ntfy user list 2>/dev/null | grep -qE "^user ${NTFY_USER}\b"; then
  echo "→ '${NTFY_USER}' kullanıcısı zaten var."
else
  PASS="$(openssl rand -base64 24)"
  echo "→ '${NTFY_USER}' kullanıcısı oluşturuluyor (parola kullanılmıyor, token ile erişilecek)..."
  printf '%s\n%s\n' "$PASS" "$PASS" | dc exec -T ntfy ntfy user add "${NTFY_USER}"
fi

echo "→ '${TOPIC}' topic'ine okuma+yazma erişimi..."
dc exec -T ntfy ntfy access "${NTFY_USER}" "${TOPIC}" rw

echo "→ Kalıcı token üretiliyor..."
TOKEN="$(dc exec -T ntfy ntfy token add --expires=never "${NTFY_USER}" | grep -oE 'tk_[A-Za-z0-9_-]+' | head -1)"

if [ -z "${TOKEN}" ]; then
  echo "HATA: token üretilemedi. Elle dene: docker compose exec ntfy ntfy token list ${NTFY_USER}" >&2
  exit 1
fi

cat <<EOF

════════════════════════════════════════════════════════
  NTFY_TOKEN=${TOKEN}
════════════════════════════════════════════════════════
  1) .env dosyasına yaz:  NTFY_TOKEN=${TOKEN}
  2) Backend'i yenile:    docker compose --profile remote up -d backend
  3) Mobil app Setup → "ntfy token" alanına gir
EOF
