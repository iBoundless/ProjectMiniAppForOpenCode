import { useCallback, useMemo, useState, type ReactNode } from "react";
import { haptic } from "../auth/telegram";
import { ToastContext, type ToastApi, type ToastKind } from "./toast-context";

interface Toast {
  id: number;
  text: string;
  kind: ToastKind;
}

let counter = 0;

export function ToastProvider({ children, timeout = 3500 }: { children: ReactNode; timeout?: number }) {
  const [items, setItems] = useState<Toast[]>([]);
  const show = useCallback(
    (text: string, kind: ToastKind = "info") => {
      const id = ++counter;
      setItems((current) => [...current.slice(-2), { id, text, kind }]);
      if (kind === "error") haptic("error");
      setTimeout(() => setItems((current) => current.filter((item) => item.id !== id)), timeout);
    },
    [timeout],
  );
  const value = useMemo<ToastApi>(() => ({ show, error: (text) => show(text, "error") }), [show]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((item) => (
          <div key={item.id} className={`toast ${item.kind === "error" ? "error" : ""}`} role="status">
            {item.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
