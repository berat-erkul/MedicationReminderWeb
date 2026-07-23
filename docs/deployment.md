# Home-server deployment

## Hızlı başlangıç

```bash
cp .env.example .env
# 1) NEXT_PUBLIC_API_URL → home-server IP'n, örn:
#    NEXT_PUBLIC_API_URL=http://192.168.1.50:8000
# 2) OPENROUTER_API_KEY → https://openrouter.ai → Keys

chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

## WhatsApp bağlama

1. `docker compose logs -f whatsapp`
2. Terminalde çıkan QR kodu telefonundaki WhatsApp → Bağlı Cihazlar ile tara
3. `http://HOME_IP:3001/status` → `"connection": "connected"` olmalı

## Push bildirimleri (ntfy → mobil app)

ntfy tamamen home-server'da çalışır, API key gerekmez.

- Topic: `NTFY_TOPIC` (varsayılan `medication-reminders`)
- Kişi bazlı topic: `medication-reminders-<user_id>` (bakıcı tek kişiyi izlemek isterse)
- Test: `curl -X POST http://HOME_IP:8000/api/notify/test`

APK yazılana kadar resmi **ntfy** uygulamasıyla (Android/iOS) test edebilirsin:
sunucu URL'i `http://HOME_IP:8080`, topic `medication-reminders`.

Bildirim tetikleyicileri:
| Olay | Öncelik |
|------|---------|
| İlaç zamanı geldi (WhatsApp gönderildi) | normal |
| Kullanıcı "aldım" dedi | düşük |
| Kullanıcı "almadım" dedi | yüksek |
| Yanıt yok → kaçırıldı | acil |

## OpenRouter (AI özeti)

`.env` içinde `AI_PROVIDER=openrouter` ve `OPENROUTER_API_KEY=...`.
Yerel/offline istersen `AI_PROVIDER=ollama` yapıp `docker compose exec ollama ollama pull llama3.2`.

## Servisler

| Servis   | Port  | Açıklama              |
|----------|-------|------------------------|
| frontend | 3000  | Admin paneli           |
| backend  | 8000  | FastAPI + scheduler    |
| whatsapp | 3001  | Baileys gateway        |
| ntfy     | 8080  | Push (mobil bildirim)  |
| ollama   | 11434 | Yerel AI (opsiyonel)   |

## Veri kalıcılığı

- `data/backend/` — SQLite
- `data/whatsapp/` — WhatsApp oturumu
- `data/ntfy/` — ntfy cache
- `data/ollama/` — modeller

## CI/CD (GitHub Actions)

`.github/workflows/ci-cd.yml`:

1. **PR / push** → backend (ruff + pytest) ve frontend (lint + build) çalışır.
2. **main push** → self-hosted runner'da otomatik deploy (`docker compose up -d --build`).

### Self-hosted runner kurulumu (tek seferlik)

1. GitHub repo → Settings → Actions → Runners → New self-hosted runner.
   Kurarken **label** olarak `home-server` ekle (workflow bunu bekliyor).
2. Runner'ın çalıştığı kullanıcının home dizininde gizli env dosyasını oluştur:
   ```bash
   cp .env.example ~/med-reminder.env
   # gerçek değerleri (OPENROUTER_API_KEY, NEXT_PUBLIC_API_URL) doldur
   ```
   Deploy job bu dosyayı checkout'a `.env` olarak kopyalar — böylece sırlar
   GitHub'a hiç girmez.
3. Runner kullanıcısı `docker` grubunda olmalı (`sudo usermod -aG docker $USER`).

Bundan sonra `main`'e her push otomatik build + deploy eder ve `/health` kontrolü yapar.
