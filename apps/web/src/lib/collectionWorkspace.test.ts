import { describe, expect, it } from "vitest";
import { parseWorkspaceTab } from "./collectionWorkspace";

describe("parseWorkspaceTab", () => {
  it("defaults to documents", () => {
    expect(parseWorkspaceTab(null)).toBe("documents");
    expect(parseWorkspaceTab("")).toBe("documents");
    expect(parseWorkspaceTab("nope")).toBe("documents");
  });

  it("accepts known tabs", () => {
    expect(parseWorkspaceTab("analytics")).toBe("analytics");
    expect(parseWorkspaceTab("models")).toBe("models");
    expect(parseWorkspaceTab("activity")).toBe("activity");
  });
});
