import { useState } from "react";
import {
  canToggleReviewStatus,
  reviewStatusToggleLabel,
  reviewStatusToggleTarget,
  type ReviewStatusItem,
} from "./reviewStatusEdit";

type Props = {
  item: ReviewStatusItem;
  onSaved: () => Promise<void>;
};

export default function ReviewStatusEditor({ item, onSaved }: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!canToggleReviewStatus(item) || !item.registry_file_id) {
    return null;
  }

  async function toggle(): Promise<void> {
    const nextStatus = reviewStatusToggleTarget(item.review_status);
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/inventory/items/${encodeURIComponent(item.registry_file_id!)}/review-status`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ review_status: nextStatus }),
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

  return (
    <>
      <button type="button" onClick={() => void toggle()} disabled={saving}>
        {saving ? "Saving…" : reviewStatusToggleLabel(item.review_status)}
      </button>
      {error ? <span className="card-review-status-error">{error}</span> : null}
    </>
  );
}
