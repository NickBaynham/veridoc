import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearStoredDirSyncState,
  filesFromWebkitFileList,
  inferRootNameFromPaths,
  loadStoredDirSyncState,
} from "./localDirectorySync";

function stubLocalStorage() {
  let store: Record<string, string> = {};
  vi.stubGlobal(
    "localStorage",
    {
      getItem: (k: string) => (k in store ? store[k] : null),
      setItem: (k: string, v: string) => {
        store[k] = v;
      },
      removeItem: (k: string) => {
        delete store[k];
      },
      clear: () => {
        store = {};
      },
      key: () => null,
      get length() {
        return Object.keys(store).length;
      },
    } as Storage,
  );
}

describe("localDirectorySync", () => {
  beforeEach(() => {
    stubLocalStorage();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("inferRootNameFromPaths uses first path segment", () => {
    const f = new File(["x"], "leaf.txt");
    Object.defineProperty(f, "webkitRelativePath", {
      value: "my-root/src/a.ts",
      enumerable: true,
      configurable: true,
    });
    expect(inferRootNameFromPaths([f])).toBe("my-root");
  });

  it("filesFromWebkitFileList drops empty names", () => {
    const a = new File(["a"], "a.txt");
    const b = new File(["b"], "");
    expect(filesFromWebkitFileList([a, b]).map((x) => x.name)).toEqual(["a.txt"]);
  });

  it("loadStoredDirSyncState returns null when empty", () => {
    expect(loadStoredDirSyncState()).toBeNull();
  });

  it("clearStoredDirSyncState removes key", () => {
    localStorage.setItem("verifiedsignal:localDirSync:v1", JSON.stringify({ v: 1, entries: { a: {} } }));
    clearStoredDirSyncState();
    expect(localStorage.getItem("verifiedsignal:localDirSync:v1")).toBeNull();
  });
});
