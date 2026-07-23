// frontend/src/components/professor/ResourceAllowlistEditor.tsx
// AEGIS-121: open-book toggle + resource editor, shared by the two exam-create
// paths (ExamCreate page and ExamScheduler tab). Controlled: the parent owns
// the state and sends `mode` on POST /exams, then POSTs each URL resource and
// uploads each PDF with the returned exam id (two-phase — resources need the
// exam id first). More resources can also be managed later via the draft/open
// exam's "Manage resources" panel.
import React from "react";

export interface DraftUrlResource {
  label: string;
  url: string;
  embed: boolean;
}

const newUrlResource = (): DraftUrlResource => ({
  label: "",
  url: "",
  // Resources are always shown inside the exam panel (no new-tab option), so
  // every URL is "embedded" from the student's perspective (AEGIS-121).
  embed: true,
});

interface ResourceAllowlistEditorProps {
  isOpenBook: boolean;
  onToggle: (value: boolean) => void;
  resources: DraftUrlResource[];
  onChange: (resources: DraftUrlResource[]) => void;
  files: File[];
  onFilesChange: (files: File[]) => void;
  inputClass: string;
}

const ResourceAllowlistEditor: React.FC<ResourceAllowlistEditorProps> = ({
  isOpenBook,
  onToggle,
  resources,
  onChange,
  files,
  onFilesChange,
  inputClass,
}) => {
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  function patch(i: number, p: Partial<DraftUrlResource>) {
    onChange(resources.map((r, idx) => (idx === i ? { ...r, ...p } : r)));
  }

  function addFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    onFilesChange([...files, ...Array.from(list)]);
    if (fileInputRef.current) fileInputRef.current.value = ""; // allow re-add
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
        lockdown. Add reference links and/or upload PDFs; more can be added
        later from the exam's Manage resources panel.
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
            </div>
          ))}

          {/* PDF uploads (AEGIS-121) — collected here, uploaded after the exam
              is created since the upload endpoint needs the exam id. */}
          <div className="border-t border-hairline-soft pt-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-ink">
                Uploaded PDFs
              </span>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-xs text-primary-active hover:underline"
              >
                + Upload PDF
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              multiple
              onChange={(e) => addFiles(e.target.files)}
              className="hidden"
              aria-label="Upload PDF resources"
            />
            {files.length === 0 ? (
              <p className="text-xs text-mute mt-1">
                No PDFs yet. Upload reference documents students can read
                in-exam.
              </p>
            ) : (
              <ul className="mt-1 space-y-1">
                {files.map((f, i) => (
                  <li
                    key={i}
                    className="flex items-center justify-between text-xs text-body"
                  >
                    <span className="truncate">📄 {f.name}</span>
                    <button
                      type="button"
                      onClick={() =>
                        onFilesChange(files.filter((_, idx) => idx !== i))
                      }
                      className="text-accent-red hover:underline shrink-0 ml-2"
                      aria-label={`Remove file ${i + 1}`}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ResourceAllowlistEditor;
