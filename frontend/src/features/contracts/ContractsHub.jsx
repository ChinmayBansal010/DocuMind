import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, FileText, Search } from "lucide-react";
import { api } from "../../services/api";
import "./ContractsHub.css";

export default function ContractsHub({ onOpenContract, onBrowseProjects, setNotice }) {
  const [contracts, setContracts] = useState([]);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const result = await api(`/contracts?search=${encodeURIComponent(search)}`);
        if (active) setContracts(result);
      } catch (error) {
        if (active) setNotice(error.message);
      } finally {
        if (active) setLoading(false);
      }
    }, search ? 180 : 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [search, setNotice]);

  const visibleContracts = useMemo(
    () => contracts.filter((contract) => status === "all" || contract.status === status),
    [contracts, status],
  );
  const projectCount = new Set(contracts.map((contract) => contract.project_id)).size;
  const attentionCount = contracts.filter((contract) => ["failed", "processing"].includes(contract.status)).length;

  return (
    <div className="page-wrap contracts-hub">
      <header className="hub-heading">
        <div><span className="eyebrow">DOCUMENT LIBRARY</span><h1>All contracts</h1><p>Search agreements across your projects without mixing their assistant context.</p></div>
        <button type="button" className="button secondary" onClick={onBrowseProjects}>Browse projects</button>
      </header>

      <section className="contracts-summary" aria-label="Contract library summary">
        <div><span>Visible contracts</span><b>{contracts.length}</b></div>
        <div><span>Projects</span><b>{projectCount}</b></div>
        <div><span>Processing or failed</span><b>{attentionCount}</b></div>
      </section>

      <section className="contracts-library">
        <div className="contracts-library-toolbar">
          <label className="search-control"><Search size={16} /><input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search contract or project" aria-label="Search contract or project" /></label>
          <label className="contracts-status-filter"><span>Status</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option><option value="ready">Ready</option><option value="processing">Processing</option><option value="failed">Failed</option></select></label>
        </div>
        {loading ? <div className="contracts-catalog-grid">{[1, 2, 3].map((item) => <div className="skeleton project-skeleton" key={item} />)}</div>
          : visibleContracts.length ? (
            <div className="contracts-catalog-grid">
              {visibleContracts.map((contract) => (
                <button
                  type="button"
                  className="contracts-catalog-card"
                  key={contract.id}
                  onClick={() => onOpenContract(contract.project_id, contract.id)}
                >
                  <span className="contracts-catalog-icon"><FileText size={18} /></span>
                  <span className="contracts-catalog-main">
                    <b>{contract.name}</b>
                    <small>{contract.project_name}</small>
                  </span>
                  <span className={`contracts-status-tag ${contract.status}`}>{contract.status}</span>
                  <span className="contracts-catalog-meta">{contract.file_type?.toUpperCase() || "CONTRACT"} · {contract.version_count} version{contract.version_count === 1 ? "" : "s"}{contract.page_count ? ` · ${contract.page_count} pages` : ""}</span>
                  <span className="contracts-catalog-date">Updated {new Date(contract.updated_at).toLocaleDateString()}</span>
                  <ArrowUpRight size={16} className="contracts-catalog-arrow" />
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-panel">
              <FileText size={25} />
              <h3>{search || status !== "all" ? "No contracts match these filters" : "No contracts yet"}</h3>
              <p>{search || status !== "all" ? "Try another search or status." : "Create a project and upload your first agreement."}</p>
              {!contracts.length ? <button type="button" className="button primary" onClick={onBrowseProjects}>Go to projects</button> : null}
            </div>
          )}
      </section>
    </div>
  );
}
