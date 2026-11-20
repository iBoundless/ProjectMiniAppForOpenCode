/** EventSource с переподключением: backoff и пробуждение при visibilitychange. */
import type { StreamEvent } from "../types/api";

type Listener = (event: StreamEvent) => void;
type StateListener = (connected: boolean) => void;

const BACKOFF = [1000, 2000, 5000, 10000, 30000];

export interface EventSourceLike {
  onopen: ((this: EventSource, ev: Event) => unknown) | null;
  onmessage: ((this: EventSource, ev: MessageEvent) => unknown) | null;
  onerror: ((this: EventSource, ev: Event) => unknown) | null;
  close(): void;
  readyState: number;
}

export class EventStream {
  private source: EventSourceLike | null = null;
  private listeners = new Set<Listener>();
  private stateListeners = new Set<StateListener>();
  private attempt = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private stopped = true;
  connected = false;
  private readonly url: string;
  private readonly factory: (url: string) => EventSourceLike;

  constructor(
    url = "/api/events",
    factory: (url: string) => EventSourceLike = (u) =>
      new EventSource(u, { withCredentials: true }) as unknown as EventSourceLike,
  ) {
    this.url = url;
    this.factory = factory;
  }

  private onVisibility = () => {
    if (document.visibilityState !== "visible" || this.stopped) return;
    // iPhone мог усыпить вкладку: соединение мертво, а onerror не пришел.
    if (!this.source || this.source.readyState === 2 || !this.connected) {
      this.attempt = 0;
      this.open();
    }
  };

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    document.addEventListener("visibilitychange", this.onVisibility);
    window.addEventListener("online", this.onVisibility);
    this.open();
  }

  stop(): void {
    this.stopped = true;
    document.removeEventListener("visibilitychange", this.onVisibility);
    window.removeEventListener("online", this.onVisibility);
    this.clearTimer();
    this.source?.close();
    this.source = null;
    this.setConnected(false);
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  onState(listener: StateListener): () => void {
    this.stateListeners.add(listener);
    return () => this.stateListeners.delete(listener);
  }

  private clearTimer(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private setConnected(value: boolean): void {
    if (this.connected === value) return;
    this.connected = value;
    for (const listener of this.stateListeners) listener(value);
  }

  private open(): void {
    this.clearTimer();
    this.source?.close();
    const source = this.factory(this.url);
    this.source = source;
    source.onopen = () => {
      this.attempt = 0;
      this.setConnected(true);
    };
    source.onmessage = (message: MessageEvent) => {
      let event: StreamEvent;
      try {
        event = JSON.parse(String(message.data));
      } catch {
        return;
      }
      for (const listener of this.listeners) listener(event);
    };
    source.onerror = () => {
      this.setConnected(false);
      source.close();
      if (this.source !== source || this.stopped) return;
      const delay = BACKOFF[Math.min(this.attempt, BACKOFF.length - 1)];
      this.attempt += 1;
      this.timer = setTimeout(() => this.open(), delay);
    };
  }
}

export const events = new EventStream();
