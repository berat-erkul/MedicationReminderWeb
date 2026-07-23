"use client";

import { FormEvent, useState } from "react";

type Field = {
  name: string;
  label: string;
  placeholder?: string;
  type?: string;
  required?: boolean;
};

type Props = {
  title: string;
  fields: Field[];
  submitLabel: string;
  onSubmit: (values: Record<string, string>) => Promise<void>;
};

export function CreateForm({ title, fields, submitLabel, onSubmit }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const form = new FormData(e.currentTarget);
    const values: Record<string, string> = {};
    fields.forEach((f) => {
      values[f.name] = String(form.get(f.name) || "").trim();
    });
    try {
      await onSubmit(values);
      e.currentTarget.reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kayıt başarısız");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel form-panel" onSubmit={handleSubmit}>
      <h2>{title}</h2>
      <div className="form-grid">
        {fields.map((field) => (
          <label key={field.name} className="field">
            <span>{field.label}</span>
            <input
              name={field.name}
              type={field.type || "text"}
              placeholder={field.placeholder}
              required={field.required !== false}
            />
          </label>
        ))}
      </div>
      {error && <p className="form-error">{error}</p>}
      <button type="submit" className="btn" disabled={busy}>
        {busy ? "Kaydediliyor…" : submitLabel}
      </button>
    </form>
  );
}
