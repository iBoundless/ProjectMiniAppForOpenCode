import { useEffect, useReducer, useRef, useState } from "react";
import { ApiError, errorMessage } from "../api/client";
import { sessions, type Delivery } from "../api/endpoints";
import { events } from "../api/events";
import { navigate } from "../app/router";
import { Button } from "../components/Button";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { formatCost, formatTime } from "../components/format";
import { Header } from "../components/Header";
import { Skeleton } from "../components/Skeleton";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/toast-context";
import { initialStream, isFinal, reduceStream } from "../stores/stream";
import { useAsync, useOnVisible } from "../stores/useAsync";

export function SessionPage({ id }: { id: string }) {
  const toast = useToast();
  const card = useAsync(() => sessions.get(id), [id]);
  const [stream, dispatch] = useReducer(reduceStream, initialStream);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [draft, setDraft] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const outputRef = useRef<HTMLDivElement>(null);
  const reload = card.reload;

  useOnVisible(() => void reload());

  useEffect(
    () =>
      events.subscribe((event) => {
        if (event.session_id !== id) return;
        dispatch(event);
        if (isFinal(event) || event.type === "session.execution.started") void reload();
      }),
    [id, reload],
  );

  useEffect(() => {
    const node = outputRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [stream.text]);

  const session = card.data;
  const status = stream.status ?? session?.status ?? "idle";
  const busy = status === "busy";
  const output = stream.text || session?.last_text || "";

  async function send(delivery?: Delivery) {
    setSending(true);
    try {
      const body = draft ? { draft_id: draft, delivery } : { text, delivery };
      const result = await sessions.prompt(id, body);
      setText("");
      setDraft(null);
      toast.show(result.delivery === "steer" ? "Отправлено в работу" : "Поставлено в очередь");
    } catch (exc) {
      if (exc instanceof ApiError && exc.status === 409 && typeof exc.extra.draft_id === "string") {
        setDraft(exc.extra.draft_id);
      } else {
        if (exc instanceof ApiError && exc.status === 404) setDraft(null);
        toast.error(errorMessage(exc));
      }
    } finally {
      setSending(false);
    }
  }

  async function interrupt() {
    setStopping(true);
    try {
      await sessions.interrupt(id);
      toast.show("Остановка отправлена");
      void reload();
    } catch (exc) {
      toast.error(errorMessage(exc));
    } finally {
      setStopping(false);
    }
  }

  async function remove() {
    setDeleting(true);
    try {
      await sessions.remove(id);
      toast.show("Сессия удалена");
      navigate({ name: "home" });
    } catch (exc) {
      toast.error(errorMessage(exc));
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function toggleSubscription() {
    if (!session) return;
    try {
      const result = session.subscribed ? await sessions.unsubscribe(id) : await sessions.subscribe(id);
      card.setData({ ...session, subscribed: result.subscribed });
    } catch (exc) {
      toast.error(errorMessage(exc));
    }
  }

  if (card.loading && !session) {
    return (
      <>
        <Header title="Сессия" back="#/" />
        <Skeleton lines={6} />
      </>
    );
  }
  if (!session) {
    return (
      <>
        <Header title="Сессия" back="#/" />
        <div className="card error-text">{errorMessage(card.error)}</div>
      </>
    );
  }

  return (
    <>
      <Header
        title={session.title || session.id}
        back="#/"
        actions={
          <Button variant="ghost" onClick={toggleSubscription} aria-label="Подписка">
            {session.subscribed ? "🔔" : "🔕"}
          </Button>
        }
      />
      <div className="card">
        <div className="row">
          <div className="grow hint">
            {[session.project.title, session.model?.id, session.agent, formatCost(session.cost), formatTime(session.time.updated)]
              .filter(Boolean)
              .join(" · ")}
          </div>
          <StatusBadge status={status} />
        </div>
        {busy && (
          <div className="progress-line" style={{ marginTop: 8 }}>
            {stream.reasoning ? "Думает…" : "Работает…"}
          </div>
        )}
        {stream.steps.length > 0 && (
          <div className="mono hint" style={{ marginTop: 6 }}>
            {stream.steps.map((step, index) => (
              <div key={index}>{step}</div>
            ))}
          </div>
        )}
        {stream.permissionAsked && (
          <p>
            <a href="#/permissions">Нужен ответ на запрос прав</a>
          </p>
        )}
      </div>

      <div className="card">
        <div className="section-title" style={{ marginTop: 0 }}>
          Ответ
        </div>
        <div className="stream pre" ref={outputRef} data-testid="output">
          {output || <span className="hint">Пока пусто</span>}
        </div>
      </div>

      <div className="card">
        {draft ? (
          <>
            <p>Сессия занята. Поставить текст в очередь или вмешаться в текущую работу?</p>
            <div className="btn-row">
              <Button variant="secondary" onClick={() => setDraft(null)} disabled={sending}>
                Отмена
              </Button>
              <Button variant="secondary" onClick={() => void send("queue")} loading={sending}>
                В очередь
              </Button>
              <Button onClick={() => void send("steer")} loading={sending}>
                Вмешаться
              </Button>
            </div>
          </>
        ) : (
          <>
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Дополнительный текст для сессии"
              maxLength={20000}
              aria-label="Текст"
            />
            <div className="btn-row" style={{ marginTop: 8 }}>
              <Button onClick={() => void send()} loading={sending} disabled={!text.trim()}>
                Отправить
              </Button>
            </div>
          </>
        )}
      </div>

      <div className="btn-row">
        <Button variant="secondary" onClick={() => void interrupt()} loading={stopping} disabled={!busy}>
          Стоп
        </Button>
        <Button variant="danger" onClick={() => setConfirmDelete(true)}>
          Удалить
        </Button>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Удалить сессию?"
        confirmLabel="Удалить"
        danger
        busy={deleting}
        onConfirm={() => void remove()}
        onCancel={() => setConfirmDelete(false)}
      >
        Сессия будет удалена в OpenCode вместе с историей. Это нельзя отменить.
      </ConfirmDialog>
    </>
  );
}
