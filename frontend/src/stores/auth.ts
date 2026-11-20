/** Вход: существующая cookie, иначе initData Telegram. */
import { ApiError } from "../api/client";
import { auth } from "../api/endpoints";
import { telegramInitData } from "../auth/telegram";
import type { User } from "../types/api";

export type AuthResult =
  | { state: "ok"; user: User }
  | { state: "forbidden"; message: string }
  | { state: "anonymous"; message?: string }
  | { state: "error"; message: string };

export async function signIn(): Promise<AuthResult> {
  const initData = telegramInitData();
  if (initData) {
    // Внутри Telegram всегда входим заново: пользователь мог смениться.
    try {
      const { user } = await auth.telegram(initData);
      return { state: "ok", user };
    } catch (error) {
      return failure(error);
    }
  }
  try {
    const { user } = await auth.me();
    return { state: "ok", user };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return { state: "anonymous" };
    return failure(error);
  }
}

function failure(error: unknown): AuthResult {
  if (error instanceof ApiError) {
    if (error.status === 403) return { state: "forbidden", message: error.message };
    if (error.status === 401) return { state: "anonymous", message: error.message };
    return { state: "error", message: error.message };
  }
  return { state: "error", message: "Не удалось войти" };
}
