/** Обертка над Telegram.WebApp: в Safari/PWA объекта нет или initData пустая. */

export interface TelegramWebApp {
  initData: string;
  colorScheme?: "light" | "dark";
  ready(): void;
  expand(): void;
  openLink?(url: string): void;
  HapticFeedback?: { notificationOccurred(type: "error" | "success" | "warning"): void };
  BackButton?: {
    show(): void;
    hide(): void;
    onClick(cb: () => void): void;
    offClick(cb: () => void): void;
  };
  onEvent?(name: string, cb: () => void): void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function telegram(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp;
}

/** initData есть только при запуске внутри Telegram. */
export function telegramInitData(): string {
  return telegram()?.initData ?? "";
}

export function isTelegram(): boolean {
  return telegramInitData().length > 0;
}

export function setupTelegram(): void {
  const app = telegram();
  if (!app) return;
  try {
    app.ready();
    app.expand();
  } catch {
    // Старые клиенты Telegram: без expand панель тоже работает.
  }
  applyScheme(app.colorScheme);
  app.onEvent?.("themeChanged", () => applyScheme(telegram()?.colorScheme));
}

function applyScheme(scheme: "light" | "dark" | undefined): void {
  if (scheme) document.documentElement.dataset.scheme = scheme;
}

export function haptic(type: "error" | "success" | "warning"): void {
  try {
    telegram()?.HapticFeedback?.notificationOccurred(type);
  } catch {
    // Нет поддержки.
  }
}
