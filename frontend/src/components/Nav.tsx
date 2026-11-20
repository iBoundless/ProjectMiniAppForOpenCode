import type { Route } from "../app/router";

const ITEMS: { name: Route["name"]; label: string; href: string }[] = [
  { name: "home", label: "Сессии", href: "#/" },
  { name: "new", label: "Новая", href: "#/new" },
  { name: "permissions", label: "Права", href: "#/permissions" },
  { name: "service", label: "Сервис", href: "#/service" },
  { name: "settings", label: "Настройки", href: "#/settings" },
];

export function Nav({ current, pendingPermissions = 0 }: { current: Route["name"]; pendingPermissions?: number }) {
  return (
    <nav className="nav">
      {ITEMS.map((item) => (
        <a
          key={item.name}
          href={item.href}
          className={current === item.name || (current === "session" && item.name === "home") ? "active" : ""}
        >
          {item.label}
          {item.name === "permissions" && pendingPermissions > 0 && (
            <span className="dot" aria-label="ожидают ответа">
              {pendingPermissions}
            </span>
          )}
        </a>
      ))}
    </nav>
  );
}
