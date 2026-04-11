import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ingestDocumentFromUrl, uploadDocumentFile } from "../api/documents";
import { ApiError } from "../api/http";
import { fetchDocumentPipeline } from "../api/pipeline";
import { useAuth } from "../context/AuthContext";
import { isApiBackend } from "../config";
import { useApiEventSource } from "../hooks/useApiEventSource";
import type { PipelineStage } from "../demo/types";

const STAGES: PipelineStage[] = ["ingest", "extract", "enrich", "score", "index", "finalize"];

interface MockFile {
  id: string;
  name: string;
  sizeLabel: string;
  duplicate: boolean;
}

function simulateFiles(files: FileList | null): MockFile[] {
  if (!files?.length) return [];
  return Array.from(files).map((f, i) => ({
    id: `tmp-${i}-${f.name}`,
    name: f.name,
    sizeLabel: `${(f.size / 1024).toFixed(1)} KB`,
    duplicate: f.name.toLowerCase().includes("copy") || f.name.toLowerCase().includes("dup"),
  }));
}

export function UploadPage() {
  const { accessToken } = useAuth();
  const api = isApiBackend();
  const inputRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"files" | "url">("files");
  const [selected, setSelected] = useState<MockFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [processing, setProcessing] = useState(false);
  const [stageIndexById, setStageIndexById] = useState<Record<string, number>>({});
  const [urlInput, setUrlInput] = useState("");
  const [apiMessage, setApiMessage] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [trackDocId, setTrackDocId] = useState<string | null>(null);
  const [pipelineLog, setPipelineLog] = useState<string>("");

  useApiEventSource(
    api && !!accessToken,
    (msg) => {
      if (msg.type === "document_queued" && msg.payload.document_id) {
        const did = String(msg.payload.document_id);
        setPipelineLog((prev) => `SSE document_queued ${did}\n${prev}`.slice(0, 4000));
      }
    },
    accessToken,
  );

  useEffect(() => {
    if (!api || !accessToken || !trackDocId) return;
    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | undefined;
    const tick = async () => {
      try {
        const p = await fetchDocumentPipeline(accessToken, trackDocId);
        if (cancelled) return;
        const evs = p.events
          .slice(-12)
          .map((e) => e.event_type)
          .join(" → ");
        setPipelineLog(
          `Document ${p.document_status}${p.run ? ` · run ${p.run.status} (${p.run.stage})` : ""}\n${evs}`,
        );
        if (p.document_status === "completed" || p.document_status === "failed") {
          if (interval) window.clearInterval(interval);
          interval = undefined;
        }
      } catch (e) {
        if (!cancelled) {
          const hint =
            e instanceof ApiError
              ? `Pipeline poll failed (${e.status}): ${e.message}`
              : "Pipeline poll failed (network or unexpected error — is the API running?)";
          setPipelineLog(hint);
        }
      }
    };
    void tick();
    interval = window.setInterval(tick, 1500);
    return () => {
      cancelled = true;
      if (interval) window.clearInterval(interval);
    };
  }, [api, accessToken, trackDocId]);

  const onPick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const onFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files;
    if (api && list?.length) {
      setSelectedFiles(Array.from(list));
      setSelected([]);
    } else {
      setSelected(simulateFiles(list));
      setSelectedFiles([]);
    }
    e.target.value = "";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (api && e.dataTransfer.files?.length) {
      setSelectedFiles(Array.from(e.dataTransfer.files));
      setSelected([]);
    } else {
      setSelected(simulateFiles(e.dataTransfer.files));
      setSelectedFiles([]);
    }
  };

  const startPipeline = () => {
    if (!selected.length) return;
    setProcessing(true);
    const initial: Record<string, number> = {};
    selected.forEach((f) => {
      initial[f.id] = 0;
    });
    setStageIndexById(initial);

    const interval = window.setInterval(() => {
      setStageIndexById((prev) => {
        const next = { ...prev };
        let anyRunning = false;
        selected.forEach((f) => {
          const idx = next[f.id] ?? 0;
          if (idx < STAGES.length) {
            anyRunning = true;
            next[f.id] = idx + 1;
          }
        });
        if (!anyRunning) {
          window.clearInterval(interval);
          setProcessing(false);
        }
        return next;
      });
    }, 600);
  };

  const uploadToApi = async () => {
    if (!accessToken || selectedFiles.length === 0) return;
    setApiError(null);
    setApiMessage(null);
    setProcessing(true);
    try {
      const outs: string[] = [];
      let lastId: string | null = null;
      for (const file of selectedFiles) {
        const res = await uploadDocumentFile(accessToken, file);
        outs.push(`${file.name} → ${res.document_id} (${res.status})`);
        lastId = res.document_id;
      }
      setApiMessage(outs.join("\n"));
      if (lastId) setTrackDocId(lastId);
      setSelectedFiles([]);
    } catch (e) {
      setApiError(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setProcessing(false);
    }
  };

  const submitUrlToApi = async () => {
    if (!accessToken || !urlInput.trim()) return;
    setApiError(null);
    setApiMessage(null);
    setProcessing(true);
    try {
      const res = await ingestDocumentFromUrl(accessToken, { url: urlInput.trim() });
      setApiMessage(`Queued ${res.document_id} (${res.status}) for ${res.source_url}`);
      setTrackDocId(res.document_id);
      setUrlInput("");
    } catch (e) {
      setApiError(e instanceof ApiError ? e.message : "URL intake failed");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <>
      <h1 className="page-title">Upload</h1>
      <p className="page-sub">
        <strong>Use Case 2</strong> —{" "}
        {api ? (
            <>
              <code>POST /api/v1/documents</code> (multipart) and <code>POST /api/v1/documents/from-url</code>. After upload,
              the UI listens on <code>/api/v1/events/stream</code> and polls <code>/api/v1/documents/{"{id}"}/pipeline</code>.
            </>
        ) : (
          <>
            file drop zone, duplicate hint, and simulated pipeline stages (SSE would stream progress in production).
          </>
        )}
      </p>

      <div className="tabs">
        <button type="button" className={tab === "files" ? "active" : ""} onClick={() => setTab("files")}>
          File upload
        </button>
        <button type="button" className={tab === "url" ? "active" : ""} onClick={() => setTab("url")}>
          URL submission
        </button>
      </div>

      {tab === "files" ? (
        <div className="card">
          <div className="dropzone" onDragOver={(e) => e.preventDefault()} onDrop={onDrop} role="presentation">
            <p>
              <strong>Drag and drop</strong> {api ? "files for API intake" : "PDF, DOCX, TXT, HTML, MD (demo accepts any file)."}
            </p>
            <p style={{ margin: "0.75rem 0" }}>or</p>
            <button type="button" className="btn btn-primary" onClick={onPick}>
              Choose files
            </button>
            <input ref={inputRef} type="file" multiple hidden onChange={onFiles} />
          </div>

          {api ? (
            <>
              {selectedFiles.length ? (
                <>
                  <h3 style={{ marginTop: "1.25rem", fontSize: "0.95rem" }}>Selected</h3>
                  {selectedFiles.map((f) => (
                    <div key={f.name + f.size} className="file-row">
                      <div>
                        <div style={{ fontWeight: 600 }}>{f.name}</div>
                        <div className="meta">{(f.size / 1024).toFixed(1)} KB</div>
                      </div>
                    </div>
                  ))}
                  <div style={{ marginTop: "1rem", display: "flex", gap: 8 }}>
                    <button type="button" className="btn btn-primary" disabled={processing} onClick={() => void uploadToApi()}>
                      {processing ? "Uploading…" : "Upload to API"}
                    </button>
                    <button
                      type="button"
                      className="btn"
                      disabled={processing}
                      onClick={() => setSelectedFiles([])}
                    >
                      Clear
                    </button>
                  </div>
                </>
              ) : null}
              {apiError ? <p className="error-text" style={{ marginTop: "1rem" }}>{apiError}</p> : null}
              {apiMessage ? (
                <pre
                  style={{
                    marginTop: "1rem",
                    fontSize: "0.85rem",
                    whiteSpace: "pre-wrap",
                    color: "var(--text-muted)",
                  }}
                >
                  {apiMessage}
                </pre>
              ) : null}
              {pipelineLog ? (
                <>
                  <h3 style={{ marginTop: "1.25rem", fontSize: "0.95rem" }}>Live progress</h3>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 0 }}>
                    <code>SSE /api/v1/events/stream</code> (e.g. <code>document_queued</code>) and polling{" "}
                    <code>GET /api/v1/documents/{"{id}"}/pipeline</code> while the worker runs.
                  </p>
                  <pre
                    style={{
                      marginTop: "0.5rem",
                      fontSize: "0.8rem",
                      whiteSpace: "pre-wrap",
                      color: "var(--text-muted)",
                      maxHeight: 200,
                      overflow: "auto",
                    }}
                  >
                    {pipelineLog}
                  </pre>
                </>
              ) : null}
            </>
          ) : (
            <>
              {selected.length ? (
                <>
                  <h3 style={{ marginTop: "1.25rem", fontSize: "0.95rem" }}>Selected</h3>
                  {selected.map((f) => (
                    <div key={f.id} className="file-row">
                      <div>
                        <div style={{ fontWeight: 600 }}>{f.name}</div>
                        <div className="meta">{f.sizeLabel}</div>
                      </div>
                      {f.duplicate ? <span className="pill pill-warn">Possible duplicate</span> : <span className="pill">New</span>}
                    </div>
                  ))}
                  <div style={{ marginTop: "1rem", display: "flex", gap: 8 }}>
                    <button type="button" className="btn btn-primary" disabled={processing} onClick={startPipeline}>
                      {processing ? "Processing…" : "Start ingestion (mock)"}
                    </button>
                    <button
                      type="button"
                      className="btn"
                      disabled={processing}
                      onClick={() => {
                        setSelected([]);
                        setStageIndexById({});
                      }}
                    >
                      Clear
                    </button>
                  </div>
                </>
              ) : null}

              {selected.length && Object.keys(stageIndexById).length ? (
                <div style={{ marginTop: "1.5rem" }}>
                  <h3 style={{ fontSize: "0.95rem" }}>Pipeline progress</h3>
                  {selected.map((f) => {
                    const idx = stageIndexById[f.id] ?? 0;
                    return (
                      <div key={f.id} className="pipeline-row">
                        <div>
                          <div style={{ fontWeight: 600 }}>{f.name}</div>
                          <div className="pipeline-stages">
                            {STAGES.map((s, i) => (
                              <span
                                key={s}
                                className={`stage-pill ${i < idx ? "done" : ""} ${i === idx && idx < STAGES.length ? "current" : ""}`}
                              >
                                {s}
                              </span>
                            ))}
                          </div>
                        </div>
                        {idx >= STAGES.length ? <span className="pill pill-ok">Complete</span> : null}
                      </div>
                    );
                  })}
                  <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "1rem" }}>
                    Presigned S3 upload and <code>POST /documents</code> run in API mode; this mock simulates stages only.
                  </p>
                </div>
              ) : null}
            </>
          )}
        </div>
      ) : (
        <div className="card">
          {api ? (
            <>
              <div className="field">
                <label htmlFor="url">Document URL</label>
                <input
                  id="url"
                  type="url"
                  placeholder="https://example.com/report.pdf"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                />
              </div>
              <button type="button" className="btn btn-primary" disabled={processing} onClick={() => void submitUrlToApi()}>
                {processing ? "Submitting…" : "Queue URL (API)"}
              </button>
              {apiError ? <p className="error-text" style={{ marginTop: "1rem" }}>{apiError}</p> : null}
              {apiMessage ? (
                <p style={{ marginTop: "1rem", fontSize: "0.9rem", color: "var(--text-muted)" }}>{apiMessage}</p>
              ) : null}
              {pipelineLog ? (
                <pre
                  style={{
                    marginTop: "1rem",
                    fontSize: "0.8rem",
                    whiteSpace: "pre-wrap",
                    color: "var(--text-muted)",
                    maxHeight: 200,
                    overflow: "auto",
                  }}
                >
                  {pipelineLog}
                </pre>
              ) : null}
            </>
          ) : (
            <>
              <p style={{ color: "var(--text-muted)", marginTop: 0 }}>
                URL ingestion UI placeholder — paste a URL and enqueue (mock). Backend not wired.
              </p>
              <div className="field">
                <label htmlFor="url">Document URL</label>
                <input id="url" type="url" placeholder="https://example.com/report.pdf" />
              </div>
              <button type="button" className="btn btn-primary">
                Queue URL (mock)
              </button>
            </>
          )}
        </div>
      )}
      {api && apiMessage?.includes("→") ? (
        <p style={{ marginTop: "1rem", fontSize: "0.9rem" }}>
          <Link to="/dashboard">Dashboard</Link> lists recent documents after worker processing.
        </p>
      ) : null}
    </>
  );
}
