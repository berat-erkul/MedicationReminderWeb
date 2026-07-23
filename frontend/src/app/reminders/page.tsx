"use client";

import { useEffect, useState } from "react";
import { api, Reminder, User } from "@/lib/api";

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

const STATUS_TR: Record<string, string> = {
  pending: "bekliyor",
  sent: "gönderildi",
  completed: "alındı",
  skipped: "atlandı",
  missed: "kaçırıldı",
  cancelled: "iptal",
};

export default function RemindersPage() {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    Promise.all([api.reminders.list(), api.users.list()])
      .then(([r, u]) => {
        setReminders(r);
        setUsers(u);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Yüklenemedi"));
  }

  useEffect(load, []);

  const userName = (id: number) => users.find((u) => u.id === id)?.name ?? `#${id}`;

  return (
    <div>
      <h1 className="page-title">Hatırlatmalar</h1>
      <p className="page-lead">Son gönderilen hatırlatmalar ve kullanıcı yanıtlarının durumu.</p>

      {error && <p className="form-error">{error}</p>}

      <section className="panel">
        <h2>Son hatırlatmalar</h2>
        {reminders.length === 0 ? (
          <p className="empty">Henüz hatırlatma yok.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Kişi</th>
                <th>Zaman</th>
                <th>Durum</th>
                <th>Deneme</th>
                <th>Yanıt</th>
              </tr>
            </thead>
            <tbody>
              {reminders.map((r) => (
                <tr key={r.id}>
                  <td>{userName(r.user_id)}</td>
                  <td>{formatWhen(r.scheduled_for)}</td>
                  <td>
                    <span className={`badge ${r.status}`}>{STATUS_TR[r.status] ?? r.status}</span>
                  </td>
                  <td>{r.retry_count}</td>
                  <td>{r.answered_at ? formatWhen(r.answered_at) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
