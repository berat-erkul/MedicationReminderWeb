"use client";

import { useEffect, useState } from "react";
import { api, Medicine } from "@/lib/api";
import { CreateForm } from "@/components/CreateForm";

export default function MedicinesPage() {
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api.medicines
      .list()
      .then(setMedicines)
      .catch((err) => setError(err instanceof Error ? err.message : "Yüklenemedi"));
  }

  useEffect(load, []);

  async function remove(id: number) {
    if (!confirm("Bu ilacı silmek istediğinize emin misiniz?")) return;
    await api.medicines.remove(id);
    load();
  }

  return (
    <div>
      <h1 className="page-title">İlaçlar</h1>
      <p className="page-lead">İlaç adı ve dozu. Program sayfasında bu ilaçları kişilere saat saat atarsın.</p>

      {error && <p className="form-error">{error}</p>}

      <div className="grid-2">
        <CreateForm
          title="Yeni ilaç"
          submitLabel="İlaç ekle"
          fields={[
            { name: "name", label: "İlaç adı", placeholder: "Tansiyon hapı" },
            { name: "dosage", label: "Doz", placeholder: "1 tablet", required: false },
            { name: "notes", label: "Not", placeholder: "Yemekten sonra", required: false },
          ]}
          onSubmit={async (v) => {
            await api.medicines.create({ name: v.name, dosage: v.dosage, notes: v.notes });
            load();
          }}
        />

        <section className="panel">
          <h2>Kayıtlı ilaçlar</h2>
          {medicines.length === 0 ? (
            <p className="empty">Henüz ilaç yok.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Ad</th>
                  <th>Doz</th>
                  <th>Not</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {medicines.map((m) => (
                  <tr key={m.id}>
                    <td>{m.name}</td>
                    <td>{m.dosage || "—"}</td>
                    <td>{m.notes || "—"}</td>
                    <td>
                      <button className="btn-ghost" onClick={() => remove(m.id)}>
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
