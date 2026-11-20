import { href } from "../app/router";
import type { Session } from "../types/api";
import { formatTime } from "./format";
import { StatusBadge } from "./StatusBadge";

export function SessionItem({ session }: { session: Session }) {
  return (
    <a
      className="card row"
      href={href({ name: "session", id: session.id })}
      style={{ color: "inherit", textDecoration: "none", margin: 0 }}
    >
      <div className="grow">
        <div className="title">{session.title || session.id}</div>
        <div className="hint">
          {[session.project.title, session.model?.id, formatTime(session.time.updated)].filter(Boolean).join(" · ")}
        </div>
      </div>
      {session.subscribed && (
        <span className="badge" title="Подписка">
          🔔
        </span>
      )}
      <StatusBadge status={session.status} />
    </a>
  );
}
