import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  fetchCollectionActivity,
  fetchCollectionAnalytics,
  fetchCollectionDetail,
  fetchCollectionDocuments,
  listCollections,
} from "../api/collections";
import { deleteDocument, moveDocument } from "../api/documents";
import { ApiError } from "../api/http";
import type {
  CollectionActivityItem,
  CollectionAnalyticsResponse,
  CollectionDetail,
  CollectionDocumentItem,
  CollectionDocumentsListResponse,
  CollectionRow,
} from "../api/types";
import { useAuth } from "../context/AuthContext";
import { useDemoData } from "../context/DemoDataContext";
import { isApiBackend } from "../config";
import { DEMO_ANALYTICS, DEMO_COLLECTIONS, DEMO_DOCUMENTS } from "../demo";
import type { DemoDocument } from "../demo/types";
import {
  clearDemoDocCollectionOverride,
  effectiveDemoDocumentCollectionId,
  setDemoDocCollectionOverride,
} from "../demo/docCollectionOverrides";
import {
  COLLECTION_DOCUMENT_SORTS,
  COLLECTION_WORKSPACE_TABS,
  type CollectionDocumentSort,
  type CollectionWorkspaceTab,
  parseWorkspaceTab,
} from "../lib/collectionWorkspace";
import { CollectionModelsTab } from "../components/CollectionModelsTab";
import { normalizeStatus, statusBadgeClass } from "../lib/statusBadge";

const PAGE_SIZE = 25;

const DEMO_ORG_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

function demoCollectionRowsFromStorage(): CollectionRow[] {
  try {
    const raw = sessionStorage.getItem("verifiedsignal_demo_collections_v1");
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed as CollectionRow[];
  } catch {
    return [];
  }
}

function allDemoCollectionRows(): CollectionRow[] {
  const stored = demoCollectionRowsFromStorage();
  if (stored.length) return stored;
  return DEMO_COLLECTIONS.map((c) => ({
    id: c.id,
    organization_id: DEMO_ORG_ID,
    name: c.name,
    slug: c.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
    document_count: c.documentCount,
    created_at: c.updatedAt,
  }));
}

/** Map demo "complete" to canonical "completed" for filters and badges. */
function pipelineStatus(doc: DemoDocument | CollectionDocumentItem): string {
  const s = "status" in doc && typeof doc.status === "string" ? doc.status : "";
  const n = normalizeStatus(s);
  if (n === "complete") return "completed";
  return n;
}

function formatScore(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(2);
}

function scoreFromDemoDoc(d: DemoDocument): { factuality: number | null; ai: number | null } {
  const factuality = d.scores.find((x) => x.id === "factuality")?.value ?? null;
  const ai = d.scores.find((x) => x.id === "ai")?.value ?? null;
  return { factuality, ai };
}

function tabLabel(t: CollectionWorkspaceTab): string {
  switch (t) {
    case "documents":
      return "Documents";
    case "analytics":
      return "Analytics";
    case "models":
      return "Models";
    case "activity":
      return "Activity";
    default:
      return t;
  }
}

function sortLabel(s: CollectionDocumentSort): string {
  switch (s) {
    case "created_at_desc":
      return "Uploaded (newest)";
    case "created_at_asc":
      return "Uploaded (oldest)";
    case "name_asc":
      return "Name (A–Z)";
    case "name_desc":
      return "Name (Z–A)";
    case "factuality_desc":
      return "Factuality (high)";
    case "factuality_asc":
      return "Factuality (low)";
    default:
      return s;
  }
}

function demoActivityItems(docs: DemoDocument[]): CollectionActivityItem[] {
  const rows: CollectionActivityItem[] = [];
  for (const d of docs) {
    rows.push({
      id: `${d.id}-evt`,
      document_id: d.id,
      document_title: d.title,
      pipeline_run_id: "00000000-0000-4000-8000-000000000099",
      event_type: "stage_complete",
      stage: d.currentStage ?? "score",
      step_index: 2,
      payload: {},
      created_at: d.ingestedAt,
    });
  }
  return rows.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
}

export function CollectionDetailPage() {
  const { collectionId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { accessToken } = useAuth();
  const api = isApiBackend();
  const { deleteDemoDocument, isDemoDocumentDeleted } = useDemoData();

  const tab = parseWorkspaceTab(searchParams.get("tab"));
  const setTab = useCallback(
    (next: CollectionWorkspaceTab) => {
      setSearchParams(
        (prev) => {
          const p = new URLSearchParams(prev);
          if (next === "documents") p.delete("tab");
          else p.set("tab", next);
          return p;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const [banner, setBanner] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [detail, setDetail] = useState<CollectionDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [docList, setDocList] = useState<CollectionDocumentsListResponse | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState<CollectionDocumentSort>("created_at_desc");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [searchQ, setSearchQ] = useState("");

  const [activityItems, setActivityItems] = useState<CollectionActivityItem[] | null>(null);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [activityLoading, setActivityLoading] = useState(false);

  const [analyticsCompact, setAnalyticsCompact] = useState<CollectionAnalyticsResponse | null>(null);
  const [analyticsError, setAnalyticsError] = useState<string | null>(null);

  const [collectionsForMove, setCollectionsForMove] = useState<CollectionRow[]>([]);
  const [moveDoc, setMoveDoc] = useState<CollectionDocumentItem | DemoDocument | null>(null);
  const [moveTargetId, setMoveTargetId] = useState("");
  const [moveBusy, setMoveBusy] = useState(false);

  const [createModelOpen, setCreateModelOpen] = useState(false);

  const [demoOverrideTick, setDemoOverrideTick] = useState(0);

  const demoRows = allDemoCollectionRows();
  const demoMeta = collectionId ? demoRows.find((c) => c.id === collectionId) : undefined;

  useEffect(() => {
    const t = window.setTimeout(() => setSearchQ(searchDraft.trim()), 350);
    return () => window.clearTimeout(t);
  }, [searchDraft]);

  useEffect(() => {
    setOffset(0);
  }, [searchQ, statusFilter, sort, collectionId]);

  useEffect(() => {
    if (!api || !accessToken || !collectionId) return;
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    void fetchCollectionDetail(accessToken, collectionId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e) => {
        if (!cancelled) {
          setDetail(null);
          setDetailError(e instanceof ApiError ? e.message : "Failed to load collection");
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api, accessToken, collectionId]);

  useEffect(() => {
    if (!api || !accessToken || !collectionId) return;
    let cancelled = false;
    void listCollections(accessToken)
      .then((r) => {
        if (!cancelled) setCollectionsForMove(r.collections);
      })
      .catch(() => {
        if (!cancelled) setCollectionsForMove([]);
      });
    return () => {
      cancelled = true;
    };
  }, [api, accessToken, collectionId]);

  useEffect(() => {
    if (!api || !accessToken || !collectionId || tab !== "documents") return;
    let cancelled = false;
    setDocLoading(true);
    setDocError(null);
    void fetchCollectionDocuments(accessToken, collectionId, {
      limit: PAGE_SIZE,
      offset,
      sort,
      q: searchQ || undefined,
      status: statusFilter || undefined,
    })
      .then((res) => {
        if (!cancelled) setDocList(res);
      })
      .catch((e) => {
        if (!cancelled) {
          setDocList(null);
          setDocError(e instanceof ApiError ? e.message : "Failed to load documents");
        }
      })
      .finally(() => {
        if (!cancelled) setDocLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api, accessToken, collectionId, tab, offset, sort, searchQ, statusFilter]);

  useEffect(() => {
    if (!api || !accessToken || !collectionId || tab !== "activity") return;
    let cancelled = false;
    setActivityLoading(true);
    setActivityError(null);
    void fetchCollectionActivity(accessToken, collectionId, { limit: 100 })
      .then((r) => {
        if (!cancelled) setActivityItems(r.items);
      })
      .catch((e) => {
        if (!cancelled) {
          setActivityItems(null);
          setActivityError(e instanceof ApiError ? e.message : "Failed to load activity");
        }
      })
      .finally(() => {
        if (!cancelled) setActivityLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api, accessToken, collectionId, tab]);

  useEffect(() => {
    if (!api || !accessToken || !collectionId || tab !== "analytics") return;
    let cancelled = false;
    setAnalyticsError(null);
    void fetchCollectionAnalytics(accessToken, collectionId)
      .then((a) => {
        if (!cancelled) setAnalyticsCompact(a);
      })
      .catch((e) => {
        if (!cancelled) {
          setAnalyticsCompact(null);
          setAnalyticsError(e instanceof ApiError ? e.message : "Failed to load analytics");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [api, accessToken, collectionId, tab]);

  const demoDocumentsInCollection = useMemo(() => {
    if (api || !collectionId) return [];
    return DEMO_DOCUMENTS.filter((d) => !isDemoDocumentDeleted(d.id)).filter((d) => {
      const eff = effectiveDemoDocumentCollectionId(d.id, d.collectionIds);
      return eff === collectionId;
    });
  }, [api, collectionId, isDemoDocumentDeleted, demoOverrideTick]);

  const demoFilteredSorted = useMemo(() => {
    let rows = demoDocumentsInCollection;
    if (statusFilter) {
      const want = normalizeStatus(statusFilter);
      rows = rows.filter((d) => pipelineStatus(d) === want);
    }
    if (searchQ) {
      const q = searchQ.toLowerCase();
      rows = rows.filter(
        (d) =>
          d.title.toLowerCase().includes(q) ||
          d.filename.toLowerCase().includes(q) ||
          d.id.toLowerCase().includes(q),
      );
    }
    const sorted = [...rows];
    if (sort === "created_at_desc") {
      sorted.sort((a, b) => new Date(b.ingestedAt).getTime() - new Date(a.ingestedAt).getTime());
    } else if (sort === "created_at_asc") {
      sorted.sort((a, b) => new Date(a.ingestedAt).getTime() - new Date(b.ingestedAt).getTime());
    } else if (sort === "name_asc") {
      sorted.sort((a, b) => a.title.localeCompare(b.title));
    } else if (sort === "name_desc") {
      sorted.sort((a, b) => b.title.localeCompare(a.title));
    } else if (sort === "factuality_desc" || sort === "factuality_asc") {
      const mul = sort === "factuality_desc" ? -1 : 1;
      sorted.sort((a, b) => {
        const fa = scoreFromDemoDoc(a).factuality ?? -1;
        const fb = scoreFromDemoDoc(b).factuality ?? -1;
        return mul * (fa - fb);
      });
    }
    return sorted;
  }, [demoDocumentsInCollection, searchQ, sort, statusFilter]);

  const demoPageSlice = useMemo(() => {
    const total = demoFilteredSorted.length;
    const items = demoFilteredSorted.slice(offset, offset + PAGE_SIZE);
    return { items, total };
  }, [demoFilteredSorted, offset]);

  const demoActivity = useMemo(() => {
    if (api || !collectionId) return [];
    return demoActivityItems(demoDocumentsInCollection);
  }, [api, collectionId, demoDocumentsInCollection]);

  if (!collectionId) {
    return (
      <>
        <h1 className="page-title">Collection not found</h1>
        <p className="page-sub">
          <Link to="/collections">Back to collections</Link>
        </p>
      </>
    );
  }

  if (!api && !demoMeta) {
    return (
      <>
        <h1 className="page-title">Collection not found</h1>
        <p className="page-sub">
          <Link to="/collections">Back to collections</Link>
        </p>
      </>
    );
  }

  if (api && detailError) {
    return (
      <>
        <h1 className="page-title">Error</h1>
        <p className="error-text">{detailError}</p>
        <p className="page-sub">
          <Link to="/collections">Back to collections</Link>
        </p>
      </>
    );
  }

  if (api && detailLoading && !detail) {
    return <p className="page-sub">Loading…</p>;
  }

  if (api && !detail) {
    return (
      <>
        <h1 className="page-title">Collection not found</h1>
        <p className="page-sub">
          <Link to="/collections">Back to collections</Link>
        </p>
      </>
    );
  }

  const title = api && detail ? detail.name : demoMeta!.name;
  const headerDocCount = api && detail ? detail.document_count : demoDocumentsInCollection.length;
  const lastUpdated =
    api && detail?.last_updated
      ? new Date(detail.last_updated).toLocaleString()
      : !api && demoMeta
        ? new Date(demoMeta.created_at).toLocaleString()
        : "—";

  async function onDeleteRow(item: CollectionDocumentItem | DemoDocument) {
    const id = item.id;
    const label = "title" in item && item.title ? item.title : id;
    if (!window.confirm(`Delete “${label}”? This cannot be undone in API mode.`)) return;
    try {
      if (api && accessToken) {
        await deleteDocument(accessToken, id);
        setBanner({ kind: "ok", text: "Document deleted." });
        setOffset(0);
        void refreshApiDocuments();
        if (detail && collectionId) {
          void fetchCollectionDetail(accessToken!, collectionId).then(setDetail).catch(() => {});
        }
      } else {
        deleteDemoDocument(id);
        clearDemoDocCollectionOverride(id);
        setBanner({ kind: "ok", text: "Document removed (demo)." });
        setDemoOverrideTick((x) => x + 1);
      }
    } catch (e) {
      setBanner({
        kind: "err",
        text: e instanceof ApiError ? e.message : "Delete failed",
      });
    }
  }

  function refreshApiDocuments() {
    if (!api || !accessToken || !collectionId) return;
    setDocLoading(true);
    void fetchCollectionDocuments(accessToken, collectionId, {
      limit: PAGE_SIZE,
      offset,
      sort,
      q: searchQ || undefined,
      status: statusFilter || undefined,
    })
      .then(setDocList)
      .catch((e) => setDocError(e instanceof ApiError ? e.message : "Failed to load documents"))
      .finally(() => setDocLoading(false));
  }

  async function confirmMove() {
    if (!moveDoc || !moveTargetId || moveTargetId === collectionId) return;
    setMoveBusy(true);
    try {
      if (api && accessToken) {
        await moveDocument(accessToken, moveDoc.id, moveTargetId);
        setBanner({ kind: "ok", text: "Document moved." });
        setMoveDoc(null);
        setMoveTargetId("");
        refreshApiDocuments();
        if (collectionId) {
          void fetchCollectionDetail(accessToken, collectionId).then(setDetail).catch(() => {});
        }
      } else {
        setDemoDocCollectionOverride(moveDoc.id, moveTargetId);
        setBanner({ kind: "ok", text: "Document moved (demo)." });
        setMoveDoc(null);
        setMoveTargetId("");
        setDemoOverrideTick((x) => x + 1);
      }
    } catch (e) {
      setBanner({
        kind: "err",
        text: e instanceof ApiError ? e.message : "Move failed",
      });
    } finally {
      setMoveBusy(false);
    }
  }

  const moveTargets = api
    ? collectionsForMove.filter((c) => c.id !== collectionId)
    : allDemoCollectionRows().filter((c) => c.id !== collectionId);

  return (
    <>
      <div style={{ marginBottom: "1rem" }}>
        <Link to="/collections" style={{ fontSize: "0.9rem" }}>
          ← Collections
        </Link>
      </div>

      {banner ? (
        <p className={banner.kind === "ok" ? "page-sub" : "error-text"} style={{ marginBottom: "0.75rem" }}>
          {banner.text}
        </p>
      ) : null}

      <header style={{ marginBottom: "1rem" }}>
        <h1 className="page-title" style={{ marginBottom: "0.35rem" }}>
          {title}
        </h1>
        <p className="page-sub" style={{ marginTop: 0 }}>
          Workspace ·{" "}
          {api ? (
            <span>
              <code>GET /api/v1/collections/{"{id}"}</code> summary and{" "}
              <code>/documents</code> directory.
            </span>
          ) : (
            <span>Demo inventory — moves persist in this browser session.</span>
          )}
        </p>
        <div
          className="kpi-grid"
          style={{ marginTop: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}
        >
          <div className="kpi-card">
            <div className="label">Documents</div>
            <div className="value">{headerDocCount}</div>
          </div>
          <div className="kpi-card">
            <div className="label">Last updated</div>
            <div className="value" style={{ fontSize: "0.95rem" }}>
              {lastUpdated}
            </div>
          </div>
          {api && detail ? (
            <>
              <div className="kpi-card">
                <div className="label">Avg factuality</div>
                <div className="value" style={{ fontSize: "1.05rem" }}>
                  {formatScore(detail.avg_canonical_factuality)}
                </div>
              </div>
              <div className="kpi-card">
                <div className="label">Failed</div>
                <div className="value">{detail.failed_document_count}</div>
              </div>
              <div className="kpi-card">
                <div className="label">In progress</div>
                <div className="value">{detail.in_progress_document_count}</div>
              </div>
            </>
          ) : null}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: "0.75rem" }}>
          <Link className="btn btn-primary" to={`/library/upload?collection=${encodeURIComponent(collectionId)}`}>
            Upload document
          </Link>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setTab("models");
              setCreateModelOpen(true);
            }}
          >
            Build model
          </button>
          <Link className="btn" to={`/collections/${collectionId}/analytics`}>
            Open analytics page
          </Link>
        </div>
      </header>

      <div
        role="tablist"
        aria-label="Collection workspace sections"
        style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: "1rem" }}
      >
        {COLLECTION_WORKSPACE_TABS.map((t: CollectionWorkspaceTab) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={tab === t ? "btn btn-primary" : "btn"}
            onClick={() => setTab(t)}
          >
            {tabLabel(t)}
          </button>
        ))}
      </div>

      {tab === "documents" ? (
        <section aria-labelledby="documents-heading">
          <h2 id="documents-heading" className="sr-only">
            Documents
          </h2>
          <div className="card" style={{ marginBottom: "1rem" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
              <label style={{ flex: "1 1 200px" }}>
                <span style={{ display: "block", fontSize: "0.85rem", marginBottom: 4 }}>Search</span>
                <input
                  value={searchDraft}
                  onChange={(e) => setSearchDraft(e.target.value)}
                  placeholder="Title or filename"
                  style={{ width: "100%", padding: "0.45rem 0.5rem", borderRadius: 6, border: "1px solid var(--border)" }}
                />
              </label>
              <label>
                <span style={{ display: "block", fontSize: "0.85rem", marginBottom: 4 }}>Status</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  style={{ padding: "0.45rem 0.5rem", borderRadius: 6, border: "1px solid var(--border)" }}
                >
                  <option value="">All</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                  <option value="queued">Queued</option>
                  <option value="created">Created</option>
                  <option value="processing">Processing</option>
                </select>
              </label>
              <label>
                <span style={{ display: "block", fontSize: "0.85rem", marginBottom: 4 }}>Sort</span>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as CollectionDocumentSort)}
                  style={{ padding: "0.45rem 0.5rem", borderRadius: 6, border: "1px solid var(--border)" }}
                >
                  {COLLECTION_DOCUMENT_SORTS.map((s: CollectionDocumentSort) => (
                    <option key={s} value={s}>
                      {sortLabel(s)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {docError ? <p className="error-text">{docError}</p> : null}

          {api && docLoading && !docList ? <p className="page-sub">Loading documents…</p> : null}

          {!api || docList ? (
            <div className="card">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Source</th>
                    <th>Uploaded</th>
                    <th>Factuality</th>
                    <th>AI prob.</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {api && docList
                    ? docList.items.map((row) => (
                        <tr
                          key={row.id}
                          style={{ cursor: "pointer" }}
                          onClick={() => navigate(`/documents/${row.id}`)}
                        >
                          <td style={{ fontWeight: 600 }}>
                            {row.title || row.original_filename || row.id.slice(0, 8)}
                          </td>
                          <td>
                            <span className={statusBadgeClass(row.status)}>{row.status}</span>
                          </td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                            {row.primary_source_kind ?? "—"}
                          </td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                            {new Date(row.created_at).toLocaleString()}
                          </td>
                          <td>{formatScore(row.canonical_score?.factuality_score)}</td>
                          <td>{formatScore(row.canonical_score?.ai_generation_probability)}</td>
                          <td onClick={(e) => e.stopPropagation()}>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                              <Link className="btn" to={`/documents/${row.id}`} onClick={(e) => e.stopPropagation()}>
                                View
                              </Link>
                              <button type="button" className="btn" onClick={() => setMoveDoc(row)}>
                                Move
                              </button>
                              <button type="button" className="btn" onClick={() => void onDeleteRow(row)}>
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    : null}
                  {!api
                    ? demoPageSlice.items.map((row) => {
                        const { factuality, ai } = scoreFromDemoDoc(row);
                        return (
                          <tr
                            key={row.id}
                            style={{ cursor: "pointer" }}
                            onClick={() => navigate(`/documents/${row.id}`)}
                          >
                            <td style={{ fontWeight: 600 }}>{row.title}</td>
                            <td>
                              <span className={statusBadgeClass(row.status)}>{pipelineStatus(row)}</span>
                            </td>
                            <td style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                              {row.sourceDomain ?? "upload"}
                            </td>
                            <td style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                              {new Date(row.ingestedAt).toLocaleString()}
                            </td>
                            <td>{formatScore(factuality)}</td>
                            <td>{formatScore(ai)}</td>
                            <td onClick={(e) => e.stopPropagation()}>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                                <Link className="btn" to={`/documents/${row.id}`}>
                                  View
                                </Link>
                                <button type="button" className="btn" onClick={() => setMoveDoc(row)}>
                                  Move
                                </button>
                                <button type="button" className="btn" onClick={() => void onDeleteRow(row)}>
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    : null}
                </tbody>
              </table>
              {api && docList && docList.items.length === 0 && !docLoading ? (
                <p style={{ color: "var(--text-muted)", padding: "0 1rem 1rem" }}>No documents in this collection.</p>
              ) : null}
              {!api && demoPageSlice.total === 0 ? (
                <p style={{ color: "var(--text-muted)", padding: "0 1rem 1rem" }}>No documents match filters.</p>
              ) : null}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.75rem 1rem" }}>
                <button
                  type="button"
                  className="btn"
                  disabled={
                    api ? offset <= 0 : offset <= 0
                  }
                  onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
                >
                  Previous
                </button>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  {api && docList
                    ? `Showing ${docList.offset + 1}–${docList.offset + docList.items.length} of ${docList.total}`
                    : `Showing ${offset + 1}–${Math.min(offset + PAGE_SIZE, demoPageSlice.total)} of ${demoPageSlice.total}`}
                </span>
                <button
                  type="button"
                  className="btn"
                  disabled={
                    api && docList
                      ? offset + docList.items.length >= docList.total
                      : offset + PAGE_SIZE >= demoPageSlice.total
                  }
                  onClick={() => setOffset((o) => o + PAGE_SIZE)}
                >
                  Next
                </button>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {tab === "analytics" ? (
        <section className="card" style={{ padding: "1rem" }}>
          <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Analytics summary</h2>
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            Full histograms and trends live on the dedicated page — this tab shows headline KPIs.
          </p>
          {api ? (
            <>
              {analyticsError ? <p className="error-text">{analyticsError}</p> : null}
              {analyticsCompact ? (
                <div className="kpi-grid" style={{ marginTop: "0.75rem" }}>
                  <div className="kpi-card">
                    <div className="label">Indexed (search)</div>
                    <div className="value">{analyticsCompact.index_total}</div>
                  </div>
                  <div className="kpi-card">
                    <div className="label">Avg factuality</div>
                    <div className="value">{formatScore(analyticsCompact.postgres.avg_factuality)}</div>
                  </div>
                  <div className="kpi-card">
                    <div className="label">Avg AI probability</div>
                    <div className="value">{formatScore(analyticsCompact.postgres.avg_ai_probability)}</div>
                  </div>
                  <div className="kpi-card">
                    <div className="label">Suspicious</div>
                    <div className="value">{analyticsCompact.postgres.suspicious_count}</div>
                  </div>
                </div>
              ) : (
                !analyticsError && <p className="page-sub">Loading…</p>
              )}
            </>
          ) : (
            (() => {
              const d = DEMO_ANALYTICS[collectionId];
              if (!d) return <p className="page-sub">No demo analytics for this collection.</p>;
              return (
                <div className="kpi-grid" style={{ marginTop: "0.75rem" }}>
                  <div className="kpi-card">
                    <div className="label">Avg factuality</div>
                    <div className="value">{d.kpis.avgFactuality.toFixed(2)}</div>
                  </div>
                  <div className="kpi-card">
                    <div className="label">Avg AI probability</div>
                    <div className="value">{d.kpis.avgAiProbability.toFixed(2)}</div>
                  </div>
                  <div className="kpi-card">
                    <div className="label">Suspicious docs</div>
                    <div className="value">{d.kpis.suspiciousCount}</div>
                  </div>
                </div>
              );
            })()
          )}
          <p style={{ marginTop: "1rem" }}>
            <Link className="btn btn-primary" to={`/collections/${collectionId}/analytics`}>
              Open full analytics
            </Link>
          </p>
        </section>
      ) : null}

      {tab === "models" ? (
        <CollectionModelsTab
          collectionId={collectionId}
          accessToken={accessToken}
          api={api}
          createOpen={createModelOpen}
          onCloseCreate={() => setCreateModelOpen(false)}
          onOpenCreate={() => setCreateModelOpen(true)}
        />
      ) : null}

      {tab === "activity" ? (
        <section className="card" style={{ padding: "1rem" }}>
          <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Pipeline activity</h2>
          {api ? (
            <>
              {activityError ? <p className="error-text">{activityError}</p> : null}
              {activityLoading ? <p className="page-sub">Loading…</p> : null}
              {!activityLoading && activityItems && activityItems.length === 0 ? (
                <p className="page-sub">No recent pipeline events for documents in this collection.</p>
              ) : null}
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {(activityItems ?? []).map((ev) => (
                  <li
                    key={ev.id}
                    style={{
                      borderBottom: "1px solid var(--border)",
                      padding: "0.65rem 0",
                      fontSize: "0.9rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                      <strong>{ev.document_title ?? ev.document_id}</strong>
                      <span style={{ color: "var(--text-muted)" }}>{new Date(ev.created_at).toLocaleString()}</span>
                    </div>
                    <div style={{ color: "var(--text-muted)", marginTop: 4 }}>
                      <span className={statusBadgeClass("processing")}>{ev.event_type}</span>
                      {ev.stage ? ` · ${ev.stage}` : null}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {demoActivity.map((ev) => (
                <li
                  key={ev.id}
                  style={{
                    borderBottom: "1px solid var(--border)",
                    padding: "0.65rem 0",
                    fontSize: "0.9rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <strong>{ev.document_title ?? ev.document_id}</strong>
                    <span style={{ color: "var(--text-muted)" }}>{new Date(ev.created_at).toLocaleString()}</span>
                  </div>
                  <div style={{ color: "var(--text-muted)", marginTop: 4 }}>
                    <span className={statusBadgeClass("processing")}>{ev.event_type}</span>
                    {ev.stage ? ` · ${ev.stage}` : null} <span>(demo)</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}

      {moveDoc ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="move-dialog-title"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 50,
            padding: 16,
          }}
        >
          <div className="card" style={{ maxWidth: 420, width: "100%", padding: "1rem" }}>
            <h2 id="move-dialog-title" style={{ marginTop: 0, fontSize: "1rem" }}>
              Move document
            </h2>
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>
              {moveDoc && "title" in moveDoc && moveDoc.title ? moveDoc.title : moveDoc?.id}
            </p>
            <label style={{ display: "block", marginTop: "0.75rem" }}>
              <span style={{ display: "block", fontSize: "0.85rem", marginBottom: 4 }}>Target collection</span>
              <select
                value={moveTargetId}
                onChange={(e) => setMoveTargetId(e.target.value)}
                style={{ width: "100%", padding: "0.45rem 0.5rem", borderRadius: 6, border: "1px solid var(--border)" }}
              >
                <option value="">Select…</option>
                {moveTargets.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: "1rem" }}>
              <button
                type="button"
                className="btn"
                disabled={moveBusy}
                onClick={() => {
                  setMoveDoc(null);
                  setMoveTargetId("");
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={moveBusy || !moveTargetId}
                onClick={() => void confirmMove()}
              >
                {moveBusy ? "…" : "Move"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

    </>
  );
}
