import type { ReactNode } from "react";

export function Header({ title, back, actions }: { title: string; back?: string; actions?: ReactNode }) {
  return (
    <div className="header">
      {back && (
        <a className="btn ghost" href={back} aria-label="Назад">
          ‹
        </a>
      )}
      <h1>{title}</h1>
      {actions}
    </div>
  );
}
