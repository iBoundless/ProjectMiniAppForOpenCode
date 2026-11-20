/** fetch с cookie сессии и единым форматом ошибок backend. */

export class ApiError extends Error {
  status: number;
  code: string;
  extra: Record<string, unknown>;

  constructor(status: number, code: string, message: string, extra: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.extra = extra;
  }
}

type Method = "GET" | "POST" | "DELETE";

let onUnauthorized: (() => void) | null = null;

/** Вызывается при 401 на любом запросе, кроме запросов входа. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network", "Нет связи с панелью");
  }
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const error = (payload as { error?: Record<string, unknown> } | null)?.error ?? {};
    const { code, message, ...extra } = error;
    if (response.status === 401 && !path.startsWith("/api/auth/") && onUnauthorized) {
      onUnauthorized();
    }
    throw new ApiError(
      response.status,
      typeof code === "string" ? code : "internal",
      typeof message === "string" ? message : `Ошибка ${response.status}`,
      extra,
    );
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body: unknown = {}) => request<T>("POST", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Неизвестная ошибка";
}
