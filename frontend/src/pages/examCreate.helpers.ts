// Pure helpers for the create-exam form (AEGIS-62), split out so they're unit-testable.

import apiClient from "../api/client";
import type { DraftUrlResource } from "../components/professor/ResourceAllowlistEditor";

/**
 * Parse student emails typed or pasted/CSV-uploaded. Splits on whitespace,
 * commas and semicolons, keeps only email-like tokens (so CSV headers/extra
 * columns are dropped), lowercases, and de-duplicates silently (order kept).
 */
export function parseStudentEmails(raw: string): string[] {
  // Set preserves insertion order, so this dedupes silently while keeping order.
  return [
    ...new Set(
      raw
        .split(/[\s,;]+/)
        .map((t) => t.trim().toLowerCase())
        .filter((t) => t.includes("@")),
    ),
  ];
}

/** Whole minutes between two datetime-local strings (end - start). */
export function durationMinutes(startLocal: string, endLocal: string): number {
  return Math.round(
    (new Date(endLocal).getTime() - new Date(startLocal).getTime()) / 60000,
  );
}

/**
 * AEGIS-121: keep only resource rows the professor actually filled in — both a
 * label and an http(s) URL. Used before POSTing to the backend (which also
 * validates the scheme) so we don't send blank rows.
 */
export function validUrlResources(
  resources: DraftUrlResource[],
): DraftUrlResource[] {
  return resources
    .map((r) => ({ ...r, label: r.label.trim(), url: r.url.trim() }))
    .filter(
      (r) =>
        r.label !== "" &&
        (r.url.toLowerCase().startsWith("http://") ||
          r.url.toLowerCase().startsWith("https://")),
    );
}

/**
 * POST each URL resource to a freshly-created exam. Returns how many succeeded
 * and failed so the caller can surface a partial failure (the exam already
 * exists at this point — resources are a second phase).
 */
export async function postUrlResources(
  examId: string,
  resources: DraftUrlResource[],
): Promise<{ added: number; failed: number }> {
  const valid = validUrlResources(resources);
  const results = await Promise.allSettled(
    valid.map((r) =>
      apiClient.post(`/exams/${examId}/resources`, {
        label: r.label,
        url: r.url,
        embed: r.embed,
      }),
    ),
  );
  const failed = results.filter((r) => r.status === "rejected").length;
  return { added: results.length - failed, failed };
}

/**
 * Upload each PDF file to a freshly-created exam (AEGIS-121). Same two-phase
 * pattern as postUrlResources — files need the exam id, so they're sent after
 * POST /exams. Returns added/failed counts for partial-failure reporting.
 */
export async function postFileResources(
  examId: string,
  files: File[],
): Promise<{ added: number; failed: number }> {
  const results = await Promise.allSettled(
    files.map((file) => {
      const form = new FormData();
      form.append("file", file);
      form.append("label", file.name);
      return apiClient.post(`/exams/${examId}/resources/file`, form);
    }),
  );
  const failed = results.filter((r) => r.status === "rejected").length;
  return { added: results.length - failed, failed };
}
