/** All telemetry event types emitted by the SDK. */

export type EventType =
  | "tab_blur"
  | "tab_return"
  | "paste"
  | "key_interval"
  | "key_burst"
  | "resize"
  | "answer_start"
  | "question_time";

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