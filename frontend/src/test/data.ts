import type { Session } from "../types/api";

export function session(id: string, overrides: Partial<Session> = {}): Session {
  return {
    id,
    parent_id: null,
    title: `Session ${id}`,
    project: { id: "p1", title: "alpha" },
    directory: "/work/alpha",
    model: { provider: "openai", id: "gpt-x" },
    agent: "build",
    status: "idle",
    busy: false,
    outcome: null,
    cost: 0,
    time: { created: 1, updated: 2, busy: null, idle: 2 },
    subscribed: false,
    active: false,
    ...overrides,
  };
}
