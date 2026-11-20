export interface User {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
}

export interface ModelRef {
  provider: string;
  id: string;
  variant?: string;
}

export type SessionStatus = "busy" | "idle" | "succeeded" | "failed" | "interrupted" | string;

export interface Session {
  id: string;
  parent_id: string | null;
  title: string;
  project: { id: string | null; title: string | null };
  directory: string | null;
  model: ModelRef | null;
  agent: string | null;
  status: SessionStatus;
  busy: boolean;
  outcome: string | null;
  cost: number;
  time: { created: number; updated: number; busy: number | null; idle: number | null };
  subscribed: boolean;
  active: boolean;
  last_text?: string | null;
}

export interface SessionPage {
  items: Session[];
  page: number;
  pages: number;
  limit: number;
  total: number;
  busy_count: number;
}

export interface Project {
  id: string;
  canonical: string;
  title: string;
  active: number;
}

export interface ModelOption {
  provider: string;
  model: string;
  label: string;
  variants: string[];
}

export interface AgentOption {
  id: string;
  label: string;
  mode: string | null;
}

export interface PermissionItem {
  id: string;
  session_id: string;
  action: string;
  resources: string[];
  message: string | null;
  directory: string | null;
  save: string[];
}

export type Decision = "once" | "always" | "reject";

export interface ServiceStatus {
  running: boolean;
  version: string | null;
  url: string;
  busy_count: number;
  restarting: boolean;
}

export interface NotificationSettings {
  notify_all: boolean;
  subscribed_sessions: string[];
}

export interface StreamEvent {
  type: string;
  session_id: string | null;
  data: Record<string, unknown>;
  created: number | null;
}
