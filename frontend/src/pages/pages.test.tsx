import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "../components/Toasts";
import { apiError, mockFetch } from "../test/fetch";
import { session } from "../test/data";
import { NewTaskPage } from "./NewTaskPage";
import { PermissionsPage } from "./PermissionsPage";
import { ServicePage } from "./ServicePage";
import { SessionPage } from "./SessionPage";

function wrap(node: React.ReactNode) {
  return render(<ToastProvider>{node}</ToastProvider>);
}

test("busy session asks queue or steer and sends the draft", async () => {
  const mock = mockFetch({
    "GET /api/sessions/s1": { body: { ...session("s1", { busy: true, status: "busy" }), last_text: "Готово наполовину" } },
    "POST /api/sessions/s1/prompt": (body) =>
      (body as { draft_id?: string }).draft_id
        ? { body: { ok: true, delivery: "steer" } }
        : apiError(409, "conflict", "Сессия занята", { draft_id: "d1" }),
  });
  wrap(<SessionPage id="s1" />);
  expect(await screen.findByText("Готово наполовину")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Текст"), "еще");
  await userEvent.click(screen.getByText("Отправить"));
  await userEvent.click(await screen.findByText("Вмешаться"));
  await waitFor(() => expect(mock.calls.at(-1)?.body).toEqual({ draft_id: "d1", delivery: "steer" }));
  expect(await screen.findByText("Отправлено в работу")).toBeInTheDocument();
});

test("delete requires confirmation", async () => {
  const mock = mockFetch({
    "GET /api/sessions/s1": { body: session("s1") },
    "DELETE /api/sessions/s1": { body: { deleted: true } },
  });
  wrap(<SessionPage id="s1" />);
  await userEvent.click(await screen.findByText("Удалить"));
  expect(mock.calls.some((call) => call.method === "DELETE")).toBe(false);
  const dialog = screen.getByRole("dialog");
  await userEvent.click(dialog.querySelector(".btn.danger") as HTMLElement);
  await waitFor(() => expect(mock.calls.some((call) => call.method === "DELETE" && call.url.includes("confirm=true"))).toBe(true));
  expect(window.location.hash).toBe("#/");
});

test("stop interrupts a busy session", async () => {
  const mock = mockFetch({
    "GET /api/sessions/s1": { body: session("s1", { busy: true, status: "busy" }) },
    "POST /api/sessions/s1/interrupt": { body: { interrupted: true } },
  });
  wrap(<SessionPage id="s1" />);
  await userEvent.click(await screen.findByText("Стоп"));
  await waitFor(() => expect(mock.calls.some((call) => call.url === "/api/sessions/s1/interrupt")).toBe(true));
});

test("service restart only after confirmation", async () => {
  const mock = mockFetch({
    "GET /api/service/status": { body: { running: true, version: "1", url: "http://127.0.0.1:1", busy_count: 2, restarting: false } },
    "POST /api/service/restart": { body: { restarted: true, busy_count: 2 } },
  });
  wrap(<ServicePage />);
  await userEvent.click(await screen.findByText("Перезапустить"));
  expect(screen.getByText(/Сейчас работают сессии: 2/)).toBeInTheDocument();
  expect(mock.calls.some((call) => call.method === "POST")).toBe(false);
  const dialog = screen.getByRole("dialog");
  await userEvent.click(dialog.querySelector(".btn.danger") as HTMLElement);
  await waitFor(() =>
    expect(mock.calls.find((call) => call.method === "POST")?.body).toEqual({ confirm: true }),
  );
});

test("permissions offer three decisions", async () => {
  const mock = mockFetch({
    "GET /api/permissions": {
      body: { items: [{ id: "r1", session_id: "s1", action: "shell", resources: ["ls -la"], message: "run ls", directory: null, save: [] }] },
    },
    "POST /api/permissions/r1/reply": { body: { ok: true } },
  });
  wrap(<PermissionsPage />);
  expect(await screen.findByText("ls -la")).toBeInTheDocument();
  expect(screen.getByText("Разрешить")).toBeInTheDocument();
  expect(screen.getByText("Всегда")).toBeInTheDocument();
  await userEvent.click(screen.getByText("Отклонить"));
  await waitFor(() =>
    expect(mock.calls.find((call) => call.method === "POST")?.body).toEqual({ decision: "reject" }),
  );
});

test("new task posts project, model, agent and prompt", async () => {
  const mock = mockFetch({
    "GET /api/projects": { body: { items: [{ id: "p1", canonical: "/work/alpha", title: "alpha", active: 1 }] } },
    "GET /api/models": { body: { items: [{ provider: "openai", model: "gpt-x", label: "GPT X", variants: [] }] } },
    "GET /api/agents": { body: { items: [{ id: "plan", label: "Plan", mode: "primary" }] } },
    "POST /api/sessions": { status: 201, body: session("new1") },
  });
  wrap(<NewTaskPage />);
  await screen.findByText("GPT X (openai)");
  await screen.findByText("Plan");
  const [, modelSelect, agentSelect] = screen.getAllByRole("combobox");
  await userEvent.selectOptions(modelSelect, "openai/gpt-x");
  await userEvent.selectOptions(agentSelect, "plan");
  await userEvent.type(screen.getByPlaceholderText("Что нужно сделать?"), "Почини тесты");
  await userEvent.click(screen.getByText("Запустить"));
  await waitFor(() => expect(window.location.hash).toBe("#/session/new1"));
  expect(mock.calls.find((call) => call.method === "POST")?.body).toEqual({
    directory: "/work/alpha",
    prompt: "Почини тесты",
    model: { provider: "openai", id: "gpt-x" },
    agent: "plan",
  });
});
