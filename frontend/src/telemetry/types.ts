/** All telemetry event types emitted by the SDK. */

export type EventType =
  | "tab_blur"
  | "tab_focus"
  | "paste"
  | "key_interval"
  | "key_burst"
  | "resize"
  | "answer_start"
  | "answer_submit";

export interface TelemetryEvent {
  type: EventType;
  sessionId: string;
  clientTs: number; // Unix ms timestamp
  payload: Record<string, unknown>;
}

export interface SDKConfig {
  sessionToken: string;
  sessionId: string;
  wsUrl: string;
}