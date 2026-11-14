import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft, FilePlus2, FileText, MessageSquareText, MoreHorizontal,
  Pencil, Plus, Search, Trash2, UploadCloud,
} from "lucide-react";
import { api } from "../../services/api";
import AssistantChat from "../assistant/AssistantChat";
import "./ProjectWorkspace.css";

export default function ProjectWorkspace({ projectId, onBack, onOpenContract, setNotice }) {
  const [project, setProject] = useState(null);
  const [contracts, setContracts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const fileInput = useRef(null);
  const versionInput = useRef(null);
  const versionTarget = useRef(null);
  const [openContractMenu, setOpenContractMenu] = useState(null);

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
      if (versionInput.current) versionInput.current.value = "";
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

  const deleteContract = async (contract) => {
    if (!window.confirm(`Delete "${contract.name}" and all its versions?`)) return;
    setBusy(true);
    try {
      await api(`/contracts/${contract.id}`, { method: "DELETE" });
      setOpenContractMenu(null);
      setNotice(`Deleted "${contract.name}".`);
      await load();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
    }
  };

  const visible = contracts.filter((contract) => (
    contract.name.toLowerCase().includes(search.toLowerCase())
    && (statusFilter === "all" || contract.status === statusFilter)
  ));
  const hasOpenVisibleMenu = visible.some((contract) => contract.id === openContractMenu);
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
      <nav className="project-shortcut-nav" aria-label="Project workspace sections">
        <a href="#project-contracts"><FileText size={15} /> Contracts <b>{contracts.length}</b></a>
        <a href="#project-assistant"><MessageSquareText size={15} /> Project assistant</a>
        <button type="button" onClick={rename}><Pencil size={14} /> Project settings</button>
      </nav>
      <section className="section-head" id="project-contracts">
        <div><span className="eyebrow">AGREEMENTS</span><h2>Contracts <span className="count-pill">{contracts.length}</span></h2></div>
        <div className="contract-actions">
          <label className="search-control"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search contracts" /></label>
          <label className="contract-status-filter"><span>Status</span><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="ready">Ready</option><option value="processing">Processing</option><option value="failed">Failed</option></select></label>
          <input ref={fileInput} hidden type="file" multiple accept=".pdf,.docx,.txt" onChange={(event) => upload(event.target.files)} />
          <button className="button primary" onClick={() => fileInput.current?.click()} disabled={busy}><Plus size={16} /> {busy ? "Processing…" : "Upload contracts"}</button>
        </div>
      </section>
      {visible.length ? <div className={`contract-table${hasOpenVisibleMenu ? " has-open-menu" : ""}`}>
        <div className="table-header"><span>NAME</span><span>STATUS</span><span>VERSIONS</span><span>UPDATED</span><span /></div>
        {visible.map((contract) => <div className="table-row" key={contract.id}>
          <button className="contract-name" onClick={() => onOpenContract(contract.id)}><span className="file-mark"><FileText size={17} /></span><span><b>{contract.name}</b><small>{contract.file_type?.toUpperCase() || "CONTRACT"}{contract.page_count ? ` · ${contract.page_count} pages` : ""}</small></span></button>
          <span><i className={`status-dot ${contract.status}`} />{contract.status}</span><span>{contract.version_count}</span>
          <span>{new Date(contract.updated_at).toLocaleDateString()}</span>
          <div
            className="contract-row-actions"
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget)) setOpenContractMenu(null);
            }}
          >
            <button
              type="button"
              className="icon-action"
              aria-label={`Contract actions: ${contract.name}`}
              aria-haspopup="menu"
              aria-expanded={openContractMenu === contract.id}
              onClick={() => setOpenContractMenu(openContractMenu === contract.id ? null : contract.id)}
            ><MoreHorizontal size={18} /></button>
            {openContractMenu === contract.id ? (
              <div className="contract-action-menu" role="menu">
                <button type="button" role="menuitem" onClick={() => { setOpenContractMenu(null); uploadPicker(contract.id); }}>
                  <FilePlus2 size={15} /> Upload new version
                </button>
                <button type="button" role="menuitem" disabled={busy} onClick={() => deleteContract(contract)}>
                  <Trash2 size={15} /> Delete contract
                </button>
              </div>
            ) : null}
          </div>
        </div>)}
      </div> : <div className="empty-panel"><UploadCloud size={26} /><h3>{search || statusFilter !== "all" ? "No contracts match these filters" : "No contracts in this project yet"}</h3><p>{search || statusFilter !== "all" ? "Try changing the search or status filter." : "Upload PDF, Word, or text agreements to begin."}</p>{!search && statusFilter === "all" && <button className="button primary" onClick={() => fileInput.current?.click()}><Plus size={16} /> Add contracts</button>}</div>}
      <div id="project-assistant" className="project-assistant-anchor"><AssistantChat projectId={projectId} setNotice={setNotice} /></div>
      <input ref={versionInput} hidden type="file" accept=".pdf,.docx,.txt" onChange={(event) => upload(event.target.files, versionTarget.current)} />
    </div>
  );

  function uploadPicker(contractId) {
    versionTarget.current = contractId;
    versionInput.current?.click();
  }
}
