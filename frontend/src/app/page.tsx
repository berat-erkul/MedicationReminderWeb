"use client";

import { useEffect, useState } from "react";
import { api, DashboardStats, Reminder, WeeklyReport } from "@/lib/api";

function formatWhen(iso: string) {
  try {
    return new Date(iso).toLocaleString("tr-TR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function HomePage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.stats(), api.reminders.list(), api.weeklyReport()])
      .then(([s, r, w]) => {
        setStats(s);
        setReminders(r);
        setReport(w);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Yüklenemedi"));
  }, []);

  return (
    <div>
      <h1 className="page-title">Bugünün özeti</h1>
      <p className="page-lead">
        WhatsApp üzerinden gelen yanıtlar burada görünür. Yaşlı kullanıcılar için tek kelimelik
        cevaplar yeterli: e, h, aldım, almadım.
      </p>

      {error && <p className="form-error">API bağlantısı: {error}</p>}

      <div className="stats">
        {[
          ["Kişiler", stats?.total_users],
          ["Aktif program", stats?.active_schedules],
          ["Bugün", stats?.reminders_today],
          ["Alındı", stats?.completed_today],
          ["Kaçırılan", stats?.missed_today],
          ["Yanıt bekleyen", stats?.pending_replies],
        ].map(([label, value]) => (
          <div className="stat" key={String(label)}>
            <span className="stat-label">{label}</span>
            <span className="stat-value">{value ?? "—"}</span>
          </div>
        ))}
      </div>

      <div className="grid-2">
        <section className="panel">
          <h2>Son hatırlatmalar</h2>
          {reminders.length === 0 ? (
            <p className="empty">Henüz hatırlatma yok.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Zaman</th>
                  <th>Durum</th>
                  <th>Deneme</th>
                </tr>
              </thead>
              <tbody>
                {reminders.slice(0, 8).map((r) => (
                  <tr key={r.id}>
                    <td>{formatWhen(r.scheduled_for)}</td>
                    <td>
                      <span className={`badge ${r.status}`}>{r.status}</span>
                    </td>
                    <td>{r.retry_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel">
          <h2>Haftalık AI gözlemi</h2>
          {report ? (
            <>
              <p className="page-lead" style={{ marginBottom: "0.75rem" }}>
                Uyum oranı: %{report.adherence_rate}
              </p>
              <div className="ai-box">{report.ai_summary}</div>
            </>
          ) : (
            <p className="empty">Rapor yükleniyor…</p>
          )}
        </section>
      </div>
    </div>
  );
}
