import { render, screen } from "@testing-library/react";
import { apiError, mockFetch } from "../test/fetch";
import { session } from "../test/data";
import { App } from "./App";

const homeRoutes = {
  "GET /api/sessions": {
    body: { items: [session("s1", { title: "Fix bug", busy: true, status: "busy" }), session("s2", { title: "Old task" })], page: 1, pages: 1, limit: 20, total: 2, busy_count: 1 },
  },
  "GET /api/service/status": { body: { running: true, version: "1.2.3", url: "http://127.0.0.1:49374", busy_count: 1, restarting: false } },
  "GET /api/permissions": { body: { items: [] } },
};

afterEach(() => {
  delete window.Telegram;
});

test("signs in with Telegram initData and shows sessions", async () => {
  window.Telegram = { WebApp: { initData: "hash=x", ready: vi.fn(), expand: vi.fn() } };
  const mock = mockFetch({
    "POST /api/auth/telegram": { body: { user: { id: 42, first_name: "Test" } } },
    ...homeRoutes,
  });
  render(<App />);
  expect(await screen.findByText("Fix bug")).toBeInTheDocument();
  expect(screen.getByText("Old task")).toBeInTheDocument();
  expect(screen.getByText("Активные")).toBeInTheDocument();
  expect(mock.calls[0]).toMatchObject({ method: "POST", url: "/api/auth/telegram", body: { init_data: "hash=x" } });
});

test("foreign Telegram user sees access denied", async () => {
  window.Telegram = { WebApp: { initData: "hash=x", ready: vi.fn(), expand: vi.fn() } };
  mockFetch({ "POST /api/auth/telegram": apiError(403, "forbidden", "Доступ запрещен") });
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Доступ запрещен" })).toBeInTheDocument();
});

test("browser without cookie asks for a login link", async () => {
  mockFetch({ "GET /api/auth/me": apiError(401, "unauthorized", "Требуется вход") });
  render(<App />);
  expect(await screen.findByText("Нужен вход")).toBeInTheDocument();
});

test("browser with cookie goes straight to the panel", async () => {
  mockFetch({ "GET /api/auth/me": { body: { user: { id: 42 }, expires_at: 1 } }, ...homeRoutes });
  render(<App />);
  expect(await screen.findByText("Fix bug")).toBeInTheDocument();
});
