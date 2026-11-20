import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

/** В jsdom нет EventSource: заглушка, которая никогда не соединяется. */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0;
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  close() {
    this.readyState = 2;
  }
}
vi.stubGlobal("EventSource", FakeEventSource);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.location.hash = "";
});
