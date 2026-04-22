import { describe, expect, it } from "vitest";
import { buildIntakeUserMetadata } from "./intakeUserMetadata";

describe("buildIntakeUserMetadata", () => {
  it("returns undefined when empty or whitespace", () => {
    expect(buildIntakeUserMetadata("")).toBeUndefined();
    expect(buildIntakeUserMetadata("   ")).toBeUndefined();
  });

  it("returns trimmed description key", () => {
    expect(buildIntakeUserMetadata("  Alpha note  ")).toEqual({ description: "Alpha note" });
  });
});
