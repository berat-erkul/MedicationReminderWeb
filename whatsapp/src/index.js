import express from "express";
import cors from "cors";
import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
} from "@whiskeysockets/baileys";
import qrcode from "qrcode-terminal";
import pino from "pino";
import fs from "fs";

const PORT = Number(process.env.PORT || 3001);
const BACKEND_WEBHOOK =
  process.env.BACKEND_WEBHOOK_URL || "http://backend:8000/api/webhooks/whatsapp";
const AUTH_DIR = process.env.AUTH_DIR || "./auth_info";
const logger = pino({ level: process.env.LOG_LEVEL || "info" });

fs.mkdirSync(AUTH_DIR, { recursive: true });

const app = express();
app.use(cors());
app.use(express.json());

let sock = null;
let connectionStatus = "starting";
let lastQr = null;

function normalizePhone(phone) {
  return String(phone || "").replace(/\D/g, "");
}

function toJid(phone) {
  const digits = normalizePhone(phone);
  return digits.includes("@") ? digits : `${digits}@s.whatsapp.net`;
}

async function forwardToBackend(phone, content, raw) {
  try {
    const res = await fetch(BACKEND_WEBHOOK, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        phone: normalizePhone(phone),
        content,
        raw_payload: JSON.stringify(raw),
      }),
    });
    if (!res.ok) {
      logger.warn({ status: res.status }, "Backend webhook failed");
    }
  } catch (err) {
    logger.error({ err }, "Backend webhook error");
  }
}

async function startWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: state,
    logger: pino({ level: "silent" }),
    printQRInTerminal: false,
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      lastQr = qr;
      connectionStatus = "qr";
      logger.info("Scan QR code with WhatsApp:");
      qrcode.generate(qr, { small: true });
    }

    if (connection === "open") {
      connectionStatus = "connected";
      lastQr = null;
      logger.info("WhatsApp connected");
    }

    if (connection === "close") {
      const code = lastDisconnect?.error?.output?.statusCode;
      logger.warn({ code }, "WhatsApp disconnected");
      if (code === DisconnectReason.loggedOut) {
        // Session invalidated (401): wipe stale creds so a fresh QR is shown
        // instead of getting stuck logged out.
        connectionStatus = "logged_out";
        try {
          fs.rmSync(AUTH_DIR, { recursive: true, force: true });
          fs.mkdirSync(AUTH_DIR, { recursive: true });
        } catch (err) {
          logger.error({ err }, "Failed to clear auth dir");
        }
        startWhatsApp();
      } else {
        connectionStatus = "reconnecting";
        startWhatsApp();
      }
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      if (msg.key.fromMe) continue;
      const remoteJid = msg.key.remoteJid || "";
      if (remoteJid.endsWith("@g.us") || remoteJid === "status@broadcast") continue;

      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        "";

      if (!text.trim()) continue;

      const phone = remoteJid.split("@")[0];
      logger.info({ phone, text }, "Incoming WhatsApp message");
      await forwardToBackend(phone, text.trim(), msg);
    }
  });
}

app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "whatsapp", connection: connectionStatus });
});

app.get("/status", (_req, res) => {
  res.json({
    connection: connectionStatus,
    hasQr: Boolean(lastQr),
    qr: lastQr,
  });
});

app.post("/send", async (req, res) => {
  try {
    const { phone, message } = req.body || {};
    if (!phone || !message) {
      return res.status(400).json({ error: "phone and message are required" });
    }
    if (!sock || connectionStatus !== "connected") {
      return res.status(503).json({ error: "WhatsApp not connected", connection: connectionStatus });
    }

    const jid = toJid(phone);
    await sock.sendMessage(jid, { text: message });
    return res.json({ ok: true, phone: normalizePhone(phone) });
  } catch (err) {
    logger.error({ err }, "Send failed");
    return res.status(500).json({ error: "send_failed", detail: String(err) });
  }
});

app.listen(PORT, () => {
  logger.info(`WhatsApp service listening on :${PORT}`);
  startWhatsApp().catch((err) => {
    logger.error({ err }, "Failed to start WhatsApp");
    connectionStatus = "error";
  });
});
