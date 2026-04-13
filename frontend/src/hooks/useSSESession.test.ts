import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useSSESession } from "./useSSESession";

// Minimal EventSource mock
class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  listeners = new Map<string, ((e: { data: string }) => void)[]>();
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, handler: (e: { data: string }) => void) {
    const handlers = this.listeners.get(event) ?? [];
    handlers.push(handler);
    this.listeners.set(event, handlers);
  }

  close() {
    this.closed = true;
  }
}

describe("useSSESession", () => {
  beforeEach(() => {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not connect when sessionId is null", () => {
    renderHook(() => useSSESession(null));

    expect(MockEventSource.instances).toHaveLength(0);
  });

  it("connects to the correct SSE endpoint", () => {
    renderHook(() => useSSESession("abc123"));

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toBe(
      "/api/thinking/abc123/events",
    );
  });

  it("registers listeners for all expected event types", () => {
    renderHook(() =>
      useSSESession("abc123", {
        onNodeStart: vi.fn(),
        onNodeText: vi.fn(),
        onNodeComplete: vi.fn(),
        onEdges: vi.fn(),
        onOpportunity: vi.fn(),
        onLayerComplete: vi.fn(),
        onSessionComplete: vi.fn(),
        onError: vi.fn(),
      }),
    );

    const es = MockEventSource.instances[0];
    const expectedEvents = [
      "node_start",
      "node_text",
      "node_complete",
      "edges",
      "opportunity",
      "layer_complete",
      "session_complete",
      "error",
    ];

    for (const event of expectedEvents) {
      expect(es.listeners.has(event), `Missing listener for "${event}"`).toBe(
        true,
      );
    }
  });

  it("closes EventSource on unmount", () => {
    const { unmount } = renderHook(() => useSSESession("abc123"));

    const es = MockEventSource.instances[0];
    expect(es.closed).toBe(false);

    unmount();
    expect(es.closed).toBe(true);
  });
});
