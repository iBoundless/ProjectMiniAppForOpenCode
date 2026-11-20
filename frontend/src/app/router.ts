/** Маршрутизация по hash: работает при раздаче статики и в Telegram WebView. */
import { useEffect, useState } from "react";

export type Route =
  | { name: "home" }
  | { name: "new" }
  | { name: "session"; id: string }
  | { name: "permissions" }
  | { name: "service" }
  | { name: "settings" };

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, "").replace(/^\/+/, "");
  const [head, tail] = path.split("/", 2);
  switch (head) {
    case "new":
      return { name: "new" };
    case "session":
      return tail ? { name: "session", id: decodeURIComponent(tail) } : { name: "home" };
    case "permissions":
      return { name: "permissions" };
    case "service":
      return { name: "service" };
    case "settings":
      return { name: "settings" };
    default:
      return { name: "home" };
  }
}

export function href(route: Route): string {
  switch (route.name) {
    case "home":
      return "#/";
    case "session":
      return `#/session/${encodeURIComponent(route.id)}`;
    default:
      return `#/${route.name}`;
  }
}

export function navigate(route: Route): void {
  window.location.hash = href(route);
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  useEffect(() => {
    const update = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
