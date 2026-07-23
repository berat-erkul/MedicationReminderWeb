const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export type DashboardStats = {
  total_users: number;
  active_schedules: number;
  reminders_today: number;
  completed_today: number;
  missed_today: number;
  pending_replies: number;
};

export type User = {
  id: number;
  name: string;
  phone: string;
  timezone: string;
  is_active: boolean;
  created_at: string;
};

export type Medicine = {
  id: number;
  name: string;
  dosage: string;
  notes: string | null;
  created_at: string;
};

export type Schedule = {
  id: number;
  user_id: number;
  medicine_id: number;
  time: string;
  recurrence: string;
  days_of_week: string | null;
  is_active: boolean;
  created_at: string;
};

export type Reminder = {
  id: number;
  user_id: number;
  schedule_id: number;
  status: string;
  scheduled_for: string;
  sent_at: string | null;
  answered_at: string | null;
  retry_count: number;
  notes: string | null;
  created_at: string;
};

export type WeeklyReport = {
  period_days: number;
  counts: Record<string, number>;
  adherence_rate: number;
  ai_summary: string;
};

export const api = {
  stats: () => request<DashboardStats>("/api/dashboard/stats"),
  users: {
    list: () => request<User[]>("/api/users"),
    create: (body: { name: string; phone: string; timezone?: string }) =>
      request<User>("/api/users", { method: "POST", body: JSON.stringify(body) }),
    remove: (id: number) => request<void>(`/api/users/${id}`, { method: "DELETE" }),
  },
  medicines: {
    list: () => request<Medicine[]>("/api/medicines"),
    create: (body: { name: string; dosage?: string; notes?: string }) =>
      request<Medicine>("/api/medicines", { method: "POST", body: JSON.stringify(body) }),
    remove: (id: number) => request<void>(`/api/medicines/${id}`, { method: "DELETE" }),
  },
  schedules: {
    list: () => request<Schedule[]>("/api/schedules"),
    create: (body: {
      user_id: number;
      medicine_id: number;
      time: string;
      recurrence?: string;
      days_of_week?: string;
    }) => request<Schedule>("/api/schedules", { method: "POST", body: JSON.stringify(body) }),
    remove: (id: number) => request<void>(`/api/schedules/${id}`, { method: "DELETE" }),
  },
  reminders: {
    list: () => request<Reminder[]>("/api/reminders?limit=30"),
  },
  weeklyReport: () => request<WeeklyReport>("/api/reports/weekly"),
};

export { API_URL };
