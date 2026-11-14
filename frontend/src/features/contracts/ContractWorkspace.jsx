import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft, ArrowDownToLine, CalendarDays, Check, ChevronDown, FileText,
  Languages, MessageSquareText, Pencil, RefreshCw, ShieldAlert, Sparkles, Trash2,
} from "lucide-react";
import { api, download } from "../../services/api";

const TABS = [
  ["overview", "Overview"], ["layout", "Document structure"], ["clauses", "Clauses"], ["risks", "Risks"],
  ["obligations", "Obligations"], ["timeline", "Timeline"], ["assistant", "Assistant"],
  ["versions", "Versions"], ["translation", "Translate"], ["reports", "Reports"],
];
const TARGET_LANGUAGES = [
  ["ar", "Arabic"], ["zh-Hans", "Chinese (Simplified)"], ["fr", "French"],
  ["de", "German"], ["it", "Italian"], ["ja", "Japanese"],
  ["pt", "Portuguese"], ["es", "Spanish"],
];

export default function ContractWorkspace({ contractId, onBack, setNotice }) {
  const [contract, setContract] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [model, setModel] = useState("");
  const [analysisHistory, setAnalysisHistory] = useState([]);
  const [tab, setTab] = useState("overview");
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [answer, setAnswer] = useState(null);
  const [versions, setVersions] = useState([]);
  const [compareFrom, setCompareFrom] = useState("");
  const [compareTo, setCompareTo] = useState("");
  const [comparison, setComparison] = useState(null);
  const [targetLanguage, setTargetLanguage] = useState("es");
  const [translationScope, setTranslationScope] = useState("contract");
  const [translation, setTranslation] = useState(null);
  const [translationHistory, setTranslationHistory] = useState([]);

  const load = useCallback(async () => {
    try {
      const result = await api(`/contracts/${contractId}`);
      const history = await api(`/contracts/${contractId}/analyses`);
      setContract(result);
      setAnalysis(result.analysis);
      setAnalysisHistory(history);
      setVersions(result.versions || []);
      if (result.versions?.[0]) {
        const history = await api(`/versions/${result.versions[0].id}/translations`);
        setTranslationHistory(history);
      } else {
        setTranslationHistory([]);
      }
      if (result.versions?.length) {
        setCompareFrom(result.versions.at(-1).id);
        setCompareTo(result.versions[0].id);
      }
      setModel(result.analysis_model || "");
    } catch (error) {
      setNotice(error.message);
    }
  }, [contractId, setNotice]);
  useEffect(() => { setTab("overview"); setAnswer(null); setComparison(null); setTranslation(null); load(); }, [contractId, load]);

  const analyze = async () => {
    setBusy(true);
    try {
      const result = await api(`/contracts/${contractId}/analyze`, { method: "POST" });
      setAnalysis(result.analysis);
      setModel(result.model);
      setNotice("Analysis saved with source-checked evidence.");
      await load();
    } catch (error) {
      setNotice(error.message);
    } finally { setBusy(false); }
  };

  const rename = async () => {
    const name = window.prompt("Contract name", contract?.name || "");
    if (!name?.trim()) return;
    try {
      await api(`/contracts/${contractId}`, { method: "PATCH", body: JSON.stringify({ name: name.trim() }) });
      await load();
    } catch (error) { setNotice(error.message); }
  };

  const remove = async () => {
    if (!window.confirm(`Delete “${contract?.name}” and its versions?`)) return;
    try {
      await api(`/contracts/${contractId}`, { method: "DELETE" });
      onBack();
    } catch (error) { setNotice(error.message); }
  };

  const ask = async (event) => {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setAnswer(null);
    try {
      const result = await api(`/contracts/${contractId}/ask`, {
        method: "POST",
        body: JSON.stringify({ question: question.trim(), conversation_id: conversationId }),
      });
      setConversationId(result.conversation_id);
      setAnswer(result);
      setQuestion("");
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const compare = async () => {
    if (!compareFrom || !compareTo || compareFrom === compareTo) {
      setNotice("Choose two different versions to compare.");
      return;
    }
    setBusy(true);
    try {
      setComparison(await api(`/contracts/${contractId}/compare`, {
        method: "POST",
        body: JSON.stringify({ first_version_id: compareFrom, second_version_id: compareTo }),
      }));
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const translate = async (event) => {
    event.preventDefault();
    const version = versions[0];
    if (!version) return;
    setBusy(true);
    try {
      const result = await api(`/versions/${version.id}/translate`, {
        method: "POST",
        body: JSON.stringify({ target_language: targetLanguage, scope: translationScope }),
      });
      setTranslation(result);
      setTranslationHistory((current) => [result, ...current]);
      setNotice("Translation saved using Azure Translator text translation.");
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const exportReport = async (format) => {
    const version = versions[0];
    if (!version) return;
    try { await download(`/versions/${version.id}/report?format=${format}`); }
    catch (error) { setNotice(error.message); }
  };

  if (!contract) return <div className="page-wrap"><div className="skeleton large-skeleton" /></div>;
  const clauses = analysis?.clauses || [];
  const risks = analysis?.risks || [];
  const obligations = analysis?.obligations || [];

  return (
    <div className="page-wrap">
      <button className="back-button" onClick={onBack}><ArrowLeft size={16} /> Project contracts</button>
      <header className="contract-heading">
        <div className="contract-title"><span className="file-mark large"><FileText size={21} /></span><div><span className="eyebrow">CONTRACT REVIEW</span><h1>{contract.name}</h1><p>{contract.file_type?.toUpperCase()} · {contract.page_count ? `${contract.page_count} pages` : "page count unavailable"} · {versions.length} version{versions.length === 1 ? "" : "s"}</p></div></div>
        <div className="heading-actions">
          <button className="button secondary" onClick={rename}><Pencil size={15} /> Rename</button>
          <button className="button secondary" onClick={analyze} disabled={busy}><Sparkles size={15} /> {busy ? "Reviewing…" : analysis ? "Reanalyse" : "Analyze"}</button>
          <button className="button danger-ghost" onClick={remove} aria-label="Delete contract"><Trash2 size={16} /></button>
        </div>
      </header>
      <nav className="tab-bar" aria-label="Contract details">
        {TABS.map(([id, label]) => <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}
      </nav>
      {!analysis && <div className="callout"><Sparkles size={18} /><div><b>Start with a source-backed review</b><span>Findings are checked against the extracted document text. Local rule-based results are clearly identified when Ollama is unavailable.</span></div><button className="button primary" onClick={analyze} disabled={busy}>{busy ? "Reviewing…" : "Analyze contract"}</button></div>}
      {tab === "overview" && (analysis ? <Overview analysis={analysis} model={model} clauses={clauses} risks={risks} obligations={obligations} /> : <div className="empty-panel"><FileText size={25} /><h3>Analysis is not available yet</h3><p>Run a review to extract clauses, identify source-supported risks, and summarize the agreement.</p></div>)}
      {tab === "layout" && <DocumentLayout layout={contract.layout_data} />}
      {tab === "clauses" && <section className="surface"><SectionTitle icon={<FileText size={17} />} title="Identified clauses" count={clauses.length} /><EvidenceList items={clauses} type="clause" empty="No matching clause text was identified." /></section>}
      {tab === "risks" && <section className="surface"><SectionTitle icon={<ShieldAlert size={17} />} title="Risk review" count={risks.length} /><div className="risk-score"><span>Rule transparency</span><b>{analysis?.risk_score ?? "—"}<small>/100</small></b><p>{analysis?.risk_methodology || "No analysis yet. Findings are not legal advice."}</p></div><EvidenceList items={risks} type="risk" empty="No source-verified risks were returned. This is not a guarantee of no risk." /></section>}
      {tab === "obligations" && <section className="surface"><SectionTitle icon={<Check size={17} />} title="Obligations" count={obligations.length} /><EvidenceList items={obligations} type="obligation" empty="No source-verified obligations were extracted." /></section>}
      {tab === "timeline" && <Timeline items={obligations} />}
      {tab === "assistant" && <section className="surface assistant-surface"><span className="eyebrow">CONTRACT-ONLY RETRIEVAL</span><h2>Ask about this agreement</h2><p>Responses use Azure AI Search hybrid retrieval, are checked by Azure Content Safety, and include page citations. If relevant evidence is missing, the assistant will say so.</p><form className="ask-form" onSubmit={ask}><textarea rows="3" maxLength="10000" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="e.g. What notice is required to terminate?" /><button className="button primary" disabled={busy || !question.trim()}><MessageSquareText size={16} />{busy ? "Searching…" : "Ask contract"}</button></form>{answer && <div className="assistant-result"><b>Answer</b><p>{answer.answer}</p>      <div className="citation-list">{answer.citations.map((citation, index) => <article className="citation" key={citation.chunk_id}><b>[S{citation.source_number || index + 1}] {citation.document} · {citation.page ? `page ${citation.page}` : "page unavailable"}</b><p>{citation.excerpt}</p></article>)}</div></div>}</section>}
      {tab === "versions" && <section className="surface"><SectionTitle icon={<RefreshCw size={17} />} title="Version history" count={versions.length} /><div className="version-list">{versions.map((version) => <div className="version-card" key={version.id}><div className="version-badge">V{version.version_number}</div><div><b>{version.filename}</b><small>{version.file_type.toUpperCase()} · {version.page_count ? `${version.page_count} pages` : "page count unavailable"} · {new Date(version.created_at).toLocaleString()}</small></div><button className="button text-button" onClick={() => { setCompareFrom(version.id); setTab("versions"); }}>Select earlier version</button></div>)}</div>{versions.length > 1 && <div className="compare-controls"><label>Earlier<select value={compareFrom} onChange={(event) => setCompareFrom(event.target.value)}>{versions.map((v) => <option value={v.id} key={v.id}>Version {v.version_number}</option>)}</select></label><ChevronDown size={16} /><label>Later<select value={compareTo} onChange={(event) => setCompareTo(event.target.value)}>{versions.map((v) => <option value={v.id} key={v.id}>Version {v.version_number}</option>)}</select></label><button className="button primary" onClick={compare} disabled={busy}>{busy ? "Comparing…" : "Compare versions"}</button></div>}{comparison && <Comparison result={comparison} />}{versions.length < 2 && <p className="subtle-copy">Upload a new version to compare changes.</p>}<h3 className="history-heading">Analysis history</h3>{analysisHistory.length ? <div className="version-list">{analysisHistory.map((item) => <article className="version-card" key={item.id}><div className="version-badge"><Sparkles size={14} /></div><div><b>Version {versions.find((version) => version.id === item.version_id)?.version_number || "—"} · {item.model}</b><small>{new Date(item.created_at).toLocaleString()} · Risk score {item.analysis.risk_score ?? "not scored"}</small></div></article>)}</div> : <p className="subtle-copy">No saved analyses yet.</p>}</section>}
      {tab === "translation" && <section className="surface"><span className="eyebrow">AZURE TRANSLATOR · F0 TEXT API</span><h2>Translate contract content</h2><p className="subtle-copy">Translate the extracted text or saved executive summary. The free tier does not include layout-preserving DOCX/PDF document translation.</p><form className="settings-form" onSubmit={translate}><label>Content<select value={translationScope} onChange={(event) => setTranslationScope(event.target.value)}><option value="contract">Full extracted contract</option><option value="summary" disabled={!analysis}>Executive summary</option></select></label><label>Translate to<select value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}>{TARGET_LANGUAGES.map(([code, label]) => <option value={code} key={code}>{label}</option>)}</select></label><button className="button primary" disabled={busy || !versions.length || (translationScope === "summary" && !analysis)}><Languages size={16} />{busy ? "Translating…" : "Translate text"}</button></form>{translation && <article className="assistant-result"><b>{translation.source_language} → {translation.target_language} · {translation.scope}</b><pre className="translation-text">{translation.text}</pre></article>}{translationHistory.length > 0 && <><h3 className="history-heading">Saved translations</h3><div className="version-list">{translationHistory.map((item) => <button className="version-card translation-history-item" key={item.id} onClick={() => setTranslation(item)}><div className="version-badge"><Languages size={14} /></div><div><b>{item.source_language} → {item.target_language} · {item.scope}</b><small>{new Date(item.created_at).toLocaleString()}</small></div></button>)}</div></>}</section>}
      {tab === "reports" && <section className="surface"><span className="eyebrow">EXPORT</span><h2>Download a review report</h2><p className="subtle-copy">Exports include the saved analysis, its source excerpts and page references. Generate an analysis first.</p><div className="export-grid">{["pdf", "md", "json"].map((format) => <button key={format} className="export-card" onClick={() => exportReport(format)} disabled={!analysis}><span><ArrowDownToLine size={17} /></span><b>{format.toUpperCase()} report</b><small>{format === "pdf" ? "Printable document" : format === "md" ? "Markdown text" : "Structured data"}</small></button>)}</div></section>}
    </div>
  );
}

function SectionTitle({ icon, title, count }) {
  return <div className="surface-title">{icon}<h2>{title}</h2><span className="count-pill">{count}</span></div>;
}

function Overview({ analysis, model, clauses, risks, obligations }) {
  return <>
    <section className="overview-hero"><div><span className="eyebrow">EXECUTIVE SUMMARY</span><h2>{analysis.contract_type || "Contract review"}</h2><p>{analysis.summary || "No source-backed summary was produced."}</p><small>Method: {model || "Saved analysis"} · Verify all findings against the original agreement.</small></div><div className="score-orb"><b>{analysis.risk_score ?? "—"}</b><span>review<br />score</span></div></section>
    {analysis.content_safety?.content_moderation && <section className="surface"><SectionTitle icon={<ShieldAlert size={17} />} title="Content Safety screening" count={analysis.content_safety.content_moderation.categories?.length || 0} /><p className="subtle-copy">{analysis.content_safety.content_moderation.blocked ? "A category met the configured severity threshold; AI interpretation was restricted to rule-based findings." : "No category met the configured severity threshold."} Prompt Shields flagged {analysis.content_safety.prompt_shields?.flagged_document_ids?.length || 0} document passages for instruction-like content.</p></section>}
    <div className="metric-grid"><Metric label="Clauses identified" value={clauses.length} /><Metric label="Risk flags" value={risks.length} /><Metric label="Obligations" value={obligations.length} /><Metric label="Missing provisions" value={analysis.missing_clauses?.length || 0} /></div>
    {analysis.missing_clauses?.length > 0 && <section className="surface"><SectionTitle icon={<ShieldAlert size={17} />} title="Provisions to review" count={analysis.missing_clauses.length} /><EvidenceList items={analysis.missing_clauses} type="missing" empty="" /></section>}
    {analysis.parties?.length > 0 && <section className="surface"><SectionTitle icon={<FileText size={17} />} title="Parties" count={analysis.parties.length} /><div className="party-grid">{analysis.parties.map((party, index) => <div className="party-card" key={index}><b>{party.name}</b><small>{party.role}</small></div>)}</div></section>}
    {analysis.key_terms?.length > 0 && <section className="surface"><SectionTitle icon={<FileText size={17} />} title="Key terms" count={analysis.key_terms.length} /><div className="terms-grid">{analysis.key_terms.map((term, index) => <div className="key-term" key={index}><small>{term.label}</small><b>{term.value}</b><span>{term.source}</span></div>)}</div></section>}
    {analysis.language_insights && <section className="surface"><SectionTitle icon={<Languages size={17} />} title="Language insights" count={analysis.language_insights.entities?.length || 0} /><p className="subtle-copy">Detected language: {(analysis.language_insights.detected_languages || []).map((item) => item.name || item.language).join(", ") || "Unavailable"}</p>{analysis.language_insights.key_phrases?.length > 0 && <p className="subtle-copy">Key phrases: {analysis.language_insights.key_phrases.slice(0, 20).join(" · ")}</p>}{analysis.language_insights.entities?.length > 0 && <div className="terms-grid">{analysis.language_insights.entities.slice(0, 20).map((entity, index) => <div className="key-term" key={`${entity.offset}-${index}`}><small>{entity.category || "Entity"}</small><b>{entity.text}</b><span>{entity.confidenceScore != null ? `Confidence ${Math.round(entity.confidenceScore * 100)}%` : "Azure Language entity"}</span></div>)}</div>}</section>}
    <p className="disclaimer">DocuMind provides informational support, not legal advice. Review the source contract before acting.</p>
  </>;
}

function Metric({ label, value }) { return <div className="metric-card"><b>{value}</b><span>{label}</span></div>; }

function DocumentLayout({ layout }) {
  if (!layout) return <div className="empty-panel"><FileText size={25} /><h3>Structured layout is unavailable</h3><p>TXT uploads are decoded locally and do not have page layout or table structure.</p></div>;
  const tables = layout.tables || [];
  const paragraphs = layout.paragraphs || [];
  return <section className="surface"><span className="eyebrow">AZURE DOCUMENT INTELLIGENCE</span><h2>Document structure</h2><p className="subtle-copy">{layout.model_id || "Document Intelligence"} · {layout.pages?.length || 0} pages · {tables.length} tables · {paragraphs.length} paragraphs</p>{tables.length > 0 && <><h3 className="history-heading">Tables</h3><div className="version-list">{tables.map((table, index) => { const rows = new Map(); (table.cells || []).forEach((cell) => { const row = rows.get(cell.rowIndex) || []; row[cell.columnIndex] = cell.content || ""; rows.set(cell.rowIndex, row); }); return <article className="evidence-card" key={`table-${index}`}><b>Table {index + 1} · {table.rowCount || rows.size} rows × {table.columnCount || 0} columns</b>{Array.from(rows.entries()).sort(([left], [right]) => left - right).map(([rowNumber, cells]) => <p key={rowNumber}>{cells.filter(Boolean).join(" | ")}</p>)}</article>; })}</div></>}{paragraphs.length > 0 && <><h3 className="history-heading">Paragraphs</h3><div className="evidence-list">{paragraphs.map((paragraph, index) => <article className="evidence-card" key={`paragraph-${index}`}><small>{paragraph.role || "Paragraph"}{paragraph.boundingRegions?.[0]?.pageNumber ? ` · page ${paragraph.boundingRegions[0].pageNumber}` : ""}</small><p>{paragraph.content}</p></article>)}</div></>}{tables.length === 0 && paragraphs.length === 0 && <p className="inline-empty">No separate tables or paragraphs were returned.</p>}</section>;
}

function EvidenceList({ items, type, empty }) {
  if (!items?.length) return <div className="inline-empty">{empty}</div>;
  return <div className="evidence-list">{items.map((item, index) => {
    const label = type === "clause" ? item.category : type === "risk" ? item.title : item.responsible_party;
    const excerpt = type === "clause" ? item.excerpt : type === "risk" ? item.evidence : item.source;
    return <article className="evidence-card" key={`${label}-${index}`}><div className="evidence-heading"><b>{label || "Finding"}</b><span className={`tag ${String(item.severity || item.risk_level || item.evidence_type || "review").toLowerCase().replaceAll(" ", "-")}`}>{item.severity || item.risk_level || item.evidence_type || "Review"}</span></div><p>{item.reason || item.summary || item.obligation || item.explanation}</p>{excerpt && <blockquote>{excerpt}</blockquote>}<div className="evidence-footer"><span>{item.page ? `Page ${item.page}` : "Page not available"}{item.section_reference ? ` · ${item.section_reference}` : ""}</span>{item.recommendation && <span>{item.recommendation}</span>}</div></article>;
  })}</div>;
}

function Timeline({ items }) {
  const dated = items.filter((item) => item.deadline);
  return <section className="surface"><SectionTitle icon={<CalendarDays size={17} />} title="Timeline & deadlines" count={dated.length} />  {dated.length ? <div className="timeline">{dated.map((item, index) => <article key={index}><span className="timeline-dot" /><small>{item.deadline}</small><b>{item.obligation}</b><span>{item.responsible_party} · {item.page ? `Page ${item.page}` : "Page not available"}</span></article>)}</div> : <div className="inline-empty">No explicit dated deadlines were extracted from source-backed obligations.</div>}</section>;
}

function Comparison({ result }) {
  return <div className="comparison-results"><div className="comparison-summary"><span><b>{result.added}</b> added</span><span><b>{result.removed}</b> removed</span><span><b>{result.modified}</b> modified</span>{result.risk_change?.first_score != null && <span>Risk score <b>{result.risk_change.first_score} → {result.risk_change.second_score}</b></span>}</div>{result.changes.length ? result.changes.map((change, index) => <article className="change-card" key={index}><div><b>{change.section}</b><span className={`tag ${change.status}`}>{change.status}</span></div><pre>{change.diff.map((line, lineIndex) => <span className={line.startsWith("+") && !line.startsWith("+++") ? "diff-added" : line.startsWith("-") && !line.startsWith("---") ? "diff-removed" : ""} key={lineIndex}>{line || " "}{'\n'}</span>)}</pre></article>) : <div className="inline-empty">No changes were detected between these versions.</div>}{result.obligation_changes?.length > 0 && <section className="obligation-changes"><h3>Obligation changes</h3>{result.obligation_changes.map((change, index) => { const item = change.after || change.before; return <article className="evidence-card" key={index}><div className="evidence-heading"><b>{item.responsible_party || "Responsible party not stated"}</b><span className={`tag ${change.status}`}>{change.status}</span></div><p>{change.before?.obligation || "No prior obligation"}{change.after?.obligation ? ` → ${change.after.obligation}` : " → removed"}</p><small>Deadline: {change.before?.deadline || "not stated"} → {change.after?.deadline || "not stated"}</small></article>; })}</section>}</div>;
}
