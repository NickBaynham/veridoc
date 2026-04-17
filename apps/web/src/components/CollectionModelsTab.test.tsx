import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CollectionModelsTab } from "./CollectionModelsTab";

vi.mock("../config", () => ({
  isApiBackend: () => true,
}));

const listMock = vi.fn();

vi.mock("../api/knowledgeModels", () => ({
  listCollectionKnowledgeModels: (...args: unknown[]) => listMock(...args),
}));

describe("CollectionModelsTab", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows empty state when API returns no models", async () => {
    listMock.mockResolvedValue({ items: [], collection_id: "c1" });

    render(
      <MemoryRouter>
        <CollectionModelsTab
          collectionId="c1"
          accessToken="tok"
          api
          createOpen={false}
          onCloseCreate={vi.fn()}
          onOpenCreate={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Models" })).toBeVisible();
    await waitFor(() => {
      expect(listMock).toHaveBeenCalledWith("tok", "c1");
    });
    expect(
      await screen.findByText(/No models yet/i),
    ).toBeVisible();
  });

  it("shows demo-only copy when API mode is off", () => {
    listMock.mockResolvedValue({ items: [], collection_id: "c1" });

    render(
      <MemoryRouter>
        <CollectionModelsTab
          collectionId="c1"
          accessToken="tok"
          api={false}
          createOpen={false}
          onCloseCreate={vi.fn()}
          onOpenCreate={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Knowledge models are available when the app runs in API mode/i)).toBeVisible();
    expect(listMock).not.toHaveBeenCalled();
  });
});
