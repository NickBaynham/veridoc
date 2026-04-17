import { ApiError, apiFetch, readErrorMessage } from "./http";
import type {
  KnowledgeModelAssetListResponse,
  KnowledgeModelCreateBody,
  KnowledgeModelCreateResponse,
  KnowledgeModelDetail,
  KnowledgeModelListResponse,
  KnowledgeModelVersionDetail,
  KnowledgeModelVersionListResponse,
} from "./types";

export async function listCollectionKnowledgeModels(
  accessToken: string,
  collectionId: string,
): Promise<KnowledgeModelListResponse> {
  const res = await apiFetch(
    `/api/v1/collections/${encodeURIComponent(collectionId)}/models`,
    { accessToken },
  );
  if (res.status === 404) {
    throw new ApiError("Collection not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as KnowledgeModelListResponse;
}

export async function createCollectionKnowledgeModel(
  accessToken: string,
  collectionId: string,
  body: KnowledgeModelCreateBody,
): Promise<KnowledgeModelCreateResponse> {
  const res = await apiFetch(`/api/v1/collections/${encodeURIComponent(collectionId)}/models`, {
    method: "POST",
    accessToken,
    jsonBody: body,
  });
  if (res.status === 404) {
    throw new ApiError("Collection not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as KnowledgeModelCreateResponse;
}

export async function fetchKnowledgeModelDetail(
  accessToken: string,
  modelId: string,
): Promise<KnowledgeModelDetail> {
  const res = await apiFetch(`/api/v1/models/${encodeURIComponent(modelId)}`, { accessToken });
  if (res.status === 404) {
    throw new ApiError("Model not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as KnowledgeModelDetail;
}

export async function listKnowledgeModelVersions(
  accessToken: string,
  modelId: string,
): Promise<KnowledgeModelVersionListResponse> {
  const res = await apiFetch(`/api/v1/models/${encodeURIComponent(modelId)}/versions`, {
    accessToken,
  });
  if (res.status === 404) {
    throw new ApiError("Model not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as KnowledgeModelVersionListResponse;
}

export async function fetchKnowledgeModelVersionDetail(
  accessToken: string,
  modelId: string,
  versionId: string,
): Promise<KnowledgeModelVersionDetail> {
  const res = await apiFetch(
    `/api/v1/models/${encodeURIComponent(modelId)}/versions/${encodeURIComponent(versionId)}`,
    { accessToken },
  );
  if (res.status === 404) {
    throw new ApiError("Model or version not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as KnowledgeModelVersionDetail;
}

export async function listKnowledgeModelVersionAssets(
  accessToken: string,
  modelId: string,
  versionId: string,
): Promise<KnowledgeModelAssetListResponse> {
  const res = await apiFetch(
    `/api/v1/models/${encodeURIComponent(modelId)}/versions/${encodeURIComponent(versionId)}/assets`,
    { accessToken },
  );
  if (res.status === 404) {
    throw new ApiError("Model or version not found", 404);
  }
  if (!res.ok) {
    throw new ApiError(await readErrorMessage(res), res.status);
  }
  return (await res.json()) as KnowledgeModelAssetListResponse;
}
