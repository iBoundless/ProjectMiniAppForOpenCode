import type {
  AgentOption,
  Decision,
  ModelOption,
  ModelRef,
  NotificationSettings,
  PermissionItem,
  Project,
  ServiceStatus,
  Session,
  SessionPage,
  User,
} from "../types/api";
import { api } from "./client";

const enc = encodeURIComponent;

export interface SessionQuery {
  page?: number;
  limit?: number;
  search?: string;
  status?: string;
}

export interface CreateSessionBody {
  directory: string;
  prompt: string;
  model?: ModelRef | null;
  agent?: string | null;
  title?: string | null;
}

export type Delivery = "queue" | "steer";

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const auth = {
  telegram: (initData: string) => api.post<{ user: User }>("/api/auth/telegram", { init_data: initData }),
  me: () => api.get<{ user: User; expires_at: number }>("/api/auth/me"),
  logout: () => api.post<{ ok: boolean }>("/api/auth/logout"),
  loginToken: () => api.post<{ url: string; expires_at: number }>("/api/auth/login-token"),
};

export const sessions = {
  list: (q: SessionQuery = {}) =>
    api.get<SessionPage>(`/api/sessions${query({ ...q })}`),
  get: (id: string) => api.get<Session>(`/api/sessions/${enc(id)}`),
  create: (body: CreateSessionBody) => api.post<Session>("/api/sessions", body),
  prompt: (id: string, body: { text?: string; draft_id?: string; delivery?: Delivery }) =>
    api.post<{ ok: boolean; delivery: Delivery }>(`/api/sessions/${enc(id)}/prompt`, body),
  interrupt: (id: string) => api.post<{ interrupted: boolean }>(`/api/sessions/${enc(id)}/interrupt`),
  remove: (id: string) => api.delete<{ deleted: boolean }>(`/api/sessions/${enc(id)}?confirm=true`),
  subscribe: (id: string) => api.post<{ subscribed: boolean }>(`/api/sessions/${enc(id)}/subscribe`),
  unsubscribe: (id: string) => api.delete<{ subscribed: boolean }>(`/api/sessions/${enc(id)}/subscribe`),
};

export const catalog = {
  projects: () => api.get<{ items: Project[] }>("/api/projects"),
  models: (directory?: string) =>
    api.get<{ items: ModelOption[] }>(`/api/models${query({ directory })}`),
  agents: (directory?: string) =>
    api.get<{ items: AgentOption[] }>(`/api/agents${query({ directory })}`),
};

export const permissions = {
  list: () => api.get<{ items: PermissionItem[] }>("/api/permissions"),
  reply: (id: string, decision: Decision) =>
    api.post<{ ok: boolean }>(`/api/permissions/${enc(id)}/reply`, { decision }),
};

export const service = {
  status: () => api.get<ServiceStatus>("/api/service/status"),
  restart: () => api.post<{ restarted: boolean; busy_count: number }>("/api/service/restart", { confirm: true }),
};

export const settings = {
  notifications: () => api.get<NotificationSettings>("/api/settings/notifications"),
  setNotifyAll: (value: boolean) =>
    api.post<NotificationSettings>("/api/settings/notifications", { notify_all: value }),
};
