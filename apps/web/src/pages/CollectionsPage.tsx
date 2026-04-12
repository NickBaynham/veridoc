import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  createCollection,
  deleteCollection,
  listCollections,
  updateCollection,
} from "../api/collections";
import { ApiError } from "../api/http";
import { useAuth } from "../context/AuthContext";
import { isApiBackend } from "../config";
import type { CollectionRow } from "../api/types";
import { DEMO_COLLECTIONS } from "../demo";

const DEMO_COLLECTIONS_STORAGE = "verifiedsignal_demo_collections_v1";
const DEMO_ORG_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

function slugifyCollectionName(name: string): string {
  const s = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return s.length > 0 ? s : "collection";
}

function loadDemoCollectionsFromStorage(): CollectionRow[] | null {
  try {
    const raw = sessionStorage.getItem(DEMO_COLLECTIONS_STORAGE);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return null;
    return parsed as CollectionRow[];
  } catch {
    return null;
  }
}

function defaultDemoCollectionRows(): CollectionRow[] {
  return DEMO_COLLECTIONS.map((c) => ({
    id: c.id,
    organization_id: DEMO_ORG_ID,
    name: c.name,
    slug: slugifyCollectionName(c.name),
    document_count: c.documentCount,
    created_at: c.updatedAt,
  }));
}

export function CollectionsPage() {
  const { accessToken } = useAuth();
  const api = isApiBackend();
  const [rows, setRows] = useState<CollectionRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");

  const persistDemoRows = useCallback((next: CollectionRow[]) => {
    setRows(next);
    sessionStorage.setItem(DEMO_COLLECTIONS_STORAGE, JSON.stringify(next));
  }, []);

  const loadApi = useCallback(async () => {
    if (!api || !accessToken) return;
    setBusy(true);
    try {
      const res = await listCollections(accessToken);
      setRows(res.collections);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load collections");
    } finally {
      setBusy(false);
    }
  }, [api, accessToken]);

  useEffect(() => {
    if (api && accessToken) {
      void loadApi();
      return;
    }
    if (!api) {
      const stored = loadDemoCollectionsFromStorage();
      setRows(stored ?? defaultDemoCollectionRows());
    }
  }, [api, accessToken, loadApi]);

  const canMutate = useMemo(() => (api ? !!accessToken : true), [api, accessToken]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      if (api && accessToken) {
        const created = await createCollection(accessToken, { name });
        setRows((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
        setNewName("");
      } else {
        const id = crypto.randomUUID();
        const row: CollectionRow = {
          id,
          organization_id: DEMO_ORG_ID,
          name,
          slug: slugifyCollectionName(name),
          document_count: 0,
          created_at: new Date().toISOString(),
        };
        persistDemoRows([...rows, row].sort((a, b) => a.name.localeCompare(b.name)));
        setNewName("");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create collection");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveRename(id: string) {
    const name = editDraft.trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      if (api && accessToken) {
        const updated = await updateCollection(accessToken, id, { name });
        setRows((prev) => prev.map((r) => (r.id === id ? updated : r)));
      } else {
        persistDemoRows(
          rows.map((r) =>
            r.id === id
              ? {
                  ...r,
                  name,
                  slug: slugifyCollectionName(name),
                }
              : r,
          ),
        );
      }
      setEditingId(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to rename collection");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id: string, label: string) {
    if (!window.confirm(`Delete collection “${label}”? Documents in it will be removed in API mode.`)) return;
    setBusy(true);
    setError(null);
    try {
      if (api && accessToken) {
        await deleteCollection(accessToken, id);
        setRows((prev) => prev.filter((r) => r.id !== id));
      } else {
        persistDemoRows(rows.filter((r) => r.id !== id));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete collection");
    } finally {
      setBusy(false);
    }
  }

  if (api) {
    return (
      <>
        <h1 className="page-title">Collections</h1>
        <p className="page-sub">
          Create and rename collections via <code>POST</code> / <code>PATCH /api/v1/collections/…</code>. Deleting a
          collection removes its documents (cascade). Each row still links to{" "}
          <code>GET …/analytics</code> for facet rollups.
        </p>
        {error ? <p className="error-text">{error}</p> : null}
        {canMutate ? (
          <div className="card" style={{ marginBottom: "1rem" }}>
            <h2 style={{ marginTop: 0, fontSize: "1rem" }}>New collection</h2>
            <form onSubmit={(e) => void onCreate(e)} style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <input
                style={{
                  flex: "1 1 220px",
                  minWidth: 0,
                  padding: "0.5rem 0.65rem",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                }}
                placeholder="Name"
                value={newName}
                disabled={busy}
                onChange={(e) => setNewName(e.target.value)}
                aria-label="New collection name"
              />
              <button type="submit" className="btn btn-primary" disabled={busy || !newName.trim()}>
                {busy ? "…" : "Create"}
              </button>
            </form>
          </div>
        ) : null}
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Documents</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 600 }}>
                    {editingId === c.id ? (
                      <span style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                        <input
                          value={editDraft}
                          disabled={busy}
                          onChange={(e) => setEditDraft(e.target.value)}
                          aria-label={`Rename ${c.name}`}
                          style={{ maxWidth: "100%" }}
                        />
                        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onSaveRename(c.id)}>
                          Save
                        </button>
                        <button
                          type="button"
                          className="btn"
                          disabled={busy}
                          onClick={() => {
                            setEditingId(null);
                          }}
                        >
                          Cancel
                        </button>
                      </span>
                    ) : (
                      c.name
                    )}
                  </td>
                  <td>{c.document_count}</td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                    {new Date(c.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      <Link to={`/collections/${c.id}/analytics`}>Analytics →</Link>
                      {canMutate ? (
                        <>
                          <button
                            type="button"
                            className="btn"
                            disabled={busy || editingId !== null}
                            onClick={() => {
                              setEditingId(c.id);
                              setEditDraft(c.name);
                            }}
                          >
                            Rename
                          </button>
                          <button type="button" className="btn" disabled={busy || editingId !== null} onClick={() => void onDelete(c.id, c.name)}>
                            Delete
                          </button>
                        </>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && !error ? (
            <p style={{ color: "var(--text-muted)", marginTop: "1rem" }}>No collections returned for your account.</p>
          ) : null}
        </div>
      </>
    );
  }

  return (
    <>
      <h1 className="page-title">Collections</h1>
      <p className="page-sub">
        Demo workspace — create, rename, and remove collections (stored in <code>sessionStorage</code> for this
        browser). <strong>Use Case 4</strong> analytics links unchanged.
      </p>
      {error ? <p className="error-text">{error}</p> : null}
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1rem" }}>New collection</h2>
        <form onSubmit={(e) => void onCreate(e)} style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <input
            style={{ flex: "1 1 220px", minWidth: 0, padding: "0.5rem 0.65rem", borderRadius: 6, border: "1px solid var(--border)" }}
            placeholder="Name"
            value={newName}
            disabled={busy}
            onChange={(e) => setNewName(e.target.value)}
            aria-label="New collection name"
          />
          <button type="submit" className="btn btn-primary" disabled={busy || !newName.trim()}>
            {busy ? "…" : "Create"}
          </button>
        </form>
      </div>
      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Documents</th>
              <th>Updated</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td style={{ fontWeight: 600 }}>
                  {editingId === c.id ? (
                    <span style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                      <input
                        value={editDraft}
                        disabled={busy}
                        onChange={(e) => setEditDraft(e.target.value)}
                        aria-label={`Rename ${c.name}`}
                      />
                      <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void onSaveRename(c.id)}>
                        Save
                      </button>
                      <button type="button" className="btn" disabled={busy} onClick={() => setEditingId(null)}>
                        Cancel
                      </button>
                    </span>
                  ) : (
                    c.name
                  )}
                </td>
                <td>{c.document_count}</td>
                <td style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                  {new Date(c.created_at).toLocaleDateString()}
                </td>
                <td>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    <Link to={`/collections/${c.id}/analytics`}>Analytics →</Link>
                    <button
                      type="button"
                      className="btn"
                      disabled={busy || editingId !== null}
                      onClick={() => {
                        setEditingId(c.id);
                        setEditDraft(c.name);
                      }}
                    >
                      Rename
                    </button>
                    <button type="button" className="btn" disabled={busy || editingId !== null} onClick={() => void onDelete(c.id, c.name)}>
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
