import { getApiBaseUrl } from "../config";
import { ApiError, apiFetch, joinApiUrl, readErrorMessage } from "./http";
import type {
  DocumentDetail,
  DocumentListResponse,
  DocumentSummary,
  IntakeResponse,
  UrlIntakeResponse,
} from "./types";

export async function listDocuments(
  accessToken: string,
  params: { limit?: number; offset?: number } = {},
): Promise<DocumentListResponse> {
  const sp = new URLSearchParams();
  if (params.limit != null) sp.set("limit", String(params.limit));
  if (params.offset != null) sp.set("offset", String(params.offset));
  const q = sp.toString();
  const path = q ? `/api/v1/documents?${q}` : "/api/v1/documents";
  const res = await apiFetch(path, { accessToken });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as DocumentListResponse;
}

export async function getDocument(accessToken: string, documentId: string): Promise<DocumentDetail> {
  const res = await apiFetch(`/api/v1/documents/${encodeURIComponent(documentId)}`, { accessToken });
  if (res.status === 404) {
    throw new ApiError("Document not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as DocumentDetail;
}

export async function uploadDocumentFile(
  accessToken: string,
  file: File,
  options: { collectionId?: string; title?: string } = {},
): Promise<IntakeResponse> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  if (options.collectionId) fd.append("collection_id", options.collectionId);
  if (options.title) fd.append("title", options.title);
  const res = await apiFetch("/api/v1/documents", {
    method: "POST",
    accessToken,
    body: fd,
    isFormData: true,
  });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as IntakeResponse;
}

export async function ingestDocumentFromUrl(
  accessToken: string,
  payload: { url: string; collection_id?: string | null; title?: string | null },
): Promise<UrlIntakeResponse> {
  const res = await apiFetch("/api/v1/documents/from-url", {
    method: "POST",
    accessToken,
    jsonBody: payload,
  });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as UrlIntakeResponse;
}

export async function moveDocument(
  accessToken: string,
  documentId: string,
  collectionId: string,
): Promise<DocumentSummary> {
  const res = await apiFetch(`/api/v1/documents/${encodeURIComponent(documentId)}/move`, {
    method: "POST",
    accessToken,
    jsonBody: { collection_id: collectionId },
  });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as DocumentSummary;
}

export async function copyDocument(
  accessToken: string,
  documentId: string,
  collectionId: string,
): Promise<DocumentSummary> {
  const res = await apiFetch(`/api/v1/documents/${encodeURIComponent(documentId)}/copy`, {
    method: "POST",
    accessToken,
    jsonBody: { collection_id: collectionId },
  });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as DocumentSummary;
}

export async function deleteDocument(accessToken: string, documentId: string): Promise<void> {
  const res = await apiFetch(`/api/v1/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
    accessToken,
  });
  if (res.status === 404) {
    throw new ApiError("Document not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
}

/**
 * Streams the original file through the API (`redirect=false`) so the Bearer token is sent.
 * Triggers a browser download with the filename from Content-Disposition when present.
 */
export async function downloadOriginalFile(accessToken: string, documentId: string): Promise<void> {
  const root = getApiBaseUrl();
  if (!root) {
    throw new ApiError("VITE_API_URL is not set", 0);
  }
  const path = `/api/v1/documents/${encodeURIComponent(documentId)}/file?redirect=false`;
  const url = joinApiUrl(root, path);
  const res = await fetch(url, {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
    credentials: "include",
  });
  if (res.status === 404) {
    throw new ApiError("Original file not available", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition");
  let filename = "download";
  if (cd) {
    const m = /filename\*=UTF-8''([^;]+)|filename="([^"]+)"/i.exec(cd);
    const raw = m?.[1] || m?.[2];
    if (raw) {
      try {
        filename = decodeURIComponent(raw);
      } catch {
        filename = raw;
      }
    }
  }
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(href);
}
