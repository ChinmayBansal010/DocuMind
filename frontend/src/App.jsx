import { useEffect, useMemo, useRef, useState } from "react";
import { Activity, ArrowDownToLine, ArrowUpRight, BookOpen, Check, ChevronDown, CircleHelp, Cloud, File, FileText, FileUp, Files, Gauge, LayoutDashboard, LoaderCircle, MessageSquareText, MoreHorizontal, Plus, Search, Settings, ShieldCheck, Sparkles, Trash2, UploadCloud, X, Zap } from "lucide-react";

const nav = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, group: "WORKSPACE" },
  { id: "documents", label: "Documents", icon: Files },
  { id: "ask", label: "Ask documents", icon: MessageSquareText },
  { id: "extract", label: "Extraction", icon: FileText },
  { id: "safety", label: "Responsible AI", icon: ShieldCheck, group: "TOOLS" },
  { id: "activity", label: "Activity", icon: Activity },
  { id: "settings", label: "Settings", icon: Settings, group: "SYSTEM" }
];
const api = async (path, options = {}) => {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Something went wrong. Please try again.");
  return data;
};
const dateLabel = value => value ? new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "—";
const shortName = name => name.length > 26 ? name.slice(0, 23) + "…" : name;

function App() {
  const [page, setPage] = useState("overview");
  const [overview, setOverview] = useState({ stats: {}, documents: [], integrations: {} });
  const [documents, setDocuments] = useState([]);
  const [activity, setActivity] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [question, setQuestion] = useState("");
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [answer, setAnswer] = useState(null);
  const [top, setTop] = useState(5);
  const [extractId, setExtractId] = useState("");
  const [fields, setFields] = useState("InvoiceNumber, InvoiceDate, CustomerName, TaxAmount, TotalAmount");
  const [extraction, setExtraction] = useState(null);
  const [moderationText, setModerationText] = useState("");
  const [moderation, setModeration] = useState(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef(null);

  const refresh = async () => {
    const [o, d, a, s] = await Promise.all([api("/api/overview"), api("/api/documents"), api("/api/activity"), api("/api/settings")]);
    setOverview(o); setDocuments(d); setActivity(a); setSettings(s);
    if (!extractId && d.length) setExtractId(String(d[0].id));
  };
  useEffect(() => { refresh().catch(e => setNotice({ type: "error", text: e.message })).finally(() => setLoading(false)); }, []);
  const integrationCount = useMemo(() => ["azure_search", "document_intelligence", "content_safety", "ollama"].filter(key => overview.integrations?.[key]).length, [overview.integrations]);

  const upload = async files => {
    if (!files?.length) return;
    setBusy(true); setNotice(null);
    const form = new FormData();
    [...files].forEach(file => form.append("files", file));
    try {
      const result = await api("/api/documents", { method: "POST", body: form });
      await refresh();
      const processed = result.results.filter(x => x.status === "processed").length;
      const failed = result.results.filter(x => x.status === "error");
      setNotice({ type: failed.length ? "warning" : "success", text: `${processed} file(s) processed. ${failed.map(x => x.name + ": " + x.message).join(" ")}` });
    } catch (e) { setNotice({ type: "error", text: e.message }); }
    finally { setBusy(false); if (fileInput.current) fileInput.current.value = ""; }
  };
  const remove = async doc => {
    if (!window.confirm(`Delete “${doc.name}” from your library?`)) return;
    try { await api(`/api/documents/${doc.id}`, { method: "DELETE" }); await refresh(); setNotice({ type: "success", text: "Document deleted." }); }
    catch (e) { setNotice({ type: "error", text: e.message }); }
  };
  const ask = async e => {
    e.preventDefault(); if (!question.trim()) return;
    setBusy(true); setAnswer(null); setNotice(null);
    try { setAnswer(await api("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, documents: selectedDocs, top }) })); }
    catch (e) { setNotice({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  };
  const extract = async e => {
    e.preventDefault(); setBusy(true); setExtraction(null);
    try { setExtraction(await api("/api/extract", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ document_id: Number(extractId), fields: fields.split(",").map(x => x.trim()).filter(Boolean) }) })); }
    catch (e) { setNotice({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  };
  const moderate = async e => {
    e.preventDefault(); setBusy(true); setModeration(null);
    try { setModeration(await api("/api/moderate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: moderationText }) })); }
    catch (e) { setNotice({ type: "error", text: e.message }); }
    finally { setBusy(false); }
  };
  const download = (content, filename, type) => {
    const blob = new Blob([content], { type }); const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
  };
  const pageTitle = nav.find(x => x.id === page)?.label || "Overview";

  if (loading) return <div className="boot"><div className="brand-mark"><Sparkles size={20}/></div><span>Preparing your workspace</span></div>;

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Sparkles size={19}/></div><div><strong>documind</strong><span>DOCUMENT INTELLIGENCE</span></div></div>
      <button className="workspace-switch"><div className="workspace-avatar">D</div><div className="workspace-meta"><b>Personal workspace</b><small>Local environment</small></div><ChevronDown size={15}/></button>
      <div className="nav-scroll">
        {nav.map(item => <div key={item.id}>{item.group && <div className="nav-group">{item.group}</div>}<button className={`nav-item ${page === item.id ? "active" : ""}`} onClick={() => { setPage(item.id); setNotice(null); }}><item.icon size={17}/><span>{item.label}</span>{item.id === "documents" && documents.length > 0 && <small>{documents.length}</small>}</button></div>)}
      </div>
      <div className="sidebar-bottom"><div className="connection-card"><div className="connection-top"><span className="status-dot"/><b>Hybrid workspace</b></div><p>Local processing with Azure services when configured.</p><button onClick={() => setPage("settings")}>View integrations <ArrowUpRight size={13}/></button></div><div className="profile"><div className="profile-avatar">DM</div><div><b>DocuMind</b><small>Community edition</small></div><MoreHorizontal size={17}/></div></div>
    </aside>
    <main className="main">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <b>{pageTitle}</b></div><div className="top-actions"><div className="api-status"><span className="status-dot"/><span>API operational</span></div><button className="icon-button" title="Help"><CircleHelp size={18}/></button><div className="top-avatar">D</div></div></header>
      <div className="content">
        {notice && <div className={`notice ${notice.type}`}><span>{notice.text}</span><button onClick={() => setNotice(null)}><X size={15}/></button></div>}
        {page === "overview" && <><div className="hero-row"><div><div className="eyebrow">YOUR KNOWLEDGE, IN ONE PLACE</div><h1>Good documents.<br/><span>Clearer decisions.</span></h1><p className="lead">A focused workspace to organize, search and understand the information inside your files.</p><button className="primary-button" onClick={() => setPage("documents")}><Plus size={16}/> Add documents</button></div><div className="hero-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="hero-sheet"><div className="sheet-icon"><FileText size={25}/></div><div className="sheet-line wide"/><div className="sheet-line"/><div className="sheet-line short"/><div className="sheet-highlight"><Sparkles size={13}/> Knowledge, connected</div></div><div className="floating-chip chip-a"><Search size={14}/> Search</div><div className="floating-chip chip-b"><ShieldCheck size={14}/> Protected</div><div className="floating-chip chip-c"><Cloud size={14}/> Synced</div></div></div>
          <div className="metrics-grid"><Metric label="Documents" value={overview.stats.documents ?? 0} icon={Files} note="In your library"/><Metric label="Indexed chunks" value={overview.stats.chunks ?? 0} icon={BookOpen} note="Ready to retrieve"/><Metric label="Questions asked" value={overview.stats.queries ?? 0} icon={MessageSquareText} note="Across your workspace"/><Metric label="Integrations active" value={integrationCount} icon={Zap} note="Configured services"/></div>
          <div className="section-grid"><section className="panel recent-panel"><div className="panel-heading"><div><h2>Recently added</h2><p>Your latest documents and files</p></div><button className="text-button" onClick={() => setPage("documents")}>View library <ArrowUpRight size={14}/></button></div>{overview.documents.length ? <div className="document-table"><div className="table-head"><span>NAME</span><span>TYPE</span><span>CHUNKS</span><span>ADDED</span></div>{overview.documents.slice(0,6).map(doc => <div className="table-row" key={doc.id}><div className="file-cell"><div className="file-icon"><FileText size={17}/></div><b title={doc.name}>{shortName(doc.name)}</b></div><span className="type-pill">{doc.file_type.toUpperCase()}</span><span className="muted">{doc.chunk_count}</span><span className="muted">{dateLabel(doc.created_at)}</span></div>)}</div> : <Empty icon={Files} title="Your library is empty" text="Upload a document to start building your knowledge workspace." action="Add your first document" onClick={() => setPage("documents")}/>}</section>
            <section className="panel pipeline-panel"><div className="panel-heading"><div><h2>How it works</h2><p>From files to useful answers</p></div><div className="panel-icon"><Gauge size={17}/></div></div><div className="pipeline">{[{n:"01",t:"Bring your files",d:"Upload common document formats",icon:FileUp},{n:"02",t:"Extract & organize",d:"Parse text and build searchable chunks",icon:BookOpen},{n:"03",t:"Ask with context",d:"Retrieve passages and trace sources",icon:MessageSquareText}].map(x=><div className="pipeline-step" key={x.n}><div className="step-number">{x.n}</div><div className="step-icon"><x.icon size={16}/></div><div><b>{x.t}</b><p>{x.d}</p></div></div>)}</div></section></div></>}
        {page === "documents" && <><PageHeading eyebrow="YOUR KNOWLEDGE BASE" title="Document library" subtitle="Bring your files together. DocuMind extracts their content and makes it searchable." action={<button className="primary-button" onClick={() => fileInput.current?.click()}><Plus size={16}/> Upload files</button>}/><input ref={fileInput} type="file" multiple hidden accept=".pdf,.docx,.txt,.md,.pptx,.xlsx,.csv,.png,.jpg,.jpeg,.tif,.tiff" onChange={e => upload(e.target.files)}/><div className={`upload-zone ${dragging ? "dragging" : ""}`} onDragOver={e => {e.preventDefault();setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={e => {e.preventDefault();setDragging(false);upload(e.dataTransfer.files);}} onClick={() => fileInput.current?.click()}><div className="upload-symbol"><UploadCloud size={23}/></div><b>Drop files here, or <span>browse</span></b><p>PDF, Word, PowerPoint, Excel, CSV, text and images · Up to {settings?.limits.max_upload_mb || 20} MB each</p>{busy && <div className="inline-progress"><LoaderCircle size={15}/> Processing your files…</div>}</div><div className="library-toolbar"><div><h2>All documents <span className="count-badge">{documents.length}</span></h2><p>Stored locally with searchable text and metadata</p></div><div className="search-mini"><Search size={15}/><input placeholder="Search by filename" onChange={e => document.querySelectorAll("[data-doc-name]").forEach(el => el.closest(".library-row").hidden = !el.dataset.docName.toLowerCase().includes(e.target.value.toLowerCase()))}/></div></div>{documents.length ? <div className="library-list">{documents.map(doc=><div className="library-row" key={doc.id}><div className="file-icon large"><FileText size={19}/></div><div className="library-info"><b data-doc-name={doc.name}>{doc.name}</b><span>{doc.file_type.toUpperCase()} · {doc.pages} page(s) · Added {dateLabel(doc.created_at)}</span></div><div className="chunk-count"><b>{doc.chunk_count}</b><span>chunks</span></div><button className="icon-button danger-hover" title="Delete document" onClick={() => remove(doc)}><Trash2 size={16}/></button></div>)}</div> : <div className="panel"><Empty icon={Files} title="No documents yet" text="Upload your first file to begin." action="Choose files" onClick={() => fileInput.current?.click()}/></div>}</>}
        {page === "ask" && <><PageHeading eyebrow="KNOWLEDGE ASSISTANT" title="Ask your documents" subtitle="Ask a question in plain language. Answers are grounded in passages retrieved from your library."/><div className="assistant-layout"><section className="panel ask-panel"><div className="assistant-intro"><div className="assistant-mark"><Sparkles size={20}/></div><div><b>DocuMind assistant</b><p>Answers from your uploaded documents</p></div><span className="powered-pill">SOURCE-GROUNDED</span></div><form onSubmit={ask}><label className="field-label">YOUR QUESTION</label><textarea className="question-box" value={question} onChange={e => setQuestion(e.target.value)} placeholder="What are the main findings in the uploaded reports?..." rows={5}/><div className="ask-options"><div><label className="field-label">SEARCH WITHIN</label><select multiple value={selectedDocs} onChange={e => setSelectedDocs([...e.target.selectedOptions].map(x => x.value))} className="doc-select">{documents.map(d=><option key={d.id} value={d.name}>{d.name}</option>)}</select><small>Leave empty to search all documents. Use Ctrl/Cmd to select multiple.</small></div><div><label className="field-label">NUMBER OF SOURCES</label><select value={top} onChange={e => setTop(Number(e.target.value))}><option value={3}>3 passages</option><option value={5}>5 passages</option><option value={8}>8 passages</option><option value={10}>10 passages</option></select></div></div><button className="primary-button wide-button" disabled={busy || !question.trim()}>{busy ? <LoaderCircle className="spin" size={16}/> : <Sparkles size={16}/>} Find an answer</button></form></section><div className="answer-column">{answer ? <section className="panel answer-panel"><div className="panel-heading"><div><h2>Answer</h2><p>{answer.answer_model} · {answer.retrieval}</p></div><button className="icon-button" title="Copy answer" onClick={() => navigator.clipboard.writeText(answer.answer)}><ArrowDownToLine size={16}/></button></div><div className="answer-text">{answer.answer}</div><div className="source-heading"><b>Retrieved sources</b><span>{answer.sources.length} passages</span></div>{answer.sources.map((s,i)=><div className="source-card" key={i}><div className="source-top"><span className="source-index">SOURCE {String(i+1).padStart(2,"0")}</span><b>{s.document_name}</b><span className="source-score">{Number(s.score).toFixed(2)}</span></div><p>{s.text}</p><small>Chunk {s.chunk_index+1}</small></div>)}</section> : <div className="empty-answer"><div className="empty-answer-icon"><MessageSquareText size={25}/></div><h3>Your answer will appear here</h3><p>Ask a question to retrieve relevant information and inspect the original source passages.</p><div className="suggestion" onClick={() => setQuestion("Summarize the key points from my uploaded documents.")}><Sparkles size={14}/> Summarize the key points from my documents <ArrowUpRight size={13}/></div></div>}</div></div></>}
        {page === "extract" && <><PageHeading eyebrow="DOCUMENT INTELLIGENCE" title="Structured extraction" subtitle="Extract useful fields from a document with Azure Document Intelligence or the local pattern-based fallback."/><div className="two-column"><section className="panel form-panel"><div className="panel-heading"><div><h2>Extraction setup</h2><p>Choose a document and the fields to extract</p></div><div className="panel-icon"><FileText size={17}/></div></div><form onSubmit={extract}><label className="field-label">DOCUMENT</label><select required value={extractId} onChange={e => setExtractId(e.target.value)}>{documents.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select><label className="field-label field-spaced">FIELDS TO EXTRACT</label><textarea rows={4} value={fields} onChange={e => setFields(e.target.value)} className="question-box"/><small className="field-help">Separate field names with commas. Default fields are optimized for invoices.</small><button className="primary-button wide-button" disabled={busy || !documents.length}>{busy ? <LoaderCircle className="spin" size={16}/> : <Sparkles size={16}/>} Extract fields</button></form></section><section className="panel result-panel"><div className="panel-heading"><div><h2>Extraction results</h2><p>Structured values and confidence scores</p></div></div>{extraction ? <><div className="method-banner"><Check size={15}/>{extraction.method}</div>{extraction.warning && <p className="warning-text">{extraction.warning}</p>}<div className="result-table">{Object.entries(extraction.fields).map(([key,value])=><div className="result-row" key={key}><span>{key}</span><b>{String(value.value || "Not found")}</b><small>{Math.round((value.confidence || 0)*100)}%</small></div>)}</div><button className="secondary-button" onClick={() => download(JSON.stringify(extraction.fields,null,2),"documind-extraction.json","application/json")}><ArrowDownToLine size={15}/> Download JSON</button></> : <Empty icon={FileText} title="No results yet" text="Run an extraction to see the detected fields here."/>}</section></div></>}
        {page === "safety" && <><PageHeading eyebrow="RESPONSIBLE AI" title="Content safety" subtitle="Analyze submitted text with Azure AI Content Safety when configured. The local fallback is a basic keyword screen."/><div className="two-column"><section className="panel form-panel"><div className="panel-heading"><div><h2>Text analysis</h2><p>Submit text for a safety check</p></div><div className="panel-icon"><ShieldCheck size={17}/></div></div><form onSubmit={moderate}><label className="field-label">TEXT TO ANALYZE</label><textarea className="question-box" rows={9} value={moderationText} onChange={e => setModerationText(e.target.value)} placeholder="Paste the text you want to analyze…"/><button className="primary-button wide-button" disabled={busy || !moderationText.trim()}>{busy ? <LoaderCircle className="spin" size={16}/> : <ShieldCheck size={16}/>} Analyze content</button></form></section><section className="panel result-panel"><div className="panel-heading"><div><h2>Analysis result</h2><p>Moderation categories and status</p></div></div>{moderation ? <><div className={`safety-result ${moderation.blocked ? "flagged" : "clear"}`}><div>{moderation.blocked ? <ShieldCheck size={19}/> : <Check size={19}/>}</div><b>{moderation.blocked ? "Potentially harmful content detected" : "No configured threshold exceeded"}</b><span>{moderation.configured ? "Azure AI Content Safety" : "Local keyword fallback — not an AI classifier"}</span></div>{moderation.error && <p className="warning-text">{moderation.error}</p>}<div className="result-table">{Object.entries(moderation.categories || {}).map(([k,v])=><div className="result-row" key={k}><span>{k}</span><b>{Array.isArray(v) ? v.join(", ") || "None" : v}</b></div>)}</div></> : <Empty icon={ShieldCheck} title="Ready to analyze" text="Your moderation result and category breakdown will appear here."/>}</section></div></>}
        {page === "activity" && <><PageHeading eyebrow="WORKSPACE HISTORY" title="Activity log" subtitle="A chronological record of document processing and analysis activity." action={<button className="secondary-button" onClick={() => download(["Event,Target,Details,Timestamp",...activity.map(x => [x.Event,x.Target,x.Details,x.Timestamp].map(v => JSON.stringify(v ?? "")).join(","))].join("\n"),"documind-activity.csv","text/csv")}><ArrowDownToLine size={15}/> Export CSV</button>}/><section className="panel activity-panel">{activity.length ? activity.map((event,i)=><div className="activity-row" key={i}><div className="activity-icon"><Activity size={16}/></div><div className="activity-copy"><b>{event.Event}</b><span>{event.Target} · {event.Details}</span></div><time>{dateLabel(event.Timestamp)}</time></div>) : <Empty icon={Activity} title="No activity recorded" text="Your document and analysis activity will appear here."/>}</section></>}
        {page === "settings" && <><PageHeading eyebrow="CONFIGURATION" title="Settings & integrations" subtitle="Check connected services and understand where your data is processed."/><div className="settings-banner"><div className="settings-banner-icon"><ShieldCheck size={22}/></div><div><b>Secrets stay on the server</b><p>Azure credentials and service endpoints are loaded from the backend environment. They are never returned to the browser or embedded in the React build.</p></div></div><div className="integration-grid">{[{id:"azure_search",name:"Azure AI Search",desc:"Cloud chunk indexing and keyword retrieval",icon:Search},{id:"document_intelligence",name:"Document Intelligence",desc:"Structured extraction from supported documents",icon:FileText},{id:"content_safety",name:"Azure AI Content Safety",desc:"Text moderation and safety checks",icon:ShieldCheck},{id:"ollama",name:"Ollama",desc:"Optional local LLM answer generation",icon:Sparkles}].map(x=><div className="panel integration-card" key={x.id}><div className="integration-icon"><x.icon size={19}/></div><div className="integration-copy"><b>{x.name}</b><p>{x.desc}</p><span className={settings?.integrations[x.id] ? "connected" : "not-connected"}><i/>{settings?.integrations[x.id] ? "Configured" : "Not configured"}</span></div></div>)}</div><section className="panel config-panel"><div className="panel-heading"><div><h2>Processing configuration</h2><p>Runtime limits reported by the backend</p></div></div><div className="config-grid"><div><span>Maximum upload size</span><b>{settings?.limits.max_upload_mb} MB</b></div><div><span>Chunk size</span><b>{settings?.limits.chunk_size} characters</b></div><div><span>Chunk overlap</span><b>{settings?.limits.chunk_overlap} characters</b></div><div><span>Answer generation</span><b>{settings?.integrations.ollama ? settings.integrations.answer_model : "Extractive"}</b></div></div><p className="privacy-note"><ShieldCheck size={15}/>{settings?.privacy}</p></section><p className="cost-note">Azure services are optional integrations. Verify the pricing tier, region eligibility and remaining free quota in your Azure subscription. DocuMind does not provision or upgrade cloud resources.</p></>}
      </div>
    </main>
  </div>;
}

function Metric({label,value,icon:Icon,note}) { return <div className="metric-card"><div className="metric-top"><span>{label}</span><div><Icon size={17}/></div></div><strong>{Number(value).toLocaleString()}</strong><small>{note}</small></div>; }
function PageHeading({eyebrow,title,subtitle,action}) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>; }
function Empty({icon:Icon,title,text,action,onClick}) { return <div className="empty-state"><div className="empty-icon"><Icon size={21}/></div><b>{title}</b><p>{text}</p>{action && <button className="secondary-button" onClick={onClick}>{action}</button>}</div>; }
export default App;