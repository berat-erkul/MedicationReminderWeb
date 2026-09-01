# CLAUDE.md — İlaç Hatırlatıcı (backend + web panel)

Aile için self-hosted ilaç hatırlatma sistemi. Bu repo **backend (FastAPI)** ve
**web panel (Next.js)** içerir. Android app ayrı repo: `../ilaç-hatırlatıcı-mobil`.

**Canlı:** `https://ilac.beraterkul.com.tr` — VPS'te, Cloudflare Tunnel arkasında.
**Sahibi:** Berat Erkul. Kullanıcılar: aile bireyleri (ilaç alanlar) + Berat (takip).

> `readme.md` ve `docs/deployment.md` **eskidir** (WhatsApp/Baileys/home-server/
> Tailscale döneminden). Güncel gerçek: bu dosya. Ayrıntılı mimari + karar
> günlüğü: Obsidian vault `01_Projects/Ilac-Hatirlatici/`.

---

## 1. Ne yapıyor

- Her ilaç için kişiye **saat + tekrar** (her gün / haftanın belirli günleri) atanır.
- Doz vakti → kişiye **Telegram** mesajı (butonlu), aileye **ntfy push**.
- Kişi cevaplamazsa Telegram'dan sıkıştırılır; 5 saat sonra "kaçırıldı" + Berat'a uyarı.
- Haftalık **AI uyum özeti** (OpenRouter, ücretsiz model).

Hasta uygulama kurmaz — sadece Telegram'dan buton/yazı ile cevap verir.
Bakıcı(lar) Android app'ten programı yönetir + push alır.

---

## 2. Çalıştırma

```bash
# Lokal (Mac) — backend + frontend + ntfy, auth kapalı
cp .env.example .env        # TELEGRAM_BOT_TOKEN doldur (test botu öner)
docker compose up -d
# http://localhost:8000/docs · :3000 panel · :8080 ntfy

# VPS — + caddy, ntfy deny-all
docker compose --profile remote up -d
```

**Backend testleri:**
```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check .        # E, F, I — line-length 100, E501/E712 ignore
.venv/bin/pytest -q           # tests/ — saf mantık, network/DB YOK
```

**Frontend:** `cd frontend && npm ci && npm run lint && npm run build`
(`next.config.ts` → `output: "standalone"`, Docker için).

> ⚠️ Telegram bot token'ı tek yerden poll edilebilir. Lokal backend'i canlı
> bot token'ıyla açarsan VPS ile `409 Conflict` çakışır. Lokal testte ya ayrı
> test botu kullan ya `TELEGRAM_BOT_TOKEN=` boş bırak (poller başlamaz,
> `send_message` no-op'lar, state machine yine test edilir).

> ⚠️ macOS: Docker Desktop `~/Desktop`'a bind-mount yapamaz (TCC). Lokal `.env`'de
> `DATA_ROOT=/Users/beraterkul/med-reminder-data` gibi korumasız bir yol ver.

---

## 3. Mimari

```
Next.js panel ─REST─┐                        ┌─Telegram Bot API──▶ hasta
Android app  ─REST──┼──▶ FastAPI (:8000) ────┤   (long polling, NAT-safe)
                    │    ├ APScheduler        └─ntfy (:8080) ─push─▶ bakıcı app
                    │    ├ SQLite (tek dosya)
                    │    └ AIService ──HTTPS──▶ OpenRouter (:free)
              Caddy (:8090) ── /ntfy/* → ntfy, /api/users|admin|dashboard → 404,
                                geri kalan → backend
              cloudflared (host systemd) ──▶ https://ilac.beraterkul.com.tr
```

### Modül haritası (`backend/`)

| Yol | İş |
| --- | --- |
| `main.py` | FastAPI app + lifespan (init_db, scheduler, telegram poller) |
| `api/auth.py` | `POST /api/register` — cihaz self-registration + invite kapısı |
| `api/deps.py` | `get_current_user` (Bearer→User) · `require_admin` (X-Admin-Token) |
| `api/{users,medicines,schedules,reminders,admin}.py` | REST uçları |
| `services/reminder_service.py` | **TÜM hatırlatma iş kuralı** (§4) |
| `scheduler/jobs.py` | `job_create_and_send` (cron 1dk) · `job_reminders_tick` (interval 1dk) |
| `messaging/telegram.py` | Telegram Bot API client (sendMessage, getUpdates, buttons) |
| `messaging/poller.py` | long-polling döngüsü → reminder_service'e dispatch |
| `notify/push.py` | ntfy'a JSON publish (fire-and-forget, asla raise etmez) |
| `ai/service.py` | OpenRouter/Ollama abstraction + `:free` fatura kapağı |
| `database/session.py` | engine, `init_db`, **elle migration** (`_migrate`), `get_session` |
| `models/entities.py` | SQLModel tablolar · `models/schemas.py` Pydantic I/O |
| `utils/{config,constants,helpers}.py` | ayarlar · enum'lar/token setleri · saf yardımcılar |

### Veri modeli

```
User ─1:N─ Medicine ─1:N─ Schedule ─1:N─ Reminder
 │  phone = Telegram chat_id, access_token cihaz başına
 └─1:N─ Message  (INBOUND/OUTBOUND audit)
```
`User` cascade delete açık. `Schedule.days_of_week` = "0,1,2" (Mon=0..Sun=6).

---

## 4. Hatırlatma state machine — EN KRİTİK BÖLÜM

`services/reminder_service.py`. Berat bu akışı bizzat tasarladı, **değiştirmeden önce sor.**

### Akış

1. `job_create_and_send` (cron, saniye 0): due `Schedule` → `Reminder(PENDING)`
   açar. Idempotent: `(schedule_id, scheduled_for)` çifti tekrar açılmaz.
2. `send_reminder()`: Telegram mesajı + **3 buton** (`take`/`snooze`/`skip`) + 1 push.
   `status=SENT`, `nag_anchor=now`, `retry_count=0`.
3. `job_reminders_tick` (her 1 dk):
   - `SNOOZED` + `snoozed_until` geçmiş → `resume_from_snooze()` = doz saati o
     anmış gibi taze `send_reminder` (yeni `nag_anchor`).
   - `SENT` → `tick_reminder(reminder, now)`:
     - `elapsed_min >= MISSED_AFTER_MIN (300)` → `mark_missed()`:
       `status=MISSED`, push, **`ADMIN_CHAT_ID`'ye Telegram uyarısı**.
     - değilse `retry_count < nags_due(elapsed_min)` → `send_nag()`:
       Telegram "Lütfen işaretleme yapın." (**butonsuz**), `retry_count += 1`.
   - `NAG_OFFSETS_MIN = (5, 15, 45, 60, 120, 180, 240)` dakika (doz saatinden).

### Cevaplar → `apply_action(action)`

| action | kaynak | sonuç |
| --- | --- | --- |
| `take` | buton `take:<id>` / "aldım","e","tamam" / app `complete?skipped=false` | `COMPLETED`, dur, teyit + push |
| `skip` | buton `skip:<id>` / "almadım","h","yok" / app `complete?skipped=true` | `SKIPPED` (o gün almadı), **dur** |
| `snooze` | buton `snooze:<id>` / "ertele","sonra" / app `POST .../snooze` | `SNOOZED`, `snoozed_until=now+60dk`, sonra taze mesaj. **Sınırsız** tekrar. |

Token setleri: `utils/constants.py` (`POSITIVE_REPLIES` / `NEGATIVE_REPLIES` / `SNOOZE_REPLIES`).

### Push politikası

ntfy push **sadece** anahtar olaylarda: doz vakti / alındı / almadı / ertelendi /
kaçırıldı. **Dakikalık sıkıştırma push'a gitmez** — nag Telegram-only. (Eski
"her 10 dk push spam" kaldırıldı.)

### nag_anchor neden var

`retry_count` = "bu anchor'dan beri kaç nag". Ertele'de anchor ertele-bitişine
kayar, `retry_count` sıfırlanır → döngü gerçekten baştan başlar. `elapsed_min`
her zaman `nag_anchor or sent_at` üzerinden, `_aware()` ile tz-normalize.

---

## 5. Güvenlik / erişim

Public deployment'ta üç kapı — hepsi env ile, boşken açık ama **her istekte uyarı loglar**:

| Env | Etkisi |
| --- | --- |
| `REGISTRATION_SECRET` | set → `POST /api/register` eşleşen `invite_code` ister (403). `secret_ok()` sabit-zamanlı. |
| `ADMIN_TOKEN` | set → `/api/users*`, `/api/admin*`, `/api/dashboard*` → `X-Admin-Token` (403). `require_admin`. |
| `NTFY_AUTH_DEFAULT_ACCESS=deny-all` | ntfy topic'e token'sız erişim 403. Token: `scripts/ntfy-setup.sh`. |

Ek: Caddy o operator path'lerini public tünelde **404**'ler (`@operator` matcher).
Panel'e erişim: `ssh -L 3000:localhost:3000 -L 8000:localhost:8000 VPS`.

`ADMIN_CHAT_ID` = Berat'ın chat_id'si (`6551014188`) → kaçırılan dozda ona Telegram.

---

## 6. Deployment (VPS)

- **Sunucu:** `admin@195.85.207.211` (Ubuntu 24.04). SSH alias: `ssh VPS`.
- **Yol:** `~/production/med-reminder` (bu repo, `main` branch).
- **Veri:** `~/production/med-data/{backend,ntfy}` (repo dışı, `DATA_ROOT`).
- **Cloudflare Tunnel:** `portfolio-vps` (portfolio ile ortak!). Ingress:
  `beraterkul.com.tr → localhost:80` (portfolio), `ilac.beraterkul.com.tr →
  localhost:8090` (bu proje). cloudflared host'ta systemd — **container çalıştırma.**
- Cloudflare değişikliği: `cloudflare-api` MCP (plugin `cloudflare@cloudflare`).
- Portlar hep `127.0.0.1`'e bind → dışarı kapalı.

### CI/CD

`.github/workflows/ci-cd.yml`:
- her push/PR → backend (ruff+pytest) + frontend (lint+build), GitHub-hosted
- **`main` push** → `appleboy/ssh-action` → VPS'te `git checkout -B main origin/main`
  + `docker compose --profile remote up -d --build` + `/health`
- Secrets: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` (kısıtlı ed25519), `VPS_APP_DIR`

Deploy güvenli mi: **evet, şu değişiklikler için** → bug fix, geriye uyumlu
endpoint, `_migrate`'in eklediği additive kolon. **Manuel dikkat gerektirir** →
kolon silme/rename, veri dönüşümü, app'in kullandığı endpoint'in kaldırılması.

### Şema migration

**Alembic yok.** `database/session.py::_migrate()` her açılışta çalışır:
`PRAGMA table_info` ile kontrol + `ALTER TABLE ADD COLUMN` (idempotent). Yeni kolon
eklerken bu pattern'e ekle. Rename/drop bu mekanizmayla YAPILAMAZ.

---

## 7. `.env` anahtarları

Şablon: `.env.example`. Kritikler:

| Anahtar | Not |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | @BotFather. Bot: `@ecazci_bot` |
| `REGISTRATION_SECRET` / `ADMIN_TOKEN` / `NTFY_TOKEN` | §5 |
| `ADMIN_CHAT_ID` | kaçırılan dozda uyarı gidecek chat_id |
| `DATA_ROOT` | VPS'te repo dışı absolute yol |
| `NTFY_AUTH_DEFAULT_ACCESS` | lokal `read-write`, VPS `deny-all` |
| `OPENROUTER_API_KEY` | https://openrouter.ai → Keys |
| `OPENROUTER_MODEL` | **`:free` ile bitmeli**. Şu an `liquid/lfm-2.5-2.6b:free` (hızlı ~5s). Büyük modeller 20s+ → mobil timeout. |
| `OPENROUTER_FREE_ONLY=true` | `:free` olmayan modeli API'ye göndermez (fatura kapağı, test edilmiş) |
| `NTFY_BASE_URL` | **path İÇERMEZ** (`/ntfy` verme, ntfy reddeder). İç adres `http://ntfy:80` yeterli. |

---

## 8. Kod yazarken

- **Türkçe** kullanıcı-facing metin, İngilizce kod/log/commit teknik terimler.
- Kullanıcı-facing mesajlar yaşlı kullanıcıya göre: kısa, net, tek eylem.
- SQLite datetime'ları **tz-naive** döner; `utc_now()` aware. Karşılaştırmadan önce
  `_aware()` (reminder_service) ya da `.replace(tzinfo=UTC)`. Bu bug bir kez ısırdı.
- `notify/push.py` **asla raise etmez** — push hatası hatırlatma akışını bozmamalı.
- Scheduler zaman karşılaştırması `settings.timezone` (Europe/Istanbul) üzerinden,
  sunucu TZ'si değil.
- Yeni endpoint eklersen: mobil app geriye uyumlu mu? (eski APK'lar sahada)
- Testler saf mantık (`tests/`). TestClient/DB entegrasyon testi yok — ekleyeceksen
  ayrı dosya + fixture.
- Anlamlı iş bitince commit. `main`'e push = otomatik prod deploy — branch + PR kullan.

---

## 9. Bilinen açık işler

- [ ] `readme.md` + `docs/deployment.md` eski — güncelle ya da sil
- [ ] Web panel user-scoped sayfaları (medicines/schedules/reminders/weekly)
      izolasyon değişikliğinden beri Bearer token göndermiyor → 401. Panel
      operatör-only + düşük öncelik. Düzgün admin konsolu = ayrı iş.
- [ ] SQLite yedek cron'u (`~/production/med-data/backend/medication.db` → VPS dışı)
- [ ] `com.example.med_reminder_app` paket adı (kozmetik)
- [ ] `admin.py` / `dashboard_stats` SNOOZED durumunu "pending" saymıyor (kozmetik)
- [ ] Node 20 deprecation uyarısı CI'da (actions/*@v4 → v5)
