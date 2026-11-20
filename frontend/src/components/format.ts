const STATUS_LABELS: Record<string, string> = {
  busy: "работает",
  idle: "ждет",
  succeeded: "готово",
  failed: "ошибка",
  interrupted: "остановлена",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

/** Время OpenCode в миллисекундах; секунды тоже поддерживаются. */
export function formatTime(value: number | null | undefined, now = Date.now()): string {
  if (!value) return "";
  const ms = value < 1e12 ? value * 1000 : value;
  const diff = Math.max(0, now - ms);
  const minute = 60_000;
  if (diff < minute) return "только что";
  if (diff < 60 * minute) return `${Math.floor(diff / minute)} мин назад`;
  if (diff < 24 * 60 * minute) return `${Math.floor(diff / (60 * minute))} ч назад`;
  return new Date(ms).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

export function formatCost(cost: number): string {
  return cost > 0 ? `$${cost.toFixed(cost < 1 ? 3 : 2)}` : "";
}
