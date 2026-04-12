import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { listCollections } from "../api/collections";
import { copyDocument, deleteDocument, downloadOriginalFile, getDocument, moveDocument } from "../api/documents";
import type { CollectionRow, DocumentDetail } from "../api/types";
import { ApiError } from "../api/http";
import { useAuth } from "../context/AuthContext";
import { useDemoData } from "../context/DemoDataContext";
import { isApiBackend } from "../config";
import { resolveDemoDocument } from "../demo";
import { ScoreBar } from "../components/ScoreBar";

function highlightTermInText(text: string, term: string): ReactNode {
  const t = term.trim();
  if (!t) return text;
  const lower = text.toLowerCase();
  const tl = t.toLowerCase();
  const parts: ReactNode[] = [];
  let start = 0;
  let idx = lower.indexOf(tl, start);
  let key = 0;
  while (idx !== -1) {
    if (idx > start) parts.push(text.slice(start, idx));
    parts.push(
      <mark
        key={`m-${key++}`}
        style={{ background: "var(--highlight-search)", color: "inherit", padding: "0 1px", borderRadius: 2 }}
      >
        {text.slice(idx, idx + t.length)}
      </mark>,
    );
    start = idx + t.length;
    idx = lower.indexOf(tl, start);
  }
  if (start < text.length) parts.push(text.slice(start));
  return parts.length ? parts : text;
}

export function DocumentReaderPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { deletedDocumentIds, deleteDemoDocument } = useDemoData();
  const api = isApiBackend();

  const [apiDoc, setApiDoc] = useState<DocumentDetail | null>(null);
  const [apiErr, setApiErr] = useState<string | null>(null);
  const [apiLoading, setApiLoading] = useState(false);
  const [apiDeleteBusy, setApiDeleteBusy] = useState(false);
  const [apiDownloadBusy, setApiDownloadBusy] = useState(false);
  const [collections, setCollections] = useState<CollectionRow[]>([]);
  const [targetCollectionId, setTargetCollectionId] = useState("");
  const [transferBusy, setTransferBusy] = useState(false);
  const [transferNote, setTransferNote] = useState<string | null>(null);

  const [panelTab, setPanelTab] = useState<"scores" | "keywords">("scores");
  const [focusMode, setFocusMode] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);

  const doc = id ? resolveDemoDocument(id, deletedDocumentIds) : undefined;

  useEffect(() => {
    setTransferNote(null);
  }, [id]);

  useEffect(() => {
    if (!api || !accessToken) {
      setCollections([]);
      return;
    }
    let cancelled = false;
    void listCollections(accessToken).then(
      (r) => {
        if (!cancelled) setCollections(r.collections);
      },
      () => {
        if (!cancelled) setCollections([]);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [api, accessToken]);

  useEffect(() => {
    if (!apiDoc || collections.length === 0) return;
    const preferred = collections.find((c) => c.id !== apiDoc.collection_id);
    setTargetCollectionId((prev) => {
      if (prev && collections.some((c) => c.id === prev)) return prev;
      return preferred?.id ?? collections[0]?.id ?? "";
    });
  }, [apiDoc?.collection_id, collections]);

  useEffect(() => {
    if (!api || !accessToken || !id) {
      setApiDoc(null);
      setApiErr(null);
      setApiLoading(false);
      return;
    }
    let cancelled = false;
    setApiLoading(true);
    setApiErr(null);
    setApiDoc(null);
    void (async () => {
      try {
        const d = await getDocument(accessToken, id);
        if (!cancelled) setApiDoc(d);
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && e.status === 404) setApiErr("notfound");
          else setApiErr(e instanceof ApiError ? e.message : "Failed to load document");
        }
      } finally {
        if (!cancelled) setApiLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, accessToken, id]);

  async function handleDeleteApiDocument() {
    if (!api || !accessToken || !id || !apiDoc) return;
    if (!window.confirm(`Remove “${apiDoc.title || apiDoc.original_filename || id}” from your library?`)) return;
    setApiDeleteBusy(true);
    try {
      await deleteDocument(accessToken, id);
      navigate("/dashboard");
    } catch (e) {
      window.alert(e instanceof ApiError ? e.message : "Delete failed");
    } finally {
      setApiDeleteBusy(false);
    }
  }

  function handleDeleteDemoDocument() {
    if (!id || !doc) return;
    if (!window.confirm(`Remove “${doc.title}” from the demo library?`)) return;
    deleteDemoDocument(id);
    navigate("/dashboard");
  }

  async function handleDownloadOriginal() {
    if (!api || !accessToken || !id) return;
    setApiDownloadBusy(true);
    try {
      await downloadOriginalFile(accessToken, id);
    } catch (e) {
      window.alert(e instanceof ApiError ? e.message : "Download failed");
    } finally {
      setApiDownloadBusy(false);
    }
  }

  async function handleMoveToCollection() {
    if (!api || !accessToken || !id || !apiDoc || !targetCollectionId) return;
    if (targetCollectionId === apiDoc.collection_id) return;
    setTransferBusy(true);
    setTransferNote(null);
    try {
      await moveDocument(accessToken, id, targetCollectionId);
      const d = await getDocument(accessToken, id);
      setApiDoc(d);
      setTransferNote("Document moved.");
    } catch (e) {
      window.alert(e instanceof ApiError ? e.message : "Move failed");
    } finally {
      setTransferBusy(false);
    }
  }

  async function handleCopyToCollection() {
    if (!api || !accessToken || !id || !apiDoc || !targetCollectionId) return;
    setTransferBusy(true);
    setTransferNote(null);
    try {
      const row = await copyDocument(accessToken, id, targetCollectionId);
      setTransferNote(
        `Copy created in the selected collection. Open it from the library (document id ${row.id}).`,
      );
    } catch (e) {
      window.alert(e instanceof ApiError ? e.message : "Copy failed");
    } finally {
      setTransferBusy(false);
    }
  }

  if (api) {
    if (!id) {
      return (
        <>
          <h1 className="page-title">Document not found</h1>
          <p className="page-sub">
            <Link to="/dashboard">Back to dashboard</Link>
          </p>
        </>
      );
    }
    if (apiLoading) {
      return <p className="page-sub">Loading document…</p>;
    }
    if (apiErr === "notfound") {
      return (
        <>
          <h1 className="page-title">Document not found</h1>
          <p className="page-sub">
            Unknown id or no access. <Link to="/dashboard">Back to dashboard</Link>
          </p>
        </>
      );
    }
    if (apiErr) {
      return (
        <>
          <h1 className="page-title">Error</h1>
          <p className="error-text">{apiErr}</p>
          <p className="page-sub">
            <Link to="/dashboard">Back to dashboard</Link>
          </p>
        </>
      );
    }
    if (!apiDoc) return null;

    const canon = apiDoc.canonical_score;
    const showScores =
      canon &&
      (canon.factuality_score != null ||
        canon.ai_generation_probability != null ||
        canon.fallacy_score != null ||
        canon.confidence_score != null);

    return (
      <>
        <div style={{ marginBottom: "1rem", display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
          <Link to="/dashboard" style={{ fontSize: "0.9rem" }}>
            ← Library
          </Link>
          {apiDoc.storage_key ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={apiDownloadBusy}
              onClick={() => void handleDownloadOriginal()}
            >
              {apiDownloadBusy ? "Downloading…" : "Download original"}
            </button>
          ) : null}
          <button
            type="button"
            className="btn"
            style={{ color: "var(--danger)", borderColor: "rgba(248,113,113,0.45)" }}
            disabled={apiDeleteBusy}
            onClick={() => void handleDeleteApiDocument()}
          >
            {apiDeleteBusy ? "Removing…" : "Delete document"}
          </button>
        </div>
        {collections.length > 0 ? (
          <div className="card" style={{ marginBottom: "1rem", maxWidth: 520 }}>
            <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Move or copy</h2>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: 0 }}>
              Current collection:{" "}
              <strong>
                {collections.find((c) => c.id === apiDoc.collection_id)?.name ?? apiDoc.collection_id}
              </strong>
            </p>
            <label htmlFor="vs-target-collection" style={{ display: "block", marginBottom: 6, fontSize: "0.9rem" }}>
              Target collection
            </label>
            <select
              id="vs-target-collection"
              style={{
                width: "100%",
                marginBottom: "0.65rem",
                padding: "0.45rem 0.5rem",
                borderRadius: 6,
                border: "1px solid var(--border)",
              }}
              value={targetCollectionId}
              disabled={transferBusy}
              onChange={(e) => setTargetCollectionId(e.target.value)}
            >
              {collections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn btn-primary"
                disabled={transferBusy || targetCollectionId === apiDoc.collection_id}
                onClick={() => void handleMoveToCollection()}
              >
                {transferBusy ? "…" : "Move here"}
              </button>
              <button type="button" className="btn" disabled={transferBusy} onClick={() => void handleCopyToCollection()}>
                {transferBusy ? "…" : "Copy here"}
              </button>
            </div>
            {transferNote ? (
              <p style={{ fontSize: "0.85rem", marginBottom: 0, marginTop: "0.65rem" }}>{transferNote}</p>
            ) : null}
          </div>
        ) : null}
        <h1 className="page-title">{apiDoc.title || apiDoc.original_filename || apiDoc.id}</h1>
        <p className="page-sub">
          <strong>API document</strong> — Status <code>{apiDoc.status}</code>
          {apiDoc.content_type ? (
            <>
              {" "}
              · <code>{apiDoc.content_type}</code>
            </>
          ) : null}
          . Canonical scores come from <code>document_scores</code> (in-process heuristic and/or HTTP scorer; see{" "}
          <code>docs/scoring-http.md</code>). Segment-level highlights remain demo-only.
        </p>
        {showScores ? (
          <div className="card" style={{ marginBottom: "1rem" }}>
            <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Scores</h2>
            <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 0 }}>
              {canon.scorer_name} {canon.scorer_version}
            </p>
            {canon.factuality_score != null ? (
              <div style={{ marginBottom: "0.75rem" }}>
                <ScoreBar value={canon.factuality_score} label="Factuality" />
              </div>
            ) : null}
            {canon.ai_generation_probability != null ? (
              <div style={{ marginBottom: "0.75rem" }}>
                <ScoreBar value={canon.ai_generation_probability} label="AI generation probability" />
              </div>
            ) : null}
            {canon.fallacy_score != null ? (
              <div style={{ marginBottom: "0.75rem" }}>
                <ScoreBar value={canon.fallacy_score} label="Fallacy / rhetoric risk" />
              </div>
            ) : null}
            {canon.confidence_score != null ? (
              <ScoreBar value={canon.confidence_score} label="Confidence" />
            ) : null}
          </div>
        ) : null}
        <div className="card">
          <pre
            style={{
              margin: 0,
              whiteSpace: "pre-wrap",
              fontFamily: "var(--font-sans, system-ui, sans-serif)",
              fontSize: "0.95rem",
              lineHeight: 1.5,
            }}
          >
            {apiDoc.body_text || "(No extracted text yet — pipeline may still be running.)"}
          </pre>
        </div>
        {apiDoc.sources.length ? (
          <div className="card" style={{ marginTop: "1rem" }}>
            <h2 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>Sources</h2>
            <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
              {apiDoc.sources.map((s) => (
                <li key={s.id} style={{ fontSize: "0.9rem" }}>
                  <code>{s.source_kind}</code> — {s.locator}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </>
    );
  }

  const aiScore = doc?.scores.find((s) => s.id === "ai");
  const factScore = doc?.scores.find((s) => s.id === "factuality");
  const showDangerBar = (aiScore && aiScore.value > 0.75) || (factScore && factScore.value <= 0.4);

  if (!doc) {
    return (
      <>
        <h1 className="page-title">Document not found</h1>
        <p className="page-sub">
          Unknown id in demo data. <Link to="/dashboard">Back to dashboard</Link>
        </p>
      </>
    );
  }

  return (
    <>
      <div style={{ marginBottom: "1rem", display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
        <Link to="/dashboard" style={{ fontSize: "0.9rem" }}>
          ← Library
        </Link>
        <button
          type="button"
          className="btn"
          style={{ color: "var(--danger)", borderColor: "rgba(248,113,113,0.45)" }}
          onClick={handleDeleteDemoDocument}
        >
          Delete document (demo)
        </button>
      </div>
      <h1 className="page-title">{doc.title}</h1>
      <p className="page-sub">
        <strong>Use Case 3</strong> — reader with score panel, inline fallacy highlights, and keyword tab (mock).
      </p>

      {showDangerBar ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            flexWrap: "wrap",
            padding: "0.65rem 1rem",
            borderRadius: "var(--radius-sm)",
            background: "var(--danger-bg)",
            border: "1px solid rgba(248,113,113,0.35)",
            marginBottom: "1rem",
          }}
        >
          <strong style={{ color: "var(--danger)" }}>Alert</strong>
          <span style={{ fontSize: "0.9rem" }}>
            Thresholds exceeded (spec): high AI probability and/or low factuality. Review highlighted passages.
          </span>
          {aiScore ? <span className="pill pill-danger">AI {Math.round(aiScore.value * 100)}%</span> : null}
          {factScore ? <span className="pill pill-warn">Factuality {Math.round(factScore.value * 100)}%</span> : null}
        </div>
      ) : null}

      <div style={{ marginBottom: "1rem", display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className={focusMode ? "btn btn-primary" : "btn"} onClick={() => setFocusMode((f) => !f)}>
          {focusMode ? "Exit focus mode" : "Focus mode"}
        </button>
      </div>

      <div className="reader-grid">
        <div className="card">
          <div className={`reader-doc ${focusMode ? "focus-mode" : ""}`}>
            {doc.bodySegments.map((seg, i) => {
              const content =
                selectedKeyword && !seg.highlight ? highlightTermInText(seg.text, selectedKeyword) : seg.text;
              return seg.highlight ? (
                <span key={i} className="hl" title={`${seg.highlight.fallacyType}: ${seg.highlight.explanation}`}>
                  {seg.text}
                </span>
              ) : (
                <span key={i}>{content}</span>
              );
            })}
          </div>
          {doc.author || doc.sourceDomain ? (
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "1rem" }}>
              Provenance (mock): {doc.author ? <>{doc.author} · </> : null}
              {doc.sourceDomain}
            </p>
          ) : null}
        </div>

        <div className="card" style={{ position: focusMode ? "sticky" : undefined, top: 12 }}>
          <div className="tabs">
            <button type="button" className={panelTab === "scores" ? "active" : ""} onClick={() => setPanelTab("scores")}>
              Scores
            </button>
            <button
              type="button"
              className={panelTab === "keywords" ? "active" : ""}
              onClick={() => setPanelTab("keywords")}
            >
              Keywords
            </button>
          </div>

          {panelTab === "scores" ? (
            <div>
              {doc.scores.length === 0 ? (
                <p style={{ color: "var(--text-muted)" }}>Scores appear when processing completes.</p>
              ) : (
                doc.scores.map((s) => (
                  <div key={s.id} style={{ marginBottom: "1rem" }}>
                    <ScoreBar value={s.value} label={s.label} />
                    {s.detail ? (
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 4 }}>{s.detail}</div>
                    ) : null}
                    <button
                      type="button"
                      className="btn btn-ghost"
                      style={{ marginTop: 6, padding: "0.2rem 0", fontSize: "0.8rem" }}
                      onClick={() => setExpanded((e) => ({ ...e, [s.id]: !e[s.id] }))}
                    >
                      {expanded[s.id] ? "Hide rationale" : "Show rationale"}
                    </button>
                    {expanded[s.id] ? (
                      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", margin: "0.35rem 0 0" }}>{s.rationale}</p>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          ) : (
            <div>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: 0 }}>
                TF-IDF terms (mock). In production, clicking would highlight occurrences in the document body.
              </p>
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {doc.keywords.map((k) => (
                  <li key={k.term} style={{ marginBottom: 8 }}>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      style={{ padding: "0.25rem 0", fontWeight: 600 }}
                      onClick={() => setSelectedKeyword((cur) => (cur === k.term ? null : k.term))}
                    >
                      {k.term}
                    </button>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginLeft: 8 }}>
                      {(k.weight * 100).toFixed(0)}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
