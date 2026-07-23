"use client";

import { useEffect, useState } from "react";
import { api, User } from "@/lib/api";
import { CreateForm } from "@/components/CreateForm";

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.users
      .list()
      .then(setUsers)
      .catch((err) => setError(err instanceof Error ? err.message : "Yüklenemedi"));
  }

  useEffect(load, []);

  async function remove(id: number) {
    if (!confirm("Bu kişiyi silmek istediğinize emin misiniz?")) return;
    await api.users.remove(id);
    load();
  }

  return (
    <div>
      <h1 className="page-title">Kişiler</h1>
      <p className="page-lead">
        İlaç hatırlatması alacak kişiler. Telefon numarası WhatsApp için ülke koduyla girilmeli
        (örn. 905321234567).
      </p>

      {error && <p className="form-error">{error}</p>}

      <div className="grid-2">
        <CreateForm
          title="Yeni kişi"
          submitLabel="Kişi ekle"
          fields={[
            { name: "name", label: "Ad Soyad", placeholder: "Fatma Yılmaz" },
            { name: "phone", label: "Telefon", placeholder: "905321234567" },
          ]}
          onSubmit={async (v) => {
            await api.users.create({ name: v.name, phone: v.phone });
            load();
          }}
        />

        <section className="panel">
          <h2>Kayıtlı kişiler</h2>
          {users.length === 0 ? (
            <p className="empty">Henüz kişi yok.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Ad</th>
                  <th>Telefon</th>
                  <th>Durum</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td>{u.phone}</td>
                    <td>
                      <span className={`badge ${u.is_active ? "completed" : "missed"}`}>
                        {u.is_active ? "aktif" : "pasif"}
                      </span>
                    </td>
                    <td>
                      <button className="btn-ghost" onClick={() => remove(u.id)}>
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
