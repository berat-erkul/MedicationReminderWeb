# AI WhatsApp Medication Reminder

Self-hosted ilaç hatırlatma sistemi. Yaşlı kullanıcılar WhatsApp'tan kısa cevap verir (`e` / `h` / `aldım` / `almadım`); yanıt gelmezse otomatik takip mesajı gider. Aile paneli home-server'da çalışır.

## Mimari

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Next.js    │────▶│   FastAPI    │────▶│  Baileys    │──▶ hasta (WhatsApp)
│  Admin UI   │     │  + Scheduler │     │  WhatsApp   │
└─────────────┘     └──┬────────┬──┘     └─────────────┘
                       │        │
              ┌────────▼──┐  ┌──▼─────┐
              │ SQLite +  │  │  ntfy  │──▶ bakıcı (mobil APK bildirimi)
              │ AI (OpenR)│  │  push  │
              └───────────┘  └────────┘
```

İlaç vakti geldiğinde: **hasta** WhatsApp mesajı alır, **bakıcı** telefonuna
ntfy push bildirimi düşer. Hasta `e`/`h` yanıtı verince bakıcıya sonuç bildirimi gider.

## Hızlı başlangıç (home-server)

```bash
cp .env.example .env
# NEXT_PUBLIC_API_URL=http://SENIN_IP:8000

chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

| Servis   | URL |
|----------|-----|
| Panel    | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| WhatsApp | `docker compose logs -f whatsapp` → QR tara |

Detay: [docs/deployment.md](docs/deployment.md)

## Yerel geliştirme

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### WhatsApp

```bash
cd whatsapp
npm install
BACKEND_WEBHOOK_URL=http://localhost:8000/api/webhooks/whatsapp npm start
```

## Hatırlatma akışı

1. Scheduler her dakika due schedule bulur
2. WhatsApp mesajı gönderilir
3. Kullanıcı `e` / `aldım` → completed, `h` / `almadım` → skipped
4. Yanıt yoksa 5 / 15 / 30 dk sonra tekrar
5. Max deneme sonrası → missed (+ opsiyonel admin bildirimi)

## Proje yapısı

```text
backend/     FastAPI, SQLModel, APScheduler, AI, ntfy push
frontend/    Next.js admin paneli
whatsapp/    Baileys gateway (Node.js)
docker/      Compose tanımı (backend, frontend, whatsapp, ntfy, ollama)
docs/        Deployment notları
scripts/     Home-server deploy
.github/     CI/CD workflow
```

## CI/CD

`.github/workflows/ci-cd.yml` hazır:

- **PR / push**: backend ruff + pytest, frontend lint + build
- **`main` push**: self-hosted runner'da otomatik `docker compose up -d --build` + health check

Kurulum: [docs/deployment.md](docs/deployment.md#cicd-github-actions)

## Tasarım hedefleri

Self-hosted · privacy-first · yaşlı kullanıcı için minimal etkileşim · AI gözlemleri · modüler yapı
