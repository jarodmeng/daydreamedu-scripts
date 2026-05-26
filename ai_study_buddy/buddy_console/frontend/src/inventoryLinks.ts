export type InventoryItemLinkShape = {
  absolute_path: string;
  root_id: string;
  registry_file_id: string | null;
  has_marking: boolean | null;
  student_id: string | null;
};

export function relPathForItem(
  item: Pick<InventoryItemLinkShape, "absolute_path" | "root_id">,
  rootsById: Record<string, string>,
): string | null {
  const root = rootsById[item.root_id];
  if (!root) return null;
  const abs = String(item.absolute_path).replace(/\\/g, "/");
  const rootNorm = String(root).replace(/\\/g, "/").replace(/\/+$/, "");
  const prefix = `${rootNorm}/`;
  return abs.startsWith(prefix) ? abs.slice(prefix.length) : null;
}

export function buildReviewHref(
  item: Pick<InventoryItemLinkShape, "registry_file_id" | "has_marking" | "student_id">,
): string | null {
  if (!item.registry_file_id || !item.has_marking) return null;
  const params = new URLSearchParams();
  params.set("attempt_id", item.registry_file_id);
  if (item.student_id) params.set("student_id", item.student_id);
  return `/review?${params.toString()}`;
}

export function buildPdfHref(
  item: Pick<InventoryItemLinkShape, "absolute_path" | "root_id">,
  rootsById: Record<string, string>,
): string | null {
  const rel = relPathForItem(item, rootsById);
  if (!rel) return null;
  const params = new URLSearchParams();
  params.set("id", item.root_id);
  params.set("rel", rel);
  return `/pdf?${params.toString()}`;
}
