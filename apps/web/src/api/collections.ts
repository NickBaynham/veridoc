import { ApiError, apiFetch, readErrorMessage } from "./http";
import type {
  CollectionAnalyticsResponse,
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
