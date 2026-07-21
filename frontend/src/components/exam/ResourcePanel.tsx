// frontend/src/components/exam/ResourcePanel.tsx
// AEGIS-121: in-exam resource panel for open-book exams.
//
// Shows the professor's curated allowlist. Opening a resource is recorded two
// ways: a lightweight telemetry event (live timeline) AND a durable REST call
// (the authoritative record the professor grades against). Tracking is
// evidence, not enforcement — nothing here blocks the student.
//
// PDF files are served by the backend behind bearer auth, so they cannot be
// framed with a raw <iframe src={endpoint}> (a browser-initiated request
// wouldn't carry the in-memory token). We fetch the file as a blob through the
// axios client and frame an object URL instead — the same pattern the
// professor's CSV export uses (SessionHistoryView).
import React, { useCallback, useEffect, useRef, useState } from "react";
import apiClient from "../../api/client";
import { makeResourceAccessEvent } from "../../telemetry/signals/resourceAccess";
import type { TelemetryEvent } from "../../telemetry/types";

export interface ExamResource {
  id: string;
  label: string;
  type: "url" | "file";
  url: string | null;
  embed: boolean;
}

interface ResourcePanelProps {
  examId: string;
  sessionId: string;
  resources: ExamResource[];
  /** Emit a telemetry event (live timeline). */
  enqueue: (event: TelemetryEvent) => void;
  /** Collapse the panel (parent controls the split layout). */
  onCollapse?: () => void;
}

/**
 * Durably record a resource OPEN and return the created access-row id (so its
 * duration can be filled in on close). Best-effort: a failure resolves to null
 * so tracking never disrupts the student (the exam is unaffected either way).
 */
async function openAccess(
  examId: string,
  resourceId: string,
): Promise<string | null> {
  try {
    const { data } = await apiClient.post<{ id: string }>(
      `/exams/${examId}/resource-access`,
      { resource_id: resourceId },
    );
    return data.id;
  } catch {
    return null; // evidence, not enforcement — never block the student
  }
}

/** Fill in how long a previously-opened resource stayed open (best-effort). */
function updateDuration(
  examId: string,
  accessId: string,
  durationMs: number,
): void {
  apiClient
    .patch(`/exams/${examId}/resource-access/${accessId}`, {
      duration_ms: durationMs,
    })
    .catch(() => {
      /* a missed update just leaves the duration null — never block */
    });
}

const ResourcePanel: React.FC<ResourcePanelProps> = ({
  examId,
  sessionId,
  resources,
  enqueue,
  onCollapse,
}) => {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [fileError, setFileError] = useState(false);
  const [fileLoading, setFileLoading] = useState(false);

  // The resource currently open + when it was opened + the durable access-row
  // id, so we can fill in its duration when the student switches away,
  // collapses, or submits.
  const openSinceRef = useRef<number | null>(null);
  const openResourceRef = useRef<string | null>(null);
  // Promise for the open access-row id — awaited on close so the PATCH targets
  // the right row even if the student closes before the POST resolves.
  const accessIdRef = useRef<Promise<string | null> | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const selected = resources.find((r) => r.id === selectedId) ?? null;

  // Flush the duration for the currently-open resource (durable + telemetry).
  const flushOpenDuration = useCallback(() => {
    const openId = openResourceRef.current;
    const since = openSinceRef.current;
    const accessIdPromise = accessIdRef.current;
    if (openId && since !== null) {
      const durationMs = Date.now() - since;
      enqueue(makeResourceAccessEvent(sessionId, openId, "close", durationMs));
      if (accessIdPromise) {
        accessIdPromise.then((accessId) => {
          if (accessId) updateDuration(examId, accessId, durationMs);
        });
      }
    }
    openResourceRef.current = null;
    openSinceRef.current = null;
    accessIdRef.current = null;
  }, [examId, sessionId, enqueue]);

  const revokeObjectUrl = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  // Flush any open resource + revoke the object URL on unmount (covers submit,
  // which unmounts ExamContent).
  useEffect(() => {
    return () => {
      flushOpenDuration();
      revokeObjectUrl();
    };
  }, [flushOpenDuration, revokeObjectUrl]);

  const openResource = useCallback(
    async (resource: ExamResource) => {
      if (resource.id === selectedId) return;

      // Close out the previously-open resource before switching.
      flushOpenDuration();
      revokeObjectUrl();
      setFileUrl(null);
      setFileError(false);

      // Record the open (telemetry + durable) and start its duration clock.
      enqueue(makeResourceAccessEvent(sessionId, resource.id, "open"));
      accessIdRef.current = openAccess(examId, resource.id);
      openResourceRef.current = resource.id;
      openSinceRef.current = Date.now();
      setSelectedId(resource.id);

      if (resource.type === "file") {
        setFileLoading(true);
        try {
          const { data } = await apiClient.get(
            `/exams/${examId}/resources/${resource.id}/file`,
            { responseType: "blob" },
          );
          const objectUrl = URL.createObjectURL(data as Blob);
          objectUrlRef.current = objectUrl;
          setFileUrl(objectUrl);
        } catch {
          setFileError(true);
        } finally {
          setFileLoading(false);
        }
      }
    },
    [
      examId,
      sessionId,
      selectedId,
      enqueue,
      flushOpenDuration,
      revokeObjectUrl,
    ],
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-hairline">
        <span className="text-xs font-semibold text-ink">Resources</span>
        {onCollapse && (
          <button
            onClick={() => {
              flushOpenDuration();
              onCollapse();
            }}
            className="text-xs text-mute hover:text-ink transition-colors"
            aria-label="Collapse resources panel"
          >
            Hide ✕
          </button>
        )}
      </div>

      {/* Resource list */}
      <div className="border-b border-hairline max-h-40 overflow-y-auto">
        {resources.length === 0 ? (
          <p className="px-3 py-2 text-xs text-mute">
            No resources for this exam.
          </p>
        ) : (
          resources.map((r) => (
            <button
              key={r.id}
              onClick={() => openResource(r)}
              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                r.id === selectedId
                  ? "bg-primary/10 text-ink font-medium"
                  : "text-body hover:bg-surface-soft"
              }`}
            >
              <span className="mr-1.5 text-xs text-mute">
                {r.type === "file" ? "📄" : "🔗"}
              </span>
              {r.label}
            </button>
          ))
        )}
      </div>

      {/* Viewer */}
      <div className="flex-1 overflow-auto bg-surface-doc">
        {!selected ? (
          <p className="p-4 text-xs text-mute">
            Select a resource to open it here.
          </p>
        ) : selected.type === "file" ? (
          fileLoading ? (
            <p className="p-4 text-xs text-mute">Loading document…</p>
          ) : fileError ? (
            <p className="p-4 text-xs text-accent-red">
              Failed to load this document.
            </p>
          ) : fileUrl ? (
            <iframe
              title={selected.label}
              src={fileUrl}
              className="w-full h-full border-0 min-h-[24rem]"
            />
          ) : null
        ) : selected.embed && selected.url ? (
          <iframe
            title={selected.label}
            src={selected.url}
            className="w-full h-full border-0 min-h-[24rem]"
            sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
          />
        ) : (
          <div className="p-4 text-sm text-body">
            <p className="mb-3">
              This resource opens in a new tab. Your access is recorded for the
              professor's review.
            </p>
            <a
              href={selected.url ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block px-3 py-1.5 bg-primary text-ink text-xs font-bold rounded-md"
            >
              Open “{selected.label}” ↗
            </a>
          </div>
        )}
      </div>
    </div>
  );
};

export default ResourcePanel;
