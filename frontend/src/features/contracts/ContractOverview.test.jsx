import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ContractOverview from "./ContractOverview";

describe("ContractOverview", () => {
  afterEach(() => cleanup());

  it("shows service results, review coverage, and navigates to detailed views", () => {
    const onNavigate = vi.fn();
    render(
      <ContractOverview
        analysis={{
          contract_type: "Services agreement",
          summary: "A source-backed summary.",
          risk_score: 32,
          missing_clauses: [{ category: "Data Protection" }],
          parties: [{ name: "Acme Ltd", role: "Customer" }],
          key_terms: [{ label: "Fees", value: "$4,800", source: "Page 1" }],
        }}
        model="Ollama"
        clauses={[{ category: "Payment" }]}
        risks={[{ title: "Late payment exposure", severity: "medium", reason: "Payment timing is unclear." }]}
        obligations={[{ responsible_party: "Customer", obligation: "Pay invoices", deadline: "2026-04-30" }]}
        safetyFindings={{
          content_moderation: {
            threshold: 4,
            blocked: true,
            categories: [
              { category: "Hate", severity: 0 },
              { category: "Hate", severity: 6 },
              { category: "SelfHarm", severity: 0 },
              { category: "Sexual", severity: 0 },
              { category: "Violence", severity: 4 },
            ],
          },
          prompt_shields: { flagged_document_ids: [1], user_prompt_attack: false },
        }}
        languageInsights={{
          detected_languages: [{ language: "en", name: "English", confidence: 1 }],
          key_phrases: ["payment terms"],
          entities: [{ text: "Acme Ltd", category: "Organization" }],
        }}
        onNavigate={onNavigate}
        onAnalyze={vi.fn()}
        analyzing={false}
      />,
    );

    expect(screen.getByRole("heading", { name: "Content Safety screening" })).toBeTruthy();
    expect(within(screen.getByRole("table")).getByText("Medium (4)")).toBeTruthy();
    expect(within(screen.getByRole("table")).getByText("High (6)")).toBeTruthy();
    expect(screen.getByText(/threshold is Medium \(4\)/i)).toBeTruthy();
    expect(screen.getByText(/AI interpretation is restricted/)).toBeTruthy();
    expect(screen.getByText(/Flagged passage 2/)).toBeTruthy();
    expect(screen.getByText("English")).toBeTruthy();
    expect(screen.getByText("EN · 100% confidence")).toBeTruthy();
    expect(screen.getByText("payment terms")).toBeTruthy();
    expect(screen.getByText("Text match found")).toBeTruthy();
    expect(screen.getByText("No text match")).toBeTruthy();
    expect(screen.getByText("Pay invoices")).toBeTruthy();
    expect(screen.getByText(/Azure Translator is called only when requested/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Review risks" }));
    expect(onNavigate).toHaveBeenCalledWith("risks");
    fireEvent.click(screen.getByRole("button", { name: "Open translator" }));
    expect(onNavigate).toHaveBeenCalledWith("translation");
  });

  it("offers a working analysis action before a saved analysis exists", () => {
    const onAnalyze = vi.fn();
    render(
      <ContractOverview
        analysis={null}
        model=""
        clauses={[]}
        risks={[]}
        obligations={[]}
        safetyFindings={null}
        languageInsights={null}
        onNavigate={vi.fn()}
        onAnalyze={onAnalyze}
        analyzing={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Analyze contract" }));
    expect(onAnalyze).toHaveBeenCalledOnce();
    expect(screen.getByText("No Content Safety result was recorded for this version.")).toBeTruthy();
  });
});
