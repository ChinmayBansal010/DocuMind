import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, FileText, MessageSquareText, MoreHorizontal, Pencil, Plus, Search, Trash2, UploadCloud } from "lucide-react";
import { api } from "../../services/api";

export default function ProjectWorkspace({ projectId, onBack, onOpenContract, setNotice }) {
  const [project, setProject] = useState(null);
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const fileInput = useRef(null);
  const [question, setQuestion] = useState("");
  const [projectAnswer, setProjectAnswer] = useState(null);
  const [conversationId, setConversationId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api(`/projects/${projectId}`);
      setProject(result);
      setContracts(result.contracts);
    } catch (error) {
      setNotice(error.message);
    } finally {
      setLoading(false);
    }
  }, [projectId, setNotice]);
  useEffect(() => { load(); }, [load]);

  const upload = async (files, contractId) => {
    if (!files?.length) return;
    setBusy(true);
    const form = new FormData();
    Array.from(files).forEach((file) => form.append("files", file));
    if (contractId) form.append("contract_id", contractId);
    try {
      const result = await api(`/projects/${projectId}/contracts`, { method: "POST", body: form });
      const failed = result.results.filter((item) => item.status === "error");
      setNotice(failed.length ? failed.map((item) => `${item.name}: ${item.message}`).join(" · ") : "Upload and text extraction completed.");
      await load();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const rename = async () => {
    const name = window.prompt("Project name", project?.name || "");
    if (!name?.trim()) return;
    try {
      await api(`/projects/${projectId}`, { method: "PATCH", body: JSON.stringify({ name: name.trim(), description: project.description || "" }) });
      await load();
    } catch (error) { setNotice(error.message); }
  };

  const remove = async () => {
    if (!window.confirm(`Delete “${project?.name}” and all its contracts?`)) return;
    try {
      await api(`/projects/${projectId}`, { method: "DELETE" });
      onBack();
    } catch (error) { setNotice(error.message); }
  };

  const askProject = async (event) => {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true);
    setProjectAnswer(null);
    try {
      const result = await api(`/projects/${projectId}/assistant/ask`, {
        method: "POST",
        body: JSON.stringify({ question: question.trim(), conversation_id: conversationId }),
      });
      setConversationId(result.conversation_id);
      setProjectAnswer(result);
      setQuestion("");
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const visible = contracts.filter((contract) => contract.name.toLowerCase().includes(search.toLowerCase()));
  if (loading) return <div className="page-wrap"><div className="skeleton large-skeleton" /></div>;
  if (!project) return null;
  return (
    <div className="page-wrap">
      <button className="back-button" onClick={onBack}><ArrowLeft size={16} /> All projects</button>
      <section className="project-heading">
        <div><span className="eyebrow">PROJECT WORKSPACE</span><h1>{project.name}</h1><p>{project.description || "Contracts and analysis in one place."}</p></div>
        <div className="heading-actions">
          <button className="button secondary" onClick={rename}><Pencil size={15} /> Rename</button>
          <button className="button danger-ghost" onClick={remove}><Trash2 size={15} /> Delete</button>
        </div>
      </section>
      <section className="section-head">
        <div><span className="eyebrow">AGREEMENTS</span><h2>Contracts <span className="count-pill">{contracts.length}</span></h2></div>
        <div className="contract-actions">
          <label className="search-control"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search contracts" /></label>
          <input ref={fileInput} hidden type="file" multiple accept=".pdf,.docx,.txt" onChange={(event) => upload(event.target.files)} />
          <button className="button primary" onClick={() => fileInput.current?.click()} disabled={busy}><Plus size={16} /> {busy ? "Processing…" : "Upload contracts"}</button>
        </div>
      </section>
      {visible.length ? <div className="contract-table">
        <div className="table-header"><span>NAME</span><span>STATUS</span><span>VERSIONS</span><span>UPDATED</span><span /></div>
        {visible.map((contract) => <div className="table-row" key={contract.id}>
          <button className="contract-name" onClick={() => onOpenContract(contract.id)}><span className="file-mark"><FileText size={17} /></span><span><b>{contract.name}</b><small>{contract.file_type?.toUpperCase() || "CONTRACT"}{contract.page_count ? ` · ${contract.page_count} pages` : ""}</small></span></button>
          <span><i className={`status-dot ${contract.status}`} />{contract.status}</span><span>{contract.version_count}</span>
          <span>{new Date(contract.updated_at).toLocaleDateString()}</span>
          <button className="icon-action" aria-label="Add version" title="Upload new version" onClick={() => uploadPicker(contract.id)}><MoreHorizontal size={17} /></button>
        </div>)}
      </div> : <div className="empty-panel"><UploadCloud size={26} /><h3>{search ? "No contracts match" : "No contracts in this project yet"}</h3><p>{search ? "Try another name." : "Upload PDF, Word, or text agreements to begin."}</p>{!search && <button className="button primary" onClick={() => fileInput.current?.click()}><Plus size={16} /> Add contracts</button>}</div>}
      <section className="surface project-assistant"><span className="eyebrow">PROJECT-WIDE RETRIEVAL</span><h2><MessageSquareText size={17} /> Ask across this project</h2><p>Searches the latest uploaded version of each contract in this project and returns page-level citations.</p><form className="ask-form" onSubmit={askProject}><textarea rows="2" maxLength="12000" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question across this project's agreements" /><button className="button primary" disabled={busy || !question.trim()}>{busy ? "Searching…" : "Ask project"}</button></form>{projectAnswer && <div className="assistant-result"><b>Answer</b><p>{projectAnswer.answer}</p>{projectAnswer.citations.map((citation) => <article className="citation" key={citation.chunk_id}><b>[S{citation.source_number}] {citation.document} · {citation.page ? `page ${citation.page}` : "page unavailable"}</b><p>{citation.excerpt}</p></article>)}</div>}</section>
      <input id="version-upload" hidden type="file" accept=".pdf,.docx,.txt" onChange={(event) => upload(event.target.files, event.target.dataset.contractId)} />
    </div>
  );

  function uploadPicker(contractId) {
    const input = document.getElementById("version-upload");
    input.dataset.contractId = contractId;
    input.click();
  }
}
