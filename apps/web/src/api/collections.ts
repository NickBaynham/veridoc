import { ApiError, apiFetch, readErrorMessage } from "./http";
import type {
  CollectionActivityResponse,
  CollectionAnalyticsResponse,
  CollectionDetail,
  CollectionDocumentsListResponse,
  CollectionListResponse,
  CollectionRow,
} from "./types";

export async function listCollections(accessToken: string): Promise<CollectionListResponse> {
  const res = await apiFetch("/api/v1/collections", { accessToken });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as CollectionListResponse;
}

export async function fetchCollectionDetail(
  accessToken: string,
  collectionId: string,
): Promise<CollectionDetail> {
  const res = await apiFetch(`/api/v1/collections/${encodeURIComponent(collectionId)}`, { accessToken });
  if (res.status === 404) {
    throw new ApiError("Collection not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as CollectionDetail;
}

export async function fetchCollectionDocuments(
  accessToken: string,
  collectionId: string,
  params: {
    limit?: number;
    offset?: number;
    q?: string;
    status?: string;
    source_kind?: string;
    sort?: string;
  } = {},
): Promise<CollectionDocumentsListResponse> {
  const sp = new URLSearchParams();
  if (params.limit != null) sp.set("limit", String(params.limit));
  if (params.offset != null) sp.set("offset", String(params.offset));
  if (params.q) sp.set("q", params.q);
  if (params.status) sp.set("status", params.status);
  if (params.source_kind) sp.set("source_kind", params.source_kind);
  if (params.sort) sp.set("sort", params.sort);
  const q = sp.toString();
  const path = q
    ? `/api/v1/collections/${encodeURIComponent(collectionId)}/documents?${q}`
    : `/api/v1/collections/${encodeURIComponent(collectionId)}/documents`;
  const res = await apiFetch(path, { accessToken });
  if (res.status === 404) {
    throw new ApiError("Collection not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as CollectionDocumentsListResponse;
}

export async function fetchCollectionActivity(
  accessToken: string,
  collectionId: string,
  params: { limit?: number } = {},
): Promise<CollectionActivityResponse> {
  const sp = new URLSearchParams();
  if (params.limit != null) sp.set("limit", String(params.limit));
  const q = sp.toString();
  const path = q
    ? `/api/v1/collections/${encodeURIComponent(collectionId)}/activity?${q}`
    : `/api/v1/collections/${encodeURIComponent(collectionId)}/activity`;
  const res = await apiFetch(path, { accessToken });
  if (res.status === 404) {
    throw new ApiError("Collection not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as CollectionActivityResponse;
}

export async function fetchCollectionAnalytics(
  accessToken: string,
  collectionId: string,
): Promise<CollectionAnalyticsResponse> {
  const res = await apiFetch(
    `/api/v1/collections/${encodeURIComponent(collectionId)}/analytics`,
    { accessToken },
  );
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as CollectionAnalyticsResponse;
}

export async function createCollection(
  accessToken: string,
  body: { name: string; organization_id?: string | null },
): Promise<CollectionRow> {
  const res = await apiFetch("/api/v1/collections", {
    method: "POST",
    accessToken,
    jsonBody: body,
  });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as CollectionRow;
}

export async function updateCollection(
  accessToken: string,
  collectionId: string,
  body: { name: string },
): Promise<CollectionRow> {
  const res = await apiFetch(`/api/v1/collections/${encodeURIComponent(collectionId)}`, {
    method: "PATCH",
    accessToken,
    jsonBody: body,
  });
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as CollectionRow;
}

export async function deleteCollection(accessToken: string, collectionId: string): Promise<void> {
  const res = await apiFetch(`/api/v1/collections/${encodeURIComponent(collectionId)}`, {
    method: "DELETE",
    accessToken,
  });
  if (!res.ok && res.status !== 204) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
}
