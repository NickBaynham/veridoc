import type { ModelWritebackVerification } from "../api/types";

export function normalizeStatus(raw: string | null | undefined): string {
  const s = String(raw || "").trim().toLowerCase();
  if (!s) return "unknown";
  if (s === "complete") return "completed";
  return s;
}

export function statusBadgeClass(raw: string | null | undefined): string {
  const s = normalizeStatus(raw);
  if (["completed", "active", "ok", "success", "accepted"].includes(s)) {
    return "vs-badge vs-badge--ok";
  }
  if (["failed", "error", "rejected", "superseded"].includes(s)) {
    return "vs-badge vs-badge--bad";
  }
  return "vs-badge vs-badge--pending";
}

export function writebackVerificationBadgeClass(
  verification: ModelWritebackVerification | string,
): string {
  return statusBadgeClass(verification);
}
