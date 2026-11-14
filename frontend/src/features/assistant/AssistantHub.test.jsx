import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AssistantHub from "./AssistantHub";

const apiMock = vi.hoisted(() => vi.fn());

vi.mock("../../services/api", () => ({ api: apiMock }));

describe("AssistantHub", () => {
  afterEach(() => cleanup());
  beforeEach(() => apiMock.mockReset());

  it("defaults to a project that contains contracts", async () => {
    const unexpectedCalls = [];
    apiMock.mockImplementation((path) => {
      if (path === "/projects") {
        return Promise.resolve([
          { id: "empty-project", name: "Empty project", contract_count: 0 },
          { id: "contract-project", name: "Contract project", contract_count: 1 },
        ]);
      }
      if (path === "/projects/contract-project/conversations") return Promise.resolve([]);
      unexpectedCalls.push(path);
      return Promise.resolve([]);
    });

    render(<AssistantHub onBrowseProjects={vi.fn()} setNotice={vi.fn()} />);

    expect(await screen.findByText("Current scope:")).toBeTruthy();
    expect(screen.getByRole("combobox").value).toBe("contract-project");
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(
      "/projects/contract-project/conversations",
    ));
    expect(screen.queryByText("No contracts in this project yet")).toBeNull();
    expect(unexpectedCalls).toEqual([]);
  });

  it("explains that a project needs contracts before enabling chat", async () => {
    apiMock.mockResolvedValue([
      { id: "empty-project", name: "Empty project", contract_count: 0 },
    ]);

    render(<AssistantHub onBrowseProjects={vi.fn()} setNotice={vi.fn()} />);

    expect(await screen.findByText("No contracts in this project yet")).toBeTruthy();
    expect(screen.getByText(/Upload contracts to this project/)).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: "Ask DocuMind" })).toBeNull();
    expect(apiMock).toHaveBeenCalledTimes(1);
  });
});
