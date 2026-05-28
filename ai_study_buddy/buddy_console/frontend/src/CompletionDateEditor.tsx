import { useEffect, useState } from "react";
import {
  buildCompletionDateOverwriteMessage,
  canEditCompletionDate,
  needsCompletionDateConfirm,
  type CompletionDateItem,
} from "./completionDateEdit";

type Props = {
  item: CompletionDateItem;
  onSaved: () => Promise<void>;
};

export default function CompletionDateEditor({ item, onSaved }: Props) {
  const [draft, setDraft] = useState(item.completion_date || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    setDraft(item.completion_date || "");
    setError(null);
    setIsOpen(false);
  }, [item.completion_date, item.registry_file_id]);

  if (!canEditCompletionDate(item) || !item.registry_file_id) {
    return null;
  }

  async function save(): Promise<void> {
    const trimmed = draft.trim();
    if (!trimmed) {
      setError("Pick a completed date.");
      return;
    }
    if (
      needsCompletionDateConfirm(item) &&
      !window.confirm(buildCompletionDateOverwriteMessage(item, trimmed))
    ) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/inventory/items/${encodeURIComponent(item.registry_file_id!)}/completion-date`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ completion_date: trimmed }),
        },
      );
      if (!res.ok) {
        let detail = `Save failed (${res.status})`;
        try {
          const body = (await res.json()) as { detail?: string };
          if (body.detail) detail = body.detail;
        } catch {
          // ignore
        }
        setError(detail);
        return;
      }
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const label = item.completion_date ? "Edit completed date" : "Set completed date";

  return (
    <div className="card-completion-date-edit">
      <button
        type="button"
        className="card-completion-date-toggle"
        onClick={() => setIsOpen((prev) => !prev)}
        disabled={saving}
      >
        {isOpen ? "Hide date editor" : label}
      </button>
      {isOpen ? (
        <div className="card-completion-date-edit-row">
          <label className="card-completion-date-edit-label">
            <span className="card-completion-date-edit-label-text">Completed date</span>
            <input
              type="date"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={saving}
            />
          </label>
          <button
            type="button"
            className="card-completion-date-save"
            onClick={() => void save()}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save"}
          </button>
          {error ? <p className="card-completion-date-error">{error}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
