import { EventStream, type EventSourceLike } from "./events";

class Source implements EventSourceLike {
  onopen: EventSourceLike["onopen"] = null;
  onmessage: EventSourceLike["onmessage"] = null;
  onerror: EventSourceLike["onerror"] = null;
  readyState = 0;
  closed = false;
  close() {
    this.closed = true;
    this.readyState = 2;
  }
  emit(data: unknown) {
    this.onmessage?.call(this as unknown as EventSource, new MessageEvent("message", { data: JSON.stringify(data) }));
  }
  open() {
    this.readyState = 1;
    this.onopen?.call(this as unknown as EventSource, new Event("open"));
  }
  fail() {
    this.onerror?.call(this as unknown as EventSource, new Event("error"));
  }
}

test("delivers events and reconnects with backoff", () => {
  vi.useFakeTimers();
  const sources: Source[] = [];
  const stream = new EventStream("/api/events", () => {
    const source = new Source();
    sources.push(source);
    return source;
  });
  const received: string[] = [];
  stream.subscribe((event) => received.push(event.type));
  const states: boolean[] = [];
  stream.onState((value) => states.push(value));
  stream.start();
  sources[0].open();
  sources[0].emit({ type: "session.idle", session_id: "s", data: {}, created: null });
  expect(received).toEqual(["session.idle"]);

  sources[0].fail();
  expect(sources[0].closed).toBe(true);
  expect(sources).toHaveLength(1);
  vi.advanceTimersByTime(1000);
  expect(sources).toHaveLength(2);
  sources[1].fail();
  vi.advanceTimersByTime(1999);
  expect(sources).toHaveLength(2);
  vi.advanceTimersByTime(1);
  expect(sources).toHaveLength(3);
  expect(states).toEqual([true, false]);

  stream.stop();
  expect(sources[2].closed).toBe(true);
  vi.useRealTimers();
});

test("reconnects on visibilitychange when dead", () => {
  const sources: Source[] = [];
  const stream = new EventStream("/api/events", () => {
    const source = new Source();
    sources.push(source);
    return source;
  });
  stream.start();
  sources[0].close();
  document.dispatchEvent(new Event("visibilitychange"));
  expect(sources).toHaveLength(2);
  stream.stop();
});
