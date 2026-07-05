import { useRef, useState } from "react";
import apiClient from "../../api/client";

interface ParsedStudent {
  student_id: string;
  name: string;
}

interface ParseError {
  row: number;
  raw: string;
  reason: string;
}

interface Props {
  examId: string;
  onDone: () => void;
}

// ---------------------------------------------------------------------------
// CSV parser — handles quoted fields, CRLF, LF, UTF-8 BOM, commas in names
// split() is not a CSV parser; this is.
// ---------------------------------------------------------------------------

function parseCSVLine(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === "," && !inQuotes) {
      fields.push(current.trim());
      current = "";
    } else {
      current += ch;
    }
  }
  fields.push(current.trim());
  return fields;
}

function parseCSV(raw: string): {
  students: ParsedStudent[];
  errors: ParseError[];
} {
  const text = raw.replace(/^\uFEFF/, ""); // strip UTF-8 BOM from Excel exports
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  const students: ParsedStudent[] = [];
  const errors: ParseError[] = [];
  const seen = new Set<string>();

  lines.forEach((line, index) => {
    const [rawId, rawName] = parseCSVLine(line);

    // Auto-detect header row
    if (index === 0 && rawId?.toLowerCase() === "student_id") return;

    if (!rawId?.trim() || !rawName?.trim()) {
      errors.push({
        row: index + 1,
        raw: line,
        reason: "Missing student_id or name",
      });
      return;
    }

    if (students.length >= 200) {
      errors.push({
        row: index + 1,
        raw: line,
        reason: "Row limit of 200 reached — skipped",
      });
      return;
    }

    if (seen.has(rawId.trim())) return; // silent dedup
    seen.add(rawId.trim());
    students.push({ student_id: rawId.trim(), name: rawName.trim() });
  });

  return { students, errors };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BulkEnrollStep({ examId, onDone }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [students, setStudents] = useState<ParsedStudent[]>([]);
  const [parseErrors, setParseErrors] = useState<ParseError[]>([]);
  const [fileName, setFileName] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [enrolledCount, setEnrolledCount] = useState<number | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setSubmitError(null);
    setEnrolledCount(null);

    const reader = new FileReader();
    reader.onload = (evt) => {
      const { students: parsed, errors } = parseCSV(
        evt.target?.result as string
      );
      setStudents(parsed);
      setParseErrors(errors);
    };
    reader.readAsText(file, "utf-8");
  }

  async function handleEnroll() {
    if (students.length === 0) return;
    setSubmitting(true);
    setSubmitError(null);

    try {
      const res = await apiClient.post<{ enrolled: number; skipped: number }>(
        `/exams/${examId}/enroll`,
        { student_ids: students.map((s) => s.student_id) }
      );
      setEnrolledCount(res.data.enrolled);
      setStudents([]);
      setParseErrors([]);
      setFileName(null);
    } catch (err: unknown) {
      const detail =
        err &&
        typeof err === "object" &&
        "response" in err
          ? (
              err as {
                response?: { data?: { detail?: string } };
              }
            ).response?.data?.detail
          : undefined;
      setSubmitError(
        detail ?? "Enrollment failed — check student IDs and try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

  const previewRows = students.slice(0, 5);
  const remaining = students.length - previewRows.length;

  return (
    <div className="space-y-4 max-w-lg">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-ink font-semibold text-sm">Exam scheduled</p>
          <p className="text-mute text-xs mt-0.5">
            Enroll students via CSV, or skip and do it later.
          </p>
        </div>
        <div className="w-8 h-8 rounded-full bg-accent-green-soft flex items-center justify-center flex-shrink-0">
          <svg
            className="w-4 h-4 text-accent-green"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
      </div>

      {/* Success banner after enrollment */}
      {enrolledCount !== null && (
        <div className="bg-accent-green-soft border border-accent-green/30 rounded-lg px-3 py-2">
          <p className="text-sm text-accent-green font-medium">
            {enrolledCount} student{enrolledCount !== 1 ? "s" : ""} enrolled.
          </p>
          <p className="text-xs text-mute mt-0.5">
            Upload another CSV to enroll more, or click Done.
          </p>
        </div>
      )}

      {/* File picker */}
      <div>
        <p className="text-xs text-mute mb-1">
          CSV format:{" "}
          <code className="bg-surface-doc px-1 rounded">student_id,name</code>{" "}
          — header row optional, max 200 rows
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="px-3 py-2 border border-hairline rounded-lg text-sm text-ink hover:bg-surface-doc transition-colors"
        >
          {fileName ? `📄 ${fileName}` : "Choose CSV file"}
        </button>
      </div>

      {/* Parse errors */}
      {parseErrors.length > 0 && (
        <div className="bg-red-50 border border-accent-red/20 rounded-lg p-3">
          <p className="text-xs font-medium text-accent-red mb-1">
            {parseErrors.length} invalid row
            {parseErrors.length !== 1 ? "s" : ""} — valid rows will still be
            enrolled
          </p>
          <ul className="text-xs text-accent-red space-y-0.5 max-h-20 overflow-y-auto">
            {parseErrors.map((e) => (
              <li key={`${e.row}-${e.raw}`}>
                Row {e.row}: {e.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Preview table */}
      {students.length > 0 && (
        <div>
          <p className="text-xs text-mute mb-1">
            Preview — {students.length} student
            {students.length !== 1 ? "s" : ""} to enroll
          </p>
          <table className="w-full text-xs border border-hairline rounded-lg overflow-hidden">
            <thead className="bg-surface-doc text-mute uppercase">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Student ID</th>
                <th className="px-3 py-2 text-left font-medium">Name</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {previewRows.map((s) => (
                <tr key={s.student_id}>
                  <td className="px-3 py-2 font-mono text-mute">
                    {s.student_id}
                  </td>
                  <td className="px-3 py-2 text-ink">{s.name}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {remaining > 0 && (
            <p className="text-xs text-ash mt-1">
              + {remaining} more row{remaining !== 1 ? "s" : ""}
            </p>
          )}
        </div>
      )}

      {/* Submit error */}
      {submitError && (
        <p className="text-xs text-accent-red bg-red-50 border border-accent-red/20 rounded p-2">
          {submitError}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-1">
        {students.length > 0 && (
          <button
            type="button"
            onClick={handleEnroll}
            disabled={submitting}
            className="flex-1 py-2.5 bg-primary text-ink font-semibold text-sm rounded-lg
                       disabled:opacity-50 disabled:cursor-not-allowed
                       hover:bg-primary-pressed transition-colors"
          >
            {submitting
              ? "Enrolling…"
              : `Enroll ${students.length} student${students.length !== 1 ? "s" : ""}`}
          </button>
        )}
        <button
          type="button"
          onClick={onDone}
          className="flex-1 py-2.5 border border-hairline text-ink text-sm
                     rounded-lg hover:bg-surface-doc transition-colors"
        >
          Done
        </button>
      </div>
    </div>
  );
}
