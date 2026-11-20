/** Состояние живого вывода сессии из событий SSE. */
import type { StreamEvent } from "../types/api";

export interface StreamState {
  text: string;
  reasoning: boolean;
  steps: string[];
  status: string | null;
  permissionAsked: boolean;
}

export const initialStream: StreamState = {
  text: "",
  reasoning: false,
  steps: [],
  status: null,
  permissionAsked: false,
};

const MAX_TEXT = 60_000;
const MAX_STEPS = 8;

function pick(data: Record<string, unknown>, keys: string[]): string | null {
  const sources = [data, data.properties, data.part].filter(
    (item): item is Record<string, unknown> => typeof item === "object" && item !== null,
  );
  for (const source of sources) {
    for (const key of keys) {
      const value = source[key];
      if (typeof value === "string" && value) return value;
    }
  }
  return null;
}

function pushStep(steps: string[], step: string): string[] {
  return [...steps, step].slice(-MAX_STEPS);
}

export function reduceStream(state: StreamState, event: StreamEvent): StreamState {
  const data = event.data ?? {};
  switch (event.type) {
    case "session.execution.started":
      return { ...initialStream, status: "busy" };
    case "session.text.delta": {
      const delta = pick(data, ["delta", "text"]) ?? "";
      return { ...state, status: "busy", reasoning: false, text: (state.text + delta).slice(-MAX_TEXT) };
    }
    case "session.reasoning.delta":
      return { ...state, status: "busy", reasoning: true };
    case "session.tool.input.started": {
      const tool = pick(data, ["tool", "name", "toolName"]) ?? "инструмент";
      return { ...state, status: "busy", steps: pushStep(state.steps, `▶ ${tool}`) };
    }
    case "session.tool.success": {
      const tool = pick(data, ["tool", "name", "toolName"]) ?? "инструмент";
      return { ...state, steps: pushStep(state.steps, `✓ ${tool}`) };
    }
    case "session.tool.failed": {
      const tool = pick(data, ["tool", "name", "toolName"]) ?? "инструмент";
      return { ...state, steps: pushStep(state.steps, `✗ ${tool}`) };
    }
    case "session.execution.succeeded":
      return { ...state, status: "succeeded", reasoning: false };
    case "session.execution.failed":
      return { ...state, status: "failed", reasoning: false };
    case "session.execution.interrupted":
      return { ...state, status: "interrupted", reasoning: false };
    case "session.idle":
      return { ...state, status: state.status === "busy" ? "idle" : state.status, reasoning: false };
    case "permission.asked":
      return { ...state, permissionAsked: true };
    case "permission.replied":
      return { ...state, permissionAsked: false };
    default:
      return state;
  }
}

/** События, после которых карточку сессии стоит перечитать с сервера. */
export function isFinal(event: StreamEvent): boolean {
  return (
    event.type === "session.execution.succeeded" ||
    event.type === "session.execution.failed" ||
    event.type === "session.execution.interrupted" ||
    event.type === "session.idle"
  );
}
