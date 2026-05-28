export type CompletionDateItem = {
  is_registered: boolean;
  scope: string;
  registry_file_id: string | null;
  completion_date: string | null;
  completion_date_source: string | null;
};

export function canEditCompletionDate(item: CompletionDateItem): boolean {
  return (
    item.is_registered === true &&
    item.scope === "completion" &&
    Boolean(item.registry_file_id)
  );
}

export function needsCompletionDateConfirm(item: CompletionDateItem): boolean {
  const source = item.completion_date_source;
  return Boolean(source && source !== "manual");
}

export function buildCompletionDateOverwriteMessage(
  item: CompletionDateItem,
  newDate: string,
): string {
  const current = item.completion_date ?? "(none)";
  const source = item.completion_date_source ?? "unknown";
  return (
    `Replace completed date?\n\n` +
    `Current: ${current} (source: ${source})\n` +
    `New: ${newDate}\n\n` +
    `The new date will be saved as manual.`
  );
}
