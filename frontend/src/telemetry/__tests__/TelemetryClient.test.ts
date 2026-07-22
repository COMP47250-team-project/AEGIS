// frontend/src/telemetry/__tests__/TelemetryClient.test.ts
// AEGIS-115 Part B: regression tests for the exam_closed WebSocket message
// triggering the onExamClosed callback.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TelemetryClient } from "../TelemetryClient";

// ---------------------------------------------------------------------------
// Minimal WebSocket mock
// ---------------------------------------------------------------------------
class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;

  send = vi.fn();
  close = vi.fn();

  simulateMessage(data: string) {
    this.onmessage?.({ data });
  }

  simulateOpen() {
    this.onopen?.();
  }
}

let mockWs: MockWebSocket;

beforeEach(() => {
  mockWs = new MockWebSocket();
  // Must use a class/constructor function, not an arrow function
  const WsMock = function () {
    return mockWs;
  } as unknown as typeof WebSocket;
  vi.stubGlobal("WebSocket", WsMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function makeClient(onExamClosed?: () => void): TelemetryClient {
  const client = new TelemetryClient({
    wsUrl: "ws://localhost:8000/ws/exam/test-id",
    sessionToken: "test-token",
    sessionId: "test-session-id",
    onExamClosed,
  });
  mockWs.simulateOpen();
  return client;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe("TelemetryClient — onExamClosed callback (AEGIS-115)", () => {
  it("calls onExamClosed when server pushes {type:'exam_closed'}", () => {
    const onExamClosed = vi.fn();
    makeClient(onExamClosed);

    mockWs.simulateMessage(JSON.stringify({ type: "exam_closed" }));

    expect(onExamClosed).toHaveBeenCalledTimes(1);
  });

  it("does NOT call onExamClosed for unrelated message types", () => {
    const onExamClosed = vi.fn();
    makeClient(onExamClosed);

    mockWs.simulateMessage(JSON.stringify({ type: "ping" }));
    mockWs.simulateMessage(JSON.stringify({ type: "heartbeat" }));
    mockWs.simulateMessage("not-json-at-all");

    expect(onExamClosed).not.toHaveBeenCalled();
  });

  it("does not throw when onExamClosed is not provided", () => {
    makeClient();

    expect(() => {
      mockWs.simulateMessage(JSON.stringify({ type: "exam_closed" }));
    }).not.toThrow();
  });

  it("does not reconnect after receiving exam_closed", () => {
    let wsCallCount = 0;
    const WsMock = function () {
      wsCallCount++;
      return mockWs;
    } as unknown as typeof WebSocket;
    vi.stubGlobal("WebSocket", WsMock);

    makeClient(vi.fn());
    mockWs.simulateMessage(JSON.stringify({ type: "exam_closed" }));

    const countAfterClose = wsCallCount;
    // Simulate socket closing — should NOT trigger a new WebSocket
    mockWs.onclose?.({ code: 1000 });

    expect(wsCallCount).toBe(countAfterClose);
  });
});
