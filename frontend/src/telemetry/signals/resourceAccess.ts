import type { TelemetryEvent } from "../types";

/**
 * AEGIS-121: resource-access telemetry (open-book exams).
 *
 * A lightweight event emitted whenever a student opens (or closes) a resource
 * in the exam console's resource panel. This is for the professor's LIVE event
 * timeline only — the authoritative, durable record is the REST
 * POST /exams/{id}/resource-access call. The integrity scorer ignores this
 * event type (evidence, not enforcement). No page content is ever captured —
 * only the resource id, an action, and a duration.
 */
export function makeResourceAccessEvent(
  sessionId: string,
  resourceId: string,
  action: "open" | "close",
  durationMs?: number,
): TelemetryEvent {
  return {
    type: "resource_access",
    sessionId,
    clientTs: Date.now(),
    payload: {
      resource_id: resourceId,
      action,
      ...(durationMs !== undefined ? { duration_ms: durationMs } : {}),
    },
  };
}
