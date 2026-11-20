import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { service, sessions } from "../api/endpoints";
import { events } from "../api/events";
import { Button } from "../components/Button";
import { Header } from "../components/Header";
import { SessionItem } from "../components/SessionItem";
import { Skeleton } from "../components/Skeleton";
import { navigate } from "../app/router";
import { isFinal } from "../stores/stream";
import { useAsync, useOnVisible } from "../stores/useAsync";

const LIMIT = 20;

export function HomePage() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const list = useAsync(() => sessions.list({ page, limit: LIMIT, search: query }), [page, query]);
  const status = useAsync(() => service.status(), []);

  useOnVisible(() => {
    void list.reload();
    void status.reload();
  });

  // Начало и конец выполнения меняют статусы в списке.
  const reloadList = list.reload;
  useEffect(
    () =>
      events.subscribe((event) => {
        if (event.type === "session.execution.started" || isFinal(event)) void reloadList();
      }),
    [reloadList],
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      setQuery(search.trim());
    }, 350);
    return () => clearTimeout(timer);
  }, [search]);

  const items = list.data?.items ?? [];
  const active = items.filter((item) => item.busy);
  const recent = items.filter((item) => !item.busy);

  return (
    <>
      <Header
        title="OpenCode"
        actions={
          <Button onClick={() => navigate({ name: "new" })} aria-label="Новая задача">
            + Задача
          </Button>
        }
      />

      <a className="card row" href="#/service" style={{ color: "inherit", textDecoration: "none" }}>
        <div className="grow">
          <div className="title">Сервер OpenCode</div>
          <div className="hint">
            {status.data
              ? status.data.running
                ? `работает${status.data.version ? `, версия ${status.data.version}` : ""}`
                : "не отвечает"
              : status.error
                ? errorMessage(status.error)
                : "проверка…"}
          </div>
        </div>
        {status.data && (
          <span className={`badge ${status.data.running ? "succeeded" : "failed"}`}>
            {status.data.running ? `занято: ${list.data?.busy_count ?? status.data.busy_count}` : "offline"}
          </span>
        )}
      </a>

      <input
        type="search"
        placeholder="Поиск по названию"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        aria-label="Поиск"
      />

      {list.loading && !list.data && <Skeleton lines={4} />}
      {list.error != null && (
        <div className="card error-text">
          {errorMessage(list.error)}{" "}
          <Button variant="ghost" onClick={() => void list.reload()}>
            Повторить
          </Button>
        </div>
      )}

      {active.length > 0 && (
        <>
          <div className="section-title">Активные</div>
          <div className="list">
            {active.map((item) => (
              <SessionItem key={item.id} session={item} />
            ))}
          </div>
        </>
      )}

      <div className="section-title">Последние</div>
      <div className="list">
        {recent.map((item) => (
          <SessionItem key={item.id} session={item} />
        ))}
      </div>
      {list.data && items.length === 0 && <div className="empty">Сессий нет</div>}

      {list.data && list.data.pages > 1 && (
        <div className="btn-row" style={{ marginTop: 12 }}>
          <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Назад
          </Button>
          <span className="hint" style={{ alignSelf: "center" }}>
            {list.data.page} / {list.data.pages}
          </span>
          <Button variant="secondary" disabled={page >= list.data.pages} onClick={() => setPage(page + 1)}>
            Дальше
          </Button>
        </div>
      )}
    </>
  );
}
