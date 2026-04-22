/** Optional description stored as `user_metadata.description` on document intake. */

export function buildIntakeUserMetadata(description: string): Record<string, string> | undefined {
  const t = description.trim();
  if (!t) return undefined;
  return { description: t };
}
