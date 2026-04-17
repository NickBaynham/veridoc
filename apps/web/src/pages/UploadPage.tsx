import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listCollections } from "../api/collections";
import { ingestDocumentFromUrl, uploadDocumentFile } from "../api/documents";
import type { CollectionRow } from "../api/types";
import { ApiError } from "../api/http";
import { fetchDocumentPipeline } from "../api/pipeline";
import { useAuth } from "../context/AuthContext";
import { isApiBackend } from "../config";
import { useApiEventSource } from "../hooks/useApiEventSource";
import type { PipelineStage } from "../demo/types";
import { buildIntakeUserMetadata } from "../lib/intakeUserMetadata";
import {
  clearStoredDirSyncState,
  collectFilesRecursive,
  filesFromWebkitFileList,
  inferRootNameFromPaths,
  loadStoredDirSyncState,
  supportsDirectoryPicker,
  syncDirectoryWithApi,
} from "../lib/localDirectorySync";

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

function simulateFolderFiles(files: FileList | readonly File[] | null): MockFile[] {
  const arr = files == null ? [] : Array.isArray(files) ? [...files] : Array.from(files);
  if (!arr.length) return [];
  return arr.map((f, i) => {
    const rel = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
    return {
      id: `tmp-dir-${i}-${rel}`,
      name: rel,
      sizeLabel: `${(f.size / 1024).toFixed(1)} KB`,
      duplicate: rel.toLowerCase().includes("copy") || rel.toLowerCase().includes("dup"),
    };
  });
}

export function UploadPage() {
  const { accessToken } = useAuth();
  const api = isApiBackend();
  const [searchParams] = useSearchParams();
  const collectionFromUrl = searchParams.get("collection");
  const inputRef = useRef<HTMLInputElement>(null);
  const webkitDirInputRef = useRef<HTMLInputElement>(null);
  const dirHandleRef = useRef<FileSystemDirectoryHandle | null>(null);
  const dirSyncInFlight = useRef(false);
  const [dirConnected, setDirConnected] = useState(false);
  const [dirRootLabel, setDirRootLabel] = useState<string | null>(null);
  const [dirAutoSync, setDirAutoSync] = useState(false);
  const [dirLog, setDirLog] = useState("");
  const [dirSyncing, setDirSyncing] = useState(false);
  const [dirTrackedCount, setDirTrackedCount] = useState(0);
  const [tab, setTab] = useState<"files" | "url" | "directory">("files");
  const [selected, setSelected] = useState<MockFile[]>([]);
  const [selectedDirDemo, setSelectedDirDemo] = useState<MockFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [processing, setProcessing] = useState(false);
  const [stageIndexById, setStageIndexById] = useState<Record<string, number>>({});
  const [urlInput, setUrlInput] = useState("");
  const [apiMessage, setApiMessage] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [trackDocId, setTrackDocId] = useState<string | null>(null);
  const [pipelineLog, setPipelineLog] = useState<string>("");
  const [uploadCollections, setUploadCollections] = useState<CollectionRow[]>([]);
  const [uploadCollectionId, setUploadCollectionId] = useState("");
  const [uploadCollectionsLoaded, setUploadCollectionsLoaded] = useState(false);
  const [uploadMetaDescription, setUploadMetaDescription] = useState("");

  useEffect(() => {
    if (!api || !accessToken) {
      setUploadCollections([]);
      setUploadCollectionId("");
      setUploadCollectionsLoaded(false);
      return;
    }
    let cancelled = false;
    setUploadCollectionsLoaded(false);
    void listCollections(accessToken).then(
      (r) => {
        if (cancelled) return;
        const cols = r.collections;
        setUploadCollections(cols);
        setUploadCollectionId((prev) => {
          if (collectionFromUrl && cols.some((c) => c.id === collectionFromUrl)) return collectionFromUrl;
          if (prev && cols.some((c) => c.id === prev)) return prev;
          return cols[0]?.id ?? "";
        });
        setUploadCollectionsLoaded(true);
      },
      () => {
        if (!cancelled) {
          setUploadCollections([]);
          setUploadCollectionId("");
          setUploadCollectionsLoaded(true);
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [api, accessToken, collectionFromUrl]);

  useEffect(() => {
    if (tab !== "directory") return;
    const s = loadStoredDirSyncState();
    setDirTrackedCount(s ? Object.keys(s.entries).length : 0);
  }, [tab]);

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

  const appendDirLog = useCallback((line: string) => {
    setDirLog((prev) => `${line}\n${prev}`.slice(0, 8000));
  }, []);

  const runDirectorySyncFromHandle = useCallback(async () => {
    const handle = dirHandleRef.current;
    if (!api || !accessToken || !handle || dirSyncInFlight.current) return;
    dirSyncInFlight.current = true;
    setDirSyncing(true);
    setApiError(null);
    try {
      const collected = await collectFilesRecursive(handle);
      const rootName = handle.name;
      await syncDirectoryWithApi({
        accessToken,
        rootName,
        files: collected,
        onLog: appendDirLog,
        collectionId: uploadCollectionId || undefined,
        metadata: buildIntakeUserMetadata(uploadMetaDescription),
      });
      setDirTrackedCount(Object.keys(loadStoredDirSyncState()?.entries ?? {}).length);
    } catch (e) {
      setApiError(e instanceof ApiError ? e.message : "Folder sync failed");
    } finally {
      dirSyncInFlight.current = false;
      setDirSyncing(false);
    }
  }, [api, accessToken, appendDirLog, uploadCollectionId, uploadMetaDescription]);

  const runDirectorySyncFromFileList = useCallback(
    async (picked: FileList | readonly File[]) => {
      if (!api || !accessToken || dirSyncInFlight.current) return;
      const files = filesFromWebkitFileList(Array.isArray(picked) ? picked : Array.from(picked));
      if (!files.length) return;
      dirSyncInFlight.current = true;
      setDirSyncing(true);
      setApiError(null);
      try {
        const rootName = inferRootNameFromPaths(files);
        await syncDirectoryWithApi({
          accessToken,
          rootName,
          files,
          onLog: appendDirLog,
          collectionId: uploadCollectionId || undefined,
          metadata: buildIntakeUserMetadata(uploadMetaDescription),
        });
        setDirRootLabel(rootName);
        setDirTrackedCount(Object.keys(loadStoredDirSyncState()?.entries ?? {}).length);
      } catch (e) {
        setApiError(e instanceof ApiError ? e.message : "Folder sync failed");
      } finally {
        dirSyncInFlight.current = false;
        setDirSyncing(false);
      }
    },
    [api, accessToken, appendDirLog, uploadCollectionId, uploadMetaDescription],
  );

  useEffect(() => {
    if (!api || !accessToken || !dirAutoSync || !dirConnected || !supportsDirectoryPicker()) return;
    const id = window.setInterval(() => {
      void runDirectorySyncFromHandle();
    }, 60_000);
    return () => window.clearInterval(id);
  }, [api, accessToken, dirAutoSync, dirConnected, runDirectorySyncFromHandle]);

  const connectDirectoryPicker = useCallback(async () => {
    if (!window.showDirectoryPicker) return;
    setApiError(null);
    try {
      const handle = await window.showDirectoryPicker({ mode: "read" });
      dirHandleRef.current = handle;
      setDirRootLabel(handle.name);
      setDirConnected(true);
      appendDirLog(`Granted access: ${handle.name}`);
      await runDirectorySyncFromHandle();
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setApiError(e instanceof ApiError ? e.message : "Could not open folder");
    }
  }, [appendDirLog, runDirectorySyncFromHandle]);

  const disconnectDirectory = useCallback(() => {
    dirHandleRef.current = null;
    setDirConnected(false);
    setDirRootLabel(null);
    setDirAutoSync(false);
    appendDirLog("Disconnected folder (index in this browser is unchanged — use “Forget index” to clear).");
  }, [appendDirLog]);

  const forgetDirectoryIndex = useCallback(() => {
    clearStoredDirSyncState();
    setDirTrackedCount(0);
    appendDirLog("Cleared stored path → document map for this browser.");
  }, [appendDirLog]);

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
      const metadata = buildIntakeUserMetadata(uploadMetaDescription);
      for (const file of selectedFiles) {
        const res = await uploadDocumentFile(accessToken, file, {
          collectionId: uploadCollectionId || undefined,
          ...(metadata ? { metadata } : {}),
        });
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
      const metadata = buildIntakeUserMetadata(uploadMetaDescription);
      const res = await ingestDocumentFromUrl(accessToken, {
        url: urlInput.trim(),
        collection_id: uploadCollectionId || undefined,
        ...(metadata ? { metadata } : {}),
      });
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

      {api && accessToken ? (
        <div className="card" style={{ marginBottom: "1rem" }}>
          <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Target collection</h2>
          {!uploadCollectionsLoaded ? (
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0 }}>Loading collections…</p>
          ) : uploadCollections.length === 0 ? (
            <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", margin: 0 }}>
              No collections returned for your account. Uploads omit <code>collection_id</code> and use the API
              default (if configured).
            </p>
          ) : (
            <>
              <label htmlFor="upload-target-collection" style={{ display: "block", marginBottom: 6, fontSize: "0.9rem" }}>
                Upload into
              </label>
              <select
                id="upload-target-collection"
                value={uploadCollectionId}
                onChange={(e) => setUploadCollectionId(e.target.value)}
                disabled={processing || dirSyncing}
                style={{
                  width: "100%",
                  maxWidth: 420,
                  padding: "0.45rem 0.5rem",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                }}
              >
                {uploadCollections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.5rem", marginBottom: 0 }}>
                Applies to <strong>file upload</strong>, <strong>URL intake</strong>, and <strong>local folder</strong> sync
                in this session.
              </p>
            </>
          )}
          <hr style={{ border: 0, borderTop: "1px solid var(--border)", margin: "1.25rem 0" }} />
          <h2 style={{ marginTop: 0, fontSize: "1rem" }}>Description (optional)</h2>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 0 }}>
            When set, stored on the document as <code>user_metadata.description</code> (included in search metadata text
            on the API).
          </p>
          <div className="field" style={{ marginTop: "0.65rem" }}>
            <label htmlFor="upload-meta-description">Description</label>
            <textarea
              id="upload-meta-description"
              rows={3}
              value={uploadMetaDescription}
              onChange={(e) => setUploadMetaDescription(e.target.value)}
              disabled={processing || dirSyncing}
              placeholder="Summary, context, or notes…"
              style={{ width: "100%", maxWidth: 560, resize: "vertical" }}
            />
          </div>
        </div>
      ) : null}

      <div className="tabs">
        <button type="button" className={tab === "files" ? "active" : ""} onClick={() => setTab("files")}>
          File upload
        </button>
        <button type="button" className={tab === "url" ? "active" : ""} onClick={() => setTab("url")}>
          URL submission
        </button>
        <button type="button" className={tab === "directory" ? "active" : ""} onClick={() => setTab("directory")}>
          Local folder
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
      ) : tab === "url" ? (
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
      ) : (
        <div className="card">
          <p style={{ marginTop: 0 }}>
            Ingest an entire <strong>folder tree</strong> from your machine. The browser cannot read arbitrary disk
            paths; you choose a directory, then we upload each file and (in API mode) keep VerifiedSignal aligned with
            that folder using <strong>relative paths</strong> stored in this browser.
          </p>
          <input
            ref={webkitDirInputRef}
            type="file"
            data-testid="local-folder-file-input"
            style={{ display: "none" }}
            {...{ webkitdirectory: "" }}
            multiple
            onChange={(e) => {
              const list = e.target.files;
              const picked = list?.length ? Array.from(list) : [];
              e.target.value = "";
              if (!picked.length) return;
              if (api && accessToken) {
                void runDirectorySyncFromFileList(picked);
              } else {
                setSelectedDirDemo(simulateFolderFiles(picked));
              }
            }}
          />
          {api ? (
            <>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                <strong>Sync</strong> means: new files are uploaded; changed files (size / last modified) are replaced
                (old document deleted, new upload); files removed from the folder get their documents deleted. Titles
                use the relative path so you can spot them on the dashboard.
              </p>
              {supportsDirectoryPicker() ? (
                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  Chromium / Edge: grant folder access once, then use <strong>Sync now</strong> or enable{" "}
                  <strong>Auto-sync every 60s</strong> without re-picking the folder.
                </p>
              ) : (
                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  This browser does not expose <code>showDirectoryPicker</code>. Use <strong>Choose folder…</strong>{" "}
                  below; run sync again after you change files (each pick re-reads the tree).
                </p>
              )}
              <div style={{ marginTop: "1rem", display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                {supportsDirectoryPicker() ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={dirSyncing || processing}
                    onClick={() => void connectDirectoryPicker()}
                  >
                    {dirConnected ? "Reconnect folder (Chromium)" : "Grant folder access (Chromium)"}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="btn"
                  disabled={dirSyncing || processing}
                  onClick={() => webkitDirInputRef.current?.click()}
                >
                  Choose folder…
                </button>
                <button
                  type="button"
                  className="btn"
                  disabled={!dirConnected || dirSyncing || processing || !supportsDirectoryPicker()}
                  onClick={() => void runDirectorySyncFromHandle()}
                >
                  {dirSyncing ? "Syncing…" : "Sync now"}
                </button>
                <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.9rem" }}>
                  <input
                    type="checkbox"
                    checked={dirAutoSync}
                    disabled={!dirConnected || !supportsDirectoryPicker()}
                    onChange={(e) => setDirAutoSync(e.target.checked)}
                  />
                  Auto-sync every 60s
                </label>
              </div>
              {dirConnected && dirRootLabel ? (
                <p style={{ marginTop: "0.75rem", fontSize: "0.9rem" }}>
                  Connected: <code>{dirRootLabel}</code> · tracked paths: {dirTrackedCount}
                </p>
              ) : (
                <p style={{ marginTop: "0.75rem", fontSize: "0.9rem", color: "var(--text-muted)" }}>
                  Tracked paths (this browser): {dirTrackedCount}
                </p>
              )}
              <div style={{ marginTop: "0.75rem", display: "flex", flexWrap: "wrap", gap: 8 }}>
                <button type="button" className="btn" disabled={!dirConnected} onClick={disconnectDirectory}>
                  Disconnect folder
                </button>
                <button type="button" className="btn" onClick={forgetDirectoryIndex}>
                  Forget index
                </button>
              </div>
              {apiError ? <p className="error-text" style={{ marginTop: "1rem" }}>{apiError}</p> : null}
              {dirLog ? (
                <>
                  <h3 style={{ marginTop: "1.25rem", fontSize: "0.95rem" }}>Sync log</h3>
                  <pre
                    style={{
                      marginTop: "0.5rem",
                      fontSize: "0.8rem",
                      whiteSpace: "pre-wrap",
                      color: "var(--text-muted)",
                      maxHeight: 240,
                      overflow: "auto",
                    }}
                  >
                    {dirLog}
                  </pre>
                </>
              ) : null}
              {pipelineLog ? (
                <pre
                  style={{
                    marginTop: "1rem",
                    fontSize: "0.8rem",
                    whiteSpace: "pre-wrap",
                    color: "var(--text-muted)",
                    maxHeight: 160,
                    overflow: "auto",
                  }}
                >
                  {pipelineLog}
                </pre>
              ) : null}
            </>
          ) : (
            <>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                Demo mode: pick a folder to list relative paths, then run the mock pipeline (no API).
              </p>
              <button type="button" className="btn btn-primary" onClick={() => webkitDirInputRef.current?.click()}>
                Choose folder…
              </button>
              {selectedDirDemo.length ? (
                <>
                  <h3 style={{ marginTop: "1.25rem", fontSize: "0.95rem" }}>Selected</h3>
                  {selectedDirDemo.map((f) => (
                    <div key={f.id} className="file-row">
                      <div>
                        <div style={{ fontWeight: 600 }}>{f.name}</div>
                        <div className="meta">{f.sizeLabel}</div>
                      </div>
                      {f.duplicate ? <span className="pill pill-warn">Possible duplicate</span> : <span className="pill">New</span>}
                    </div>
                  ))}
                  <div style={{ marginTop: "1rem", display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={processing}
                      onClick={() => {
                        if (!selectedDirDemo.length) return;
                        setProcessing(true);
                        const initial: Record<string, number> = {};
                        selectedDirDemo.forEach((f) => {
                          initial[f.id] = 0;
                        });
                        setStageIndexById(initial);
                        const interval = window.setInterval(() => {
                          setStageIndexById((prev) => {
                            const next = { ...prev };
                            let anyRunning = false;
                            selectedDirDemo.forEach((f) => {
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
                      }}
                    >
                      {processing ? "Processing…" : "Start ingestion (mock)"}
                    </button>
                    <button
                      type="button"
                      className="btn"
                      disabled={processing}
                      onClick={() => {
                        setSelectedDirDemo([]);
                        setStageIndexById({});
                      }}
                    >
                      Clear
                    </button>
                  </div>
                </>
              ) : null}
              {selectedDirDemo.length > 0 && Object.keys(stageIndexById).length > 0 ? (
                <div style={{ marginTop: "1.5rem" }}>
                  <h3 style={{ fontSize: "0.95rem" }}>Pipeline progress</h3>
                  {selectedDirDemo.map((f) => {
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
                </div>
              ) : null}
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
