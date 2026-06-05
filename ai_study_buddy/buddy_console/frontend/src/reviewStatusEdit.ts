export type ReviewStatusItem = {
  has_marking: boolean | null;
  registry_file_id: string | null;
  review_status: string | null;
};

export function canToggleReviewStatus(item: ReviewStatusItem): boolean {
  return item.has_marking === true && Boolean(item.registry_file_id);
}

export function reviewStatusToggleLabel(reviewStatus: string | null): string {
  return reviewStatus === "completed" ? "Revert review" : "Mark review completed";
}

export function reviewStatusToggleTarget(reviewStatus: string | null): "completed" | "not_started" {
  return reviewStatus === "completed" ? "not_started" : "completed";
}
