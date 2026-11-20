import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (value: T | null) => void;
}

/** Загрузка данных с перезагрузкой; ответы устаревших запросов отбрасываются. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const loader = useCallback(load, deps);

  const reload = useCallback(async () => {
    const current = ++generation.current;
    setLoading(true);
    try {
      const value = await loader();
      if (current === generation.current) {
        setData(value);
        setError(null);
      }
    } catch (exc) {
      if (current === generation.current) setError(exc);
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

/** Перезагрузка при возврате приложения из фона (iPhone, Telegram). */
export function useOnVisible(callback: () => void): void {
  const ref = useRef(callback);
  useEffect(() => {
    ref.current = callback;
  });
  useEffect(() => {
    const handler = () => {
      if (document.visibilityState === "visible") ref.current();
    };
    document.addEventListener("visibilitychange", handler);
    return () => document.removeEventListener("visibilitychange", handler);
  }, []);
}
