import type { TelemetryEvent } from "../types";

/** Keys that should not trigger an IKI sample on their own. */
const IGNORED_KEYS = new Set([
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Control",
  "Shift",
  "Tab",
  "Alt",
  "Meta",
  "CapsLock",
]);

/** Minimum keystrokes before emitting any IKI event. */
const MIN_KEYSTROKES = 5;

/** Minimum milliseconds between emitted events (throttle). */
const THROTTLE_MS = 2_000;

/** Maximum IKI value — long pauses are capped at this value. */
const MAX_IKI_MS = 5_000;

export interface KeystrokeSignalOptions {
  questionId: string;
  onEvent: (event: TelemetryEvent) => void;
}

export class KeystrokeSignal {
  private readonly questionId: string;
  private readonly onEvent: (event: TelemetryEvent) => void;
  private previousKeydownTime: number | null = null;
  private keystrokeCount = 0;
  private lastEmitTime = 0;
  private readonly handler: (e: KeyboardEvent) => void;

  constructor(
    private readonly target: HTMLElement,
    options: KeystrokeSignalOptions,
  ) {
    this.questionId = options.questionId;
    this.onEvent = options.onEvent;
    this.handler = this.handleKeydown.bind(this);
    this.target.addEventListener("keydown", this.handler);
  }

  /** Remove the event listener — call when the question is unmounted. */
  destroy(): void {
    this.target.removeEventListener("keydown", this.handler);
  }

  private handleKeydown(e: KeyboardEvent): void {
    if (IGNORED_KEYS.has(e.key)) return;

    const now = performance.now();

    if (this.previousKeydownTime !== null) {
      const ikiMs = Math.min(now - this.previousKeydownTime, MAX_IKI_MS);
      this.keystrokeCount++;

      if (
        this.keystrokeCount >= MIN_KEYSTROKES &&
        now - this.lastEmitTime >= THROTTLE_MS
      ) {
        this.lastEmitTime = now;
        this.onEvent({
          type: "key_interval",
          sessionId: "",
          clientTs: Date.now(),
          payload: {
            iki_ms: Math.round(ikiMs),
            question_id: this.questionId,
          },
        });
      }
    }

    this.previousKeydownTime = now;
  }
}