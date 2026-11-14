import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AssistantChat from "./AssistantChat";

const apiMock = vi.hoisted(() => vi.fn());

vi.mock("../../services/api", () => ({ api: apiMock }));

describe("AssistantChat", () => {
  afterEach(() => cleanup());
  beforeEach(() => apiMock.mockReset());

  it("loads saved messages and keeps evidence in a closed disclosure by default", async () => {
    apiMock.mockResolvedValue([{
      id: "chat-1",
      title: "Payment terms",
      created_at: "2026-11-14T10:00:00Z",
      messages: [
        { id: "message-1", role: "user", content: "When is payment due?", citations: [] },
        {
          id: "message-2",
          role: "assistant",
          content: "Payment is due within 30 days. [S1]",
          citations: [{
            chunk_id: "chunk-1",
            document: "terms.pdf",
            page: 2,
            excerpt: "Customer shall pay each invoice within 30 days.",
          }],
        },
      ],
    }]);

    render(<AssistantChat projectId="project-1" setNotice={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Payment terms" })).toBeTruthy();
    expect(screen.getByText("Payment is due within 30 days.")).toBeTruthy();
    expect(screen.queryByText("[S1]")).toBeNull();
    const disclosure = document.querySelector("details.assistant-evidence");
    expect(disclosure.open).toBe(false);
    fireEvent.click(screen.getByText("Show supporting evidence (1)"));
    expect(disclosure.open).toBe(true);
    expect(screen.getByText("Customer shall pay each invoice within 30 days.")).toBeTruthy();
    expect(apiMock).toHaveBeenCalledWith("/projects/project-1/conversations");
  });

  it("creates a saved thread from a suggested prompt and restores it after sending", async () => {
    let listCalls = 0;
    const unexpectedCalls = [];
    apiMock.mockImplementation((path, options = {}) => {
      if (path === "/projects/project-1/conversations") {
        listCalls += 1;
        return Promise.resolve(listCalls === 1 ? [] : [{
          id: "new-chat",
          title: "Summarize the key responsibilities.",
          created_at: "2026-11-14T10:00:00Z",
          messages: [
            { id: "user-1", role: "user", content: "Summarize the key responsibilities.", citations: [] },
            { id: "assistant-1", role: "assistant", content: "The parties must perform the listed services.", citations: [] },
          ],
        }]);
      }
      if (path === "/projects/project-1/assistant/ask") {
        return Promise.resolve({ conversation_id: "new-chat", answer: "The parties must perform the listed services.", citations: [] });
      }
      unexpectedCalls.push([path, options]);
      return Promise.resolve([]);
    });

    render(<AssistantChat projectId="project-1" setNotice={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /Summarize the key responsibilities/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send question" }));

    expect(await screen.findByText("The parties must perform the listed services.")).toBeTruthy();
    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(
      "/projects/project-1/assistant/ask",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          question: "Summarize the key responsibilities.",
          conversation_id: null,
        }),
      }),
    ));
    expect(screen.getByText(/2 messages/)).toBeTruthy();
    expect(unexpectedCalls).toEqual([]);
  });
});
