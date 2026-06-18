import { CircularBuffer } from "./CircularBuffer";
import type { SDKConfig, TelemetryEvent } from "./types";

const MAX_BACKOFF_MS = 30_000; // 30 seconds max wait
const BASE_BACKOFF_MS = 1_000; // start at 1 second

/**
 * Manages WebSocket connection to the backend telemetry gateway.
 * - Buffers events in a CircularBuffer (max 500)
 * - Reconnects with exponential backoff on disconnect
 * - Flushes buffered events in order on reconnect
 */
export class TelemetryClient {
  private ws: WebSocket | null = null;
  private readonly buffer: CircularBuffer<TelemetryEvent>;
  private readonly config: SDKConfig;
  private retryCount = 0;
  private retryTimeout: ReturnType<typeof setTimeout> | null = null;
  private isDestroyed = false;

  constructor(config: SDKConfig) {
    this.config = config;
    this.buffer = new CircularBuffer<TelemetryEvent>(500);
    this.connect();
  }

  /** Queue a telemetry event for sending. */
  enqueue(event: TelemetryEvent): void {
    if (this.isConnected()) {
      this.send(event);
    } else {
      this.buffer.push(event);
    }
  }

  /** Flush any buffered events immediately if connected, then close. */
  flush(): void {
    if (this.isConnected()) {
      this.flushBuffer();
    }
  }

  /** Tear down the client — closes socket and cancels retries. */
  destroy(): void {
    this.isDestroyed = true;
    if (this.retryTimeout !== null) {
      clearTimeout(this.retryTimeout);
      this.retryTimeout = null;
    }
    if (this.ws !== null) {
      this.ws.close();
      this.ws = null;
    }
  }

  private connect(): void {
    if (this.isDestroyed) return;

    const url = `${this.config.wsUrl}?token=${this.config.sessionToken}&session=${this.config.sessionId}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.retryCount = 0;
      this.flushBuffer();
    };

    this.ws.onclose = (event: CloseEvent) => {
      this.ws = null;
      // 4401 (unauthorized) and 4403 (forbidden) are permanent auth errors.
      // Retrying with the same token would always fail, so stop here.
      if (event.code === 4401 || event.code === 4403) return;
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      // onclose fires after onerror — reconnect handled there
    };
  }

  private flushBuffer(): void {
    const events = this.buffer.flush();
    for (const event of events) {
      this.send(event);
    }
  }

  private send(event: TelemetryEvent): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(event));
    } else {
      this.buffer.push(event);
    }
  }

  private isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private scheduleReconnect(): void {
    if (this.isDestroyed) return;

    const backoff = Math.min(
      BASE_BACKOFF_MS * Math.pow(2, this.retryCount),
      MAX_BACKOFF_MS,
    );
    this.retryCount++;

    this.retryTimeout = setTimeout(() => {
      this.connect();
    }, backoff);
  }
}