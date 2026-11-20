import { createContext, useContext } from "react";

export type ToastKind = "info" | "error";

export interface ToastApi {
  show(text: string, kind?: ToastKind): void;
  error(text: string): void;
}

export const ToastContext = createContext<ToastApi>({ show: () => undefined, error: () => undefined });

export function useToast(): ToastApi {
  return useContext(ToastContext);
}
