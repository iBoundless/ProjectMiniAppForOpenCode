/** Подмена fetch: маршруты "METHOD /path" -> ответ или функция. */
import { vi } from "vitest";

export type Reply = { status?: number; body?: unknown };
export type Handler = Reply | ((body: unknown, url: string) => Reply);

export interface FetchMock {
  calls: { method: string; url: string; body: unknown }[];
  routes: Record<string, Handler>;
}

export function mockFetch(routes: Record<string, Handler>): FetchMock {
  const mock: FetchMock = { calls: [], routes };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    mock.calls.push({ method, url, body });
    const path = url.split("?")[0];
    const handler = mock.routes[`${method} ${url}`] ?? mock.routes[`${method} ${path}`];
    if (!handler) {
      return new Response(JSON.stringify({ error: { code: "not_found", message: "Не найдено" } }), { status: 404 });
    }
    const reply = typeof handler === "function" ? handler(body, url) : handler;
    return new Response(reply.body === undefined ? "" : JSON.stringify(reply.body), {
      status: reply.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  return mock;
}

export function apiError(status: number, code: string, message: string, extra: Record<string, unknown> = {}): Reply {
  return { status, body: { error: { code, message, ...extra } } };
}
