export const COLLECTION_WORKSPACE_TABS = [
  "documents",
  "analytics",
  "models",
  "activity",
] as const;

export type CollectionWorkspaceTab = (typeof COLLECTION_WORKSPACE_TABS)[number];

export const COLLECTION_DOCUMENT_SORTS = [
  "created_at_desc",
  "created_at_asc",
  "name_asc",
  "name_desc",
  "factuality_desc",
  "factuality_asc",
] as const;

export type CollectionDocumentSort = (typeof COLLECTION_DOCUMENT_SORTS)[number];

export function parseWorkspaceTab(raw: string | null): CollectionWorkspaceTab {
  if (!raw) return "documents";
  if ((COLLECTION_WORKSPACE_TABS as readonly string[]).includes(raw)) {
    return raw as CollectionWorkspaceTab;
  }
  return "documents";
}
