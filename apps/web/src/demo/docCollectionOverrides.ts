/** Demo-only: persist per-document collection moves in sessionStorage (API mode uses POST /documents/{id}/move). */
const STORAGE_KEY = "verifiedsignal_demo_doc_collection_v1";

export function loadDemoDocCollectionOverrides(): Record<string, string> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof v === "string") out[k] = v;
    }
    return out;
  } catch {
    return {};
  }
}

export function saveDemoDocCollectionOverrides(map: Record<string, string>): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

export function setDemoDocCollectionOverride(
  documentId: string,
  targetCollectionId: string,
): Record<string, string> {
  const next = { ...loadDemoDocCollectionOverrides(), [documentId]: targetCollectionId };
  saveDemoDocCollectionOverrides(next);
  return next;
}

export function clearDemoDocCollectionOverride(documentId: string): Record<string, string> {
  const cur = loadDemoDocCollectionOverrides();
  if (!(documentId in cur)) return cur;
  const next = { ...cur };
  delete next[documentId];
  saveDemoDocCollectionOverrides(next);
  return next;
}

/** Effective collection for a demo document: override wins, else first id in collectionIds. */
export function effectiveDemoDocumentCollectionId(
  documentId: string,
  defaultCollectionIds: string[],
): string | undefined {
  const o = loadDemoDocCollectionOverrides();
  if (o[documentId]) return o[documentId];
  return defaultCollectionIds[0];
}
