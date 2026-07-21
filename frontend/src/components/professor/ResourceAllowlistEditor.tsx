// frontend/src/components/professor/ResourceAllowlistEditor.tsx
// AEGIS-121: open-book toggle + URL allowlist editor, shared by the two
// exam-create paths (ExamCreate page and ExamScheduler tab). Controlled: the
// parent owns the state and sends `mode` on POST /exams, then POSTs each URL
// resource with the returned exam id. File uploads are handled separately in a
// draft-exam "Manage resources" panel (they need the exam id first).
import React from "react";

export interface DraftUrlResource {
  label: string;
  url: string;
  embed: boolean;
}

export const newUrlResource = (): DraftUrlResource => ({
  label: "",
  url: "",
  embed: false,
});

interface ResourceAllowlistEditorProps {
  isOpenBook: boolean;
  onToggle: (value: boolean) => void;
  resources: DraftUrlResource[];
  onChange: (resources: DraftUrlResource[]) => void;
  inputClass: string;
}

const ResourceAllowlistEditor: React.FC<ResourceAllowlistEditorProps> = ({
  isOpenBook,
  onToggle,
  resources,
  onChange,
  inputClass,
}) => {
  function patch(i: number, p: Partial<DraftUrlResource>) {
    onChange(resources.map((r, idx) => (idx === i ? { ...r, ...p } : r)));
  }

  return (
    <div>
      <label className="flex items-center gap-2 text-sm text-ink">
        <input
          type="checkbox"
          checked={isOpenBook}
          onChange={(e) => onToggle(e.target.checked)}
          data-testid="open-book-toggle"
        />
        Open-book exam (students see a curated resource panel)
      </label>
      <p className="text-xs text-ash mt-1">
        Resource access is recorded for your review — it is evidence, not a
        lockdown. Uploaded files can be added after the exam is created.
      </p>

      {isOpenBook && (
        <div className="mt-3 space-y-3 border border-hairline rounded-md p-3 bg-surface-card">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-ink">
              Allowed links
            </span>
            <button
              type="button"
              onClick={() => onChange([...resources, newUrlResource()])}
              className="text-xs text-primary-active hover:underline"
            >
              + Add link
            </button>
          </div>

          {resources.length === 0 && (
            <p className="text-xs text-mute">
              No links yet. Add reference URLs students may open in-exam.
            </p>
          )}

          {resources.map((r, i) => (
            <div
              key={i}
              className="space-y-2 border-b border-hairline-soft pb-2"
            >
              <div className="flex gap-2">
                <input
                  className={inputClass}
                  value={r.label}
                  onChange={(e) => patch(i, { label: e.target.value })}
                  placeholder="Label (e.g. MDN HTTP docs)"
                  aria-label={`Resource ${i + 1} label`}
                />
                <button
                  type="button"
                  onClick={() =>
                    onChange(resources.filter((_, idx) => idx !== i))
                  }
                  className="text-xs text-accent-red hover:underline shrink-0"
                  aria-label={`Remove resource ${i + 1}`}
                >
                  Remove
                </button>
              </div>
              <input
                className={inputClass}
                value={r.url}
                onChange={(e) => patch(i, { url: e.target.value })}
                placeholder="https://…"
                aria-label={`Resource ${i + 1} URL`}
              />
              <label className="flex items-center gap-2 text-xs text-mute">
                <input
                  type="checkbox"
                  checked={r.embed}
                  onChange={(e) => patch(i, { embed: e.target.checked })}
                />
                Show inside the exam (only for sites that allow embedding;
                otherwise it opens in a new tab)
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ResourceAllowlistEditor;
