import { ArrowRight, CalendarDays, FileText, Languages, ShieldAlert } from "lucide-react";
import "./ContractOverview.css";

const SEVERITY_LABELS = new Map([
  [0, "None detected"],
  [2, "Low"],
  [4, "Medium"],
  [6, "High"],
]);

const QUICK_LINKS = [
  ["clauses", "Review clauses"],
  ["risks", "Review risks"],
  ["obligations", "Review obligations"],
  ["timeline", "Open timeline"],
  ["assistant", "Ask a question"],
  ["translation", "Translate text"],
  ["reports", "Export report"],
];

export default function ContractOverview({
  analysis,
  model,
  clauses,
  risks,
  obligations,
  safetyFindings,
  languageInsights,
  onNavigate,
  onAnalyze,
  analyzing,
}) {
  const missingClauses = analysis?.missing_clauses || [];
  return (
    <div className="contract-overview">
      <section className="overview-hero">
        <div>
          <span className="eyebrow">{analysis ? "EXECUTIVE SUMMARY" : "CONTRACT REVIEW"}</span>
          <h2>{analysis?.contract_type || "Turn this contract into an actionable review"}</h2>
          <p>
            {analysis?.summary
              || "Review clauses, risks, responsibilities, key dates, language, and document safety. Findings are tied to the uploaded contract."}
          </p>
          {analysis
            ? <small>Method: {model || "Saved analysis"} · Verify all findings against the original agreement.</small>
            : <button className="button primary" onClick={onAnalyze} disabled={analyzing}>{analyzing ? "Reviewing…" : "Analyze contract"}</button>}
        </div>
        {analysis ? (
          <div className="score-orb" aria-label={`Review score ${analysis.risk_score ?? "not available"}`}>
            <b>{analysis.risk_score ?? "—"}</b>
            <span>review<br />score</span>
          </div>
        ) : null}
      </section>

      {analysis ? (
        <>
          <div className="metric-grid">
            <Metric label="Clauses identified" value={clauses.length} />
            <Metric label="Risk flags" value={risks.length} />
            <Metric label="Obligations" value={obligations.length} />
            <Metric label="Provisions to review" value={missingClauses.length} />
          </div>

          {analysis.parties?.length > 0 ? (
            <section className="surface">
              <SectionTitle icon={<FileText size={17} />} title="Parties" count={analysis.parties.length} />
              <div className="party-grid">
                {analysis.parties.map((party, index) => (
                  <div className="party-card" key={`${party.name}-${index}`}>
                    <b>{party.name}</b>
                    <small>{party.role || "Role not stated"}</small>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {analysis.key_terms?.length > 0 ? (
            <section className="surface">
              <SectionTitle icon={<FileText size={17} />} title="Key terms" count={analysis.key_terms.length} />
              <div className="terms-grid">
                {analysis.key_terms.map((term, index) => (
                  <div className="key-term" key={`${term.label}-${index}`}>
                    <small>{term.label}</small>
                    <b>{term.value}</b>
                    {term.source ? <span>{term.source}</span> : null}
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      <div className="overview-insights-grid">
        <ContentSafetyPanel findings={safetyFindings} />
        <LanguagePanel insights={languageInsights} />
      </div>

      <TranslatorPanel onNavigate={onNavigate} />

      {analysis ? (
        <div className="overview-insights-grid">
          <ClauseCoverage clauses={clauses} missingClauses={missingClauses} onNavigate={onNavigate} />
          <ReviewHighlights risks={risks} obligations={obligations} onNavigate={onNavigate} />
        </div>
      ) : null}

      <section className="surface overview-navigation">
        <SectionTitle icon={<ArrowRight size={17} />} title="Continue your review" />
        <div className="overview-link-grid">
          {QUICK_LINKS.map(([tab, label]) => (
            <button type="button" className="overview-link" key={tab} onClick={() => onNavigate(tab)}>
              {label}<ArrowRight size={14} />
            </button>
          ))}
        </div>
      </section>

      <p className="disclaimer">
        DocuMind provides informational support, not legal advice. A missing text match does not establish that a clause is legally required.
      </p>
    </div>
  );
}

function ContentSafetyPanel({ findings }) {
  const moderation = findings?.content_moderation;
  const shields = findings?.prompt_shields;
  const scores = new Map();
  for (const item of moderation?.categories || []) {
    const current = scores.get(item.category);
    if (!current || item.severity > current.severity) {
      scores.set(item.category, item);
    }
  }
  const threshold = moderation?.threshold;
  const thresholdLabel = Number.isInteger(threshold)
    ? `${SEVERITY_LABELS.get(threshold) || "Score"} (${threshold})`
    : "Unavailable";
  const flaggedPassages = (shields?.flagged_document_ids || []).map((value) => {
    const index = Number(value);
    return Number.isInteger(index) && index >= 0 ? index + 1 : value;
  });

  return (
    <section className="surface">
      <SectionTitle icon={<ShieldAlert size={17} />} title="Content Safety screening" />
      {moderation ? (
        <>
          <p className="overview-explainer">
            Azure checks hate, self-harm, sexual, and violence categories. Scores use 0, 2, 4, and 6; the configured threshold is {thresholdLabel}.
          </p>
          <div className="safety-table-wrap">
            <table className="safety-table">
              <thead><tr><th scope="col">Category</th><th scope="col">Highest level</th></tr></thead>
              <tbody>
                {[...scores.values()].map((item) => {
                  const level = safetyLevel(item.severity);
                  return (
                    <tr key={item.category}>
                      <th scope="row">{item.category}</th>
                      <td><span className={`safety-level ${level.tone}`}>{level.label} ({item.severity})</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className={`safety-status ${moderation.blocked ? "restricted" : "clear"}`}>
            {moderation.blocked
              ? "A category met the threshold; AI interpretation is restricted for this version."
              : "No category met the configured threshold. This is a content screen, not a legal-risk score."}
          </p>
        </>
      ) : <p className="overview-explainer">No Content Safety result was recorded for this version.</p>}

      {shields ? (
        <p className="prompt-shields-result">
          <b>Prompt Shields:</b>{" "}
          {flaggedPassages.length
            ? `Flagged passage${flaggedPassages.length === 1 ? "" : "s"} ${flaggedPassages.join(", ")} for instruction-like content.`
            : "No instruction-like passages were flagged."}
          {shields.user_prompt_attack ? " The review prompt was also flagged." : null}
        </p>
      ) : null}
    </section>
  );
}

function safetyLevel(score) {
  if (!Number.isInteger(score)) return { label: "Unknown", tone: "unknown" };
  if (score >= 6) return { label: "High", tone: "high" };
  if (score >= 4) return { label: "Medium", tone: "medium" };
  if (score >= 2) return { label: "Low", tone: "low" };
  return { label: "None detected", tone: "none" };
}

function LanguagePanel({ insights }) {
  const languages = insights?.detected_languages || [];
  const phrases = insights?.key_phrases || [];
  const entities = insights?.entities || [];
  return (
    <section className="surface">
      <SectionTitle icon={<Languages size={17} />} title="Language & text insights" count={entities.length} />
      <p className="overview-explainer">Azure AI Language detects languages and extracts entities and key phrases from the contract text.</p>
      {languages.length ? (
        <div className="language-results">
          {languages.map((item, index) => (
            <div className="language-result" key={`${item.language}-${index}`}>
              <b>{item.name || item.language}</b>
              <span>
                {item.language && item.name ? `${item.language.toUpperCase()} · ` : ""}
                {Number.isFinite(item.confidence) ? `${Math.round(item.confidence * 100)}% confidence` : "Confidence unavailable"}
              </span>
            </div>
          ))}
        </div>
      ) : <p className="inline-empty">Language detection is not available for this version.</p>}
      {phrases.length > 0 ? (
        <div className="language-section">
          <b>Key phrases</b>
          <div className="phrase-chips">{phrases.slice(0, 12).map((phrase, index) => <span key={`${phrase}-${index}`}>{phrase}</span>)}</div>
        </div>
      ) : null}
      {entities.length > 0 ? (
        <div className="language-section">
          <b>Entities</b>
          <div className="entity-list">
            {entities.slice(0, 8).map((entity, index) => (
              <div className="entity-row" key={`${entity.offset}-${index}`}>
                <span>{entity.text}</span>
                <small>
                  {entity.category || "Entity"}
                  {Number.isFinite(entity.confidenceScore) ? ` · ${Math.round(entity.confidenceScore * 100)}%` : null}
                </small>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function TranslatorPanel({ onNavigate }) {
  return (
    <section className="surface">
      <SectionTitle
        icon={<Languages size={17} />}
        title="On-demand translation"
        action={<button className="overview-text-link" onClick={() => onNavigate("translation")}>Open translator</button>}
      />
      <p className="overview-explainer">
        Azure Translator is called only when requested. It auto-detects the source language and translates extracted contract text or the latest saved summary, splitting longer text into 50,000-character segments. Translations are saved separately; they do not replace the source, analysis, or search index, and do not preserve PDF/DOCX layout.
      </p>
    </section>
  );
}

function ClauseCoverage({ clauses, missingClauses, onNavigate }) {
  const rows = [];
  const seen = new Set();
  for (const clause of clauses) {
    if (clause.category && !seen.has(clause.category)) {
      rows.push({
        category: clause.category,
        status: "Text match found",
        detected: true,
        detail: clause.excerpt || clause.evidence,
        page: clause.page,
      });
      seen.add(clause.category);
    }
  }
  for (const clause of missingClauses) {
    if (clause.category && !seen.has(clause.category)) {
      rows.push({
        category: clause.category,
        status: "No text match",
        detected: false,
        detail: clause.explanation || clause.reason || clause.recommendation,
      });
      seen.add(clause.category);
    }
  }
  return (
    <section className="surface">
      <SectionTitle
        icon={<FileText size={17} />}
        title="Clause coverage"
        count={rows.length}
        action={<button className="overview-text-link" onClick={() => onNavigate("clauses")}>All clauses</button>}
      />
      <p className="overview-explainer">Coverage reflects detected text only; “No text match” is not a legal conclusion.</p>
      {rows.length ? (
        <div className="coverage-list">
          {rows.map((row) => (
            <div className="coverage-row" key={row.category}>
              <div className="coverage-label">
                <span>{row.category}</span>
                {(row.detail || row.page) ? (
                  <small>{row.detail}{row.page ? `${row.detail ? " · " : ""}Page ${row.page}` : ""}</small>
                ) : null}
              </div>
              <span className={`coverage-status ${row.detected ? "detected" : "not-detected"}`}>{row.status}</span>
            </div>
          ))}
        </div>
      ) : <p className="inline-empty">Run an analysis to see clause coverage.</p>}
    </section>
  );
}

function ReviewHighlights({ risks, obligations, onNavigate }) {
  return (
    <section className="surface">
      <div className="review-highlight">
        <div className="highlight-heading">
          <SectionTitle icon={<ShieldAlert size={17} />} title="Priority risks" count={risks.length} />
          <button className="overview-text-link" onClick={() => onNavigate("risks")}>All risks</button>
        </div>
        {risks.length ? risks.slice(0, 3).map((risk, index) => (
          <article className="highlight-item" key={`${risk.title}-${index}`}>
            <div><b>{risk.title || "Risk to review"}</b><span className={`tag ${String(risk.severity || "review").toLowerCase()}`}>{risk.severity || "Review"}</span></div>
            <p>{risk.reason || risk.evidence}</p>
            {risk.recommendation ? <small>Suggested review: {risk.recommendation}</small> : null}
          </article>
        )) : <p className="inline-empty">No source-supported risk flags were returned.</p>}
      </div>

      <div className="review-highlight obligations-highlight">
        <div className="highlight-heading">
          <SectionTitle icon={<CalendarDays size={17} />} title="Responsibilities & dates" count={obligations.length} />
          <button className="overview-text-link" onClick={() => onNavigate("timeline")}>Timeline</button>
        </div>
        {obligations.length ? obligations.slice(0, 3).map((item, index) => (
          <article className="highlight-item" key={`${item.obligation}-${index}`}>
            <div><b>{item.responsible_party || "Responsible party not stated"}</b>{item.deadline ? <span className="obligation-deadline">{item.deadline}</span> : null}</div>
            <p>{item.obligation}</p>
          </article>
        )) : <p className="inline-empty">No source-verified obligations were extracted.</p>}
      </div>
    </section>
  );
}

function SectionTitle({ icon, title, count, action }) {
  return (
    <div className="surface-title">
      {icon}<h2>{title}</h2>
      {Number.isInteger(count) ? <span className="count-pill">{count}</span> : null}
      {action}
    </div>
  );
}

function Metric({ label, value }) {
  return <div className="metric-card"><b>{value}</b><span>{label}</span></div>;
}
