import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ProjectWorkspace from "./ProjectWorkspace";

const apiMock = vi.hoisted(() => vi.fn());

vi.mock("../../services/api", () => ({ api: apiMock }));

describe("ProjectWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("offers version upload and owner-scoped contract deletion in the actions menu", async () => {
    let projectLoads = 0;
    apiMock.mockImplementation((path, options = {}) => {
      if (path === "/projects/project-1") {
        projectLoads += 1;
        return Promise.resolve({
          id: "project-1",
          name: "Supplier contracts",
          description: "",
          contracts: projectLoads === 1 ? [{
            id: "contract-1",
            name: "Supply terms",
            status: "ready",
            version_count: 1,
            file_type: "pdf",
            page_count: 2,
            updated_at: "2026-11-14T10:00:00Z",
          }] : [],
        });
      }
      if (path === "/projects/project-1/conversations") return Promise.resolve([]);
      if (path === "/contracts/contract-1" && options.method === "DELETE") {
        return Promise.resolve({ deleted: "contract-1" });
      }
      throw new Error(`Unexpected request: ${path} ${options.method || "GET"}`);
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <ProjectWorkspace
        projectId="project-1"
        onBack={vi.fn()}
        onOpenContract={vi.fn()}
        setNotice={vi.fn()}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Contract actions: Supply terms" }));
    expect(document.querySelector(".contract-table").classList.contains("has-open-menu")).toBe(true);
    expect(screen.getByRole("menuitem", { name: /Upload new version/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("menuitem", { name: /Delete contract/ }));

    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(
      "/contracts/contract-1",
      { method: "DELETE" },
    ));
    expect(await screen.findByText("No contracts in this project yet")).toBeTruthy();
  });
});
