/**
 * Browser local-folder sync: persist path → document metadata in localStorage and
 * align the API (upload / delete) with the current tree. See docs/end-user/documents.md.
 */

import { deleteDocument, uploadDocumentFile } from "../api/documents";

const STORAGE_KEY = "verifiedsignal:localDirSync:v1";

export interface DirSyncEntry {
  document_id: string;
  lastModified: number;
  size: number;
}

export interface StoredDirSyncState {
  entries: Record<string, DirSyncEntry>;
}

interface PersistedV1 {
  v: 1;
  entries: Record<string, DirSyncEntry>;
}

function loadPersisted(): PersistedV1 {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { v: 1, entries: {} };
    const p = JSON.parse(raw) as unknown;
    if (!p || typeof p !== "object") return { v: 1, entries: {} };
    const o = p as Record<string, unknown>;
    if (o.v !== 1 || typeof o.entries !== "object" || o.entries === null) return { v: 1, entries: {} };
    return { v: 1, entries: o.entries as Record<string, DirSyncEntry> };
  } catch {
    return { v: 1, entries: {} };
  }
}

function savePersisted(entries: Record<string, DirSyncEntry>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ v: 1, entries } satisfies PersistedV1));
}

export function supportsDirectoryPicker(): boolean {
  return typeof window !== "undefined" && typeof window.showDirectoryPicker === "function";
}

export function loadStoredDirSyncState(): StoredDirSyncState | null {
  const { entries } = loadPersisted();
  if (Object.keys(entries).length === 0) return null;
  return { entries };
}

export function clearStoredDirSyncState(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function filesFromWebkitFileList(files: readonly File[]): File[] {
  return Array.from(files).filter((f) => f.name.length > 0);
}

export function inferRootNameFromPaths(files: readonly File[]): string {
  if (!files.length) return "folder";
  const raw =
    (files[0] as File & { webkitRelativePath?: string }).webkitRelativePath || files[0].name || "folder";
  const normalized = raw.replace(/\\/g, "/");
  const first = normalized.split("/").filter(Boolean)[0];
  return first || "folder";
}

function entryPrefix(rootName: string): string {
  return `${rootName.replace(/::/g, "_")}::`;
}

function relPathOf(file: File): string {
  const p = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
  return p.replace(/^\/+/, "").replace(/\\/g, "/");
}

/**
 * Recursively read files under a directory handle (Chromium File System Access API).
 * Each file gets `webkitRelativePath` set to paths relative to the chosen root.
 */
export async function collectFilesRecursive(root: FileSystemDirectoryHandle): Promise<File[]> {
  const out: File[] = [];

  async function walk(dir: FileSystemDirectoryHandle, base: string): Promise<void> {
    for await (const [name, handle] of dir.entries()) {
      const rel = base ? `${base}/${name}` : name;
      if (handle.kind === "file") {
        const fh = handle as FileSystemFileHandle;
        const file = await fh.getFile();
        Object.defineProperty(file, "webkitRelativePath", {
          value: rel,
          enumerable: true,
          configurable: true,
        });
        out.push(file);
      } else if (handle.kind === "directory") {
        await walk(handle as FileSystemDirectoryHandle, rel);
      }
    }
  }

  await walk(root, "");
  return out;
}

export interface SyncDirectoryWithApiOptions {
  accessToken: string;
  rootName: string;
  files: File[];
  /** When set, sent as multipart `collection_id` for each new upload. */
  collectionId?: string;
  /** When set, sent as multipart `metadata` JSON for each new upload. */
  metadata?: Record<string, unknown>;
  onLog?: (line: string) => void;
}

/**
 * Compare `files` to persisted entries for `rootName`, then upload new paths,
 * re-upload when mtime/size change, and delete API documents for paths removed locally.
 */
export async function syncDirectoryWithApi(opts: SyncDirectoryWithApiOptions): Promise<void> {
  const { accessToken, rootName, files, collectionId, metadata, onLog } = opts;
  const prefix = entryPrefix(rootName);
  const persisted = loadPersisted();
  const entries: Record<string, DirSyncEntry> = { ...persisted.entries };

  const currentRelPaths = new Set(files.map((f) => relPathOf(f)));

  for (const key of Object.keys(entries)) {
    if (!key.startsWith(prefix)) continue;
    const rel = key.slice(prefix.length);
    if (currentRelPaths.has(rel)) continue;
    const row = entries[key];
    if (!row) continue;
    try {
      await deleteDocument(accessToken, row.document_id);
      onLog?.(`Deleted (removed from folder): ${rel}`);
    } catch (e) {
      onLog?.(`Delete failed (${rel}): ${e instanceof Error ? e.message : String(e)}`);
    }
    delete entries[key];
  }

  for (const file of files) {
    const rel = relPathOf(file);
    const key = `${prefix}${rel}`;
    const lm = file.lastModified;
    const sz = file.size;
    const prev = entries[key];
    if (prev && prev.lastModified === lm && prev.size === sz) {
      onLog?.(`Unchanged: ${rel}`);
      continue;
    }
    if (prev) {
      try {
        await deleteDocument(accessToken, prev.document_id);
        onLog?.(`Re-upload (file changed): ${rel}`);
      } catch (e) {
        onLog?.(`Delete before re-upload failed (${rel}): ${e instanceof Error ? e.message : String(e)}`);
      }
    }
    const res = await uploadDocumentFile(accessToken, file, {
      title: rel,
      ...(collectionId ? { collectionId } : {}),
      ...(metadata && Object.keys(metadata).length > 0 ? { metadata } : {}),
    });
    entries[key] = { document_id: res.document_id, lastModified: lm, size: sz };
    onLog?.(`Uploaded: ${rel} → ${res.document_id}`);
  }

  savePersisted(entries);
}
