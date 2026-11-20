import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { permissions } from "../api/endpoints";
import { events } from "../api/events";
import { href } from "../app/router";
import { Button } from "../components/Button";
import { Header } from "../components/Header";
import { Skeleton } from "../components/Skeleton";
import { useToast } from "../components/toast-context";
import type { Decision } from "../types/api";
import { useAsync, useOnVisible } from "../stores/useAsync";

const LABELS: Record<Decision, string> = { once: "Разрешить", always: "Всегда", reject: "Отклонить" };

export function PermissionsPage({ onChange }: { onChange?: (count: number) => void }) {
  const toast = useToast();
  const list = useAsync(() => permissions.list(), []);
  const [pending, setPending] = useState<string | null>(null);
  const reload = list.reload;
  useOnVisible(() => void reload());

  useEffect(
    () =>
      events.subscribe((event) => {
        if (event.type === "permission.asked" || event.type === "permission.replied") void reload();
      }),
    [reload],
  );

  useEffect(() => {
    if (list.data) onChange?.(list.data.items.length);
  }, [list.data, onChange]);

  async function reply(id: string, decision: Decision) {
    setPending(id);
    try {
      await permissions.reply(id, decision);
      toast.show(decision === "reject" ? "Отклонено" : "Разрешено");
    } catch (exc) {
      toast.error(errorMessage(exc));
    } finally {
      setPending(null);
      void reload();
    }
  }

  const items = list.data?.items ?? [];
  return (
    <>
      <Header title="Запросы прав" />
      {list.loading && !list.data && <Skeleton lines={3} />}
      {list.error != null && <div className="card error-text">{errorMessage(list.error)}</div>}
      {list.data && items.length === 0 && <div className="empty">Нет запросов</div>}
      <div className="list">
        {items.map((item) => (
          <div className="card" key={item.id} style={{ margin: 0 }}>
            <div className="title">{item.action}</div>
            {item.message && <div className="pre">{item.message}</div>}
            {item.resources.length > 0 && (
              <div className="mono pre hint" style={{ margin: "6px 0" }}>
                {item.resources.join("\n")}
              </div>
            )}
            <div className="hint">
              <a href={href({ name: "session", id: item.session_id })}>Сессия</a>
              {item.directory ? ` · ${item.directory}` : ""}
            </div>
            <div className="btn-row" style={{ marginTop: 8 }}>
              {(["once", "always", "reject"] as Decision[]).map((decision) => (
                <Button
                  key={decision}
                  variant={decision === "reject" ? "danger" : decision === "always" ? "secondary" : "primary"}
                  disabled={pending !== null}
                  onClick={() => void reply(item.id, decision)}
                >
                  {LABELS[decision]}
                </Button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
