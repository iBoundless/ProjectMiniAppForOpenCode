import { initialStream, isFinal, reduceStream } from "./stream";

const ev = (type: string, data: Record<string, unknown> = {}) => ({ type, session_id: "s1", data, created: null });

test("accumulates text and tool steps", () => {
  let state = reduceStream(initialStream, ev("session.execution.started"));
  state = reduceStream(state, ev("session.text.delta", { delta: "Hel" }));
  state = reduceStream(state, ev("session.text.delta", { delta: "lo" }));
  state = reduceStream(state, ev("session.tool.input.started", { tool: "bash" }));
  state = reduceStream(state, ev("session.tool.success", { tool: "bash" }));
  expect(state.text).toBe("Hello");
  expect(state.steps).toEqual(["▶ bash", "✓ bash"]);
  expect(state.status).toBe("busy");
  state = reduceStream(state, ev("session.execution.succeeded"));
  expect(state.status).toBe("succeeded");
});

test("permission flags and final events", () => {
  let state = reduceStream(initialStream, ev("permission.asked"));
  expect(state.permissionAsked).toBe(true);
  state = reduceStream(state, ev("permission.replied"));
  expect(state.permissionAsked).toBe(false);
  expect(isFinal(ev("session.idle"))).toBe(true);
  expect(isFinal(ev("session.text.delta"))).toBe(false);
});
