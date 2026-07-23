"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, Medicine, Schedule, User } from "@/lib/api";

const WEEKDAYS = [
  ["1", "Pzt"],
  ["2", "Sal"],
  ["3", "Çar"],
  ["4", "Per"],
  ["5", "Cum"],
  ["6", "Cmt"],
  ["0", "Paz"],
];

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [recurrence, setRecurrence] = useState("daily");
  const [days, setDays] = useState<string[]>([]);

  function load() {
    Promise.all([api.schedules.list(), api.users.list(), api.medicines.list()])
      .then(([s, u, m]) => {
        setSchedules(s);
        setUsers(u);
        setMedicines(m);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Yüklenemedi"));
  }

  useEffect(load, []);

  const userName = (id: number) => users.find((u) => u.id === id)?.name ?? `#${id}`;
  const medName = (id: number) => medicines.find((m) => m.id === id)?.name ?? `#${id}`;

  function toggleDay(d: string) {
    setDays((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]));
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const form = new FormData(e.currentTarget);
    try {
      await api.schedules.create({
        user_id: Number(form.get("user_id")),
        medicine_id: Number(form.get("medicine_id")),
        time: String(form.get("time")),
        recurrence,
        days_of_week: recurrence === "weekly" ? days.join(",") : undefined,
      });
      e.currentTarget.reset();
      setDays([]);
      setRecurrence("daily");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kayıt başarısız");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    if (!confirm("Bu programı silmek istediğinize emin misiniz?")) return;
    await api.schedules.remove(id);
    load();
  }

  const canCreate = users.length > 0 && medicines.length > 0;

  return (
    <div>
      <h1 className="page-title">Program</h1>
      <p className="page-lead">
        Hangi kişiye, hangi ilacın, saat kaçta hatırlatılacağını belirle. Scheduler her dakika kontrol
        eder ve zamanı gelince WhatsApp + telefon bildirimi gönderir.
      </p>

      {error && <p className="form-error">{error}</p>}

      <div className="grid-2">
        <form className="panel form-panel" onSubmit={handleSubmit}>
          <h2>Yeni program</h2>
          {!canCreate ? (
            <p className="empty">Önce en az bir kişi ve bir ilaç eklemelisin.</p>
          ) : (
            <>
              <div className="form-grid">
                <label className="field">
                  <span>Kişi</span>
                  <select name="user_id" required>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>İlaç</span>
                  <select name="medicine_id" required>
                    {medicines.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} {m.dosage ? `(${m.dosage})` : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span>Saat</span>
                  <input name="time" type="time" required defaultValue="09:00" />
                </label>
                <label className="field">
                  <span>Tekrar</span>
                  <select value={recurrence} onChange={(e) => setRecurrence(e.target.value)}>
                    <option value="daily">Her gün</option>
                    <option value="weekly">Haftanın belirli günleri</option>
                  </select>
                </label>
              </div>

              {recurrence === "weekly" && (
                <div className="days-row">
                  {WEEKDAYS.map(([val, label]) => (
                    <button
                      type="button"
                      key={val}
                      className={days.includes(val) ? "day-chip active" : "day-chip"}
                      onClick={() => toggleDay(val)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}

              <button type="submit" className="btn" disabled={busy}>
                {busy ? "Kaydediliyor…" : "Program ekle"}
              </button>
            </>
          )}
        </form>

        <section className="panel">
          <h2>Aktif programlar</h2>
          {schedules.length === 0 ? (
            <p className="empty">Henüz program yok.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Kişi</th>
                  <th>İlaç</th>
                  <th>Saat</th>
                  <th>Tekrar</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((s) => (
                  <tr key={s.id}>
                    <td>{userName(s.user_id)}</td>
                    <td>{medName(s.medicine_id)}</td>
                    <td>{s.time.slice(0, 5)}</td>
                    <td>{s.recurrence === "weekly" ? s.days_of_week : "her gün"}</td>
                    <td>
                      <button className="btn-ghost" onClick={() => remove(s.id)}>
                        Sil
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
