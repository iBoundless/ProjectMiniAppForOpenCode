import { useState } from "react";
import { errorMessage } from "../api/client";
import { service } from "../api/endpoints";
import { Button } from "../components/Button";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Header } from "../components/Header";
import { Skeleton } from "../components/Skeleton";
import { useToast } from "../components/toast-context";
import { useAsync, useOnVisible } from "../stores/useAsync";

export function ServicePage() {
  const toast = useToast();
  const status = useAsync(() => service.status(), []);
  const [confirm, setConfirm] = useState(false);
  const [restarting, setRestarting] = useState(false);
  useOnVisible(() => void status.reload());

  async function restart() {
    setRestarting(true);
    try {
      await service.restart();
      toast.show("OpenCode перезапущен");
    } catch (exc) {
      toast.error(errorMessage(exc));
    } finally {
      setRestarting(false);
      setConfirm(false);
      void status.reload();
    }
  }

  const data = status.data;
  return (
    <>
      <Header title="Сервис" />
      {status.loading && !data && <Skeleton lines={4} />}
      {status.error != null && !data && <div className="card error-text">{errorMessage(status.error)}</div>}
      {data && (
        <div className="card">
          <div className="row">
            <div className="grow title">OpenCode</div>
            <span className={`badge ${data.running ? "succeeded" : "failed"}`}>
              {data.running ? "работает" : "не отвечает"}
            </span>
          </div>
          <dl className="hint">
            <dt>Версия</dt>
            <dd>{data.version ?? "неизвестно"}</dd>
            <dt>Адрес</dt>
            <dd className="mono">{data.url}</dd>
            <dt>Занятых сессий</dt>
            <dd>{data.busy_count}</dd>
          </dl>
          <div className="btn-row">
            <Button variant="secondary" onClick={() => void status.reload()}>
              Обновить
            </Button>
            <Button variant="danger" onClick={() => setConfirm(true)} disabled={data.restarting || restarting}>
              Перезапустить
            </Button>
          </div>
        </div>
      )}
      <ConfirmDialog
        open={confirm}
        title="Перезапустить OpenCode?"
        confirmLabel="Перезапустить"
        danger
        busy={restarting}
        onConfirm={() => void restart()}
        onCancel={() => setConfirm(false)}
      >
        {data && data.busy_count > 0
          ? `Сейчас работают сессии: ${data.busy_count}. Их выполнение прервется.`
          : "Перезапускается только сервис OpenCode, не сервер."}
      </ConfirmDialog>
    </>
  );
}
