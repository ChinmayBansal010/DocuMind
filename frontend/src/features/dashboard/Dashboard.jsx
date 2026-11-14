import { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, FilePlus2, FolderPlus, Search, ShieldCheck } from "lucide-react";
import { api } from "../../services/api";

export default function Dashboard({ onOpenProject, notice, setNotice }) {
  const [projects, setProjects] = useState([]);
  const [query, setQuery] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (search = "") => {
    setLoading(true);
    try {
      setProjects(await api(`/projects?search=${encodeURIComponent(search)}`));
    } catch (error) {
      setNotice(error.message);
    } finally {
      setLoading(false);
    }
  }, [setNotice]);

  useEffect(() => { load(""); }, [load]);

  const createProject = async (event) => {
    event.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      const project = await api("/projects", { method: "POST", body: JSON.stringify({ name: name.trim(), description: "" }) });
      setName("");
      setProjects((current) => [project, ...current]);
      onOpenProject(project.id);
    } catch (error) {
      setNotice(error.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="page-wrap">
      <section className="welcome-panel">
        <div>
          <span className="eyebrow">YOUR CONTRACT WORKSPACE</span>
          <h1>Make the important details easier to find.</h1>
          <p>Organize agreements by project, review evidence-backed findings, and keep changes and obligations visible.</p>
          <form className="create-project" onSubmit={createProject}>
            <input aria-label="New project name" placeholder="Name a project to get started" value={name} onChange={(event) => setName(event.target.value)} maxLength={200} />
            <button className="button primary" disabled={creating || !name.trim()}><FolderPlus size={16} /> {creating ? "Creating…" : "Create project"}</button>
          </form>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <div className="art-sheet"><span>AGREEMENT REVIEW</span><i /><i /><i /><b>✓</b><i /></div>
          <div className="art-check"><ShieldCheck size={18} /> Source checked</div>
        </div>
      </section>
      <section className="section-head">
        <div><span className="eyebrow">PORTFOLIO</span><h2>Your projects</h2></div>
        <label className="search-control"><Search size={16} /><input placeholder="Search projects" value={query} onChange={(event) => { setQuery(event.target.value); load(event.target.value); }} /></label>
      </section>
      {notice && <div className="error-box" role="alert">{notice}<button onClick={() => setNotice("")}>Dismiss</button></div>}
      {loading ? <div className="project-grid">{[1, 2, 3].map((item) => <div className="skeleton project-skeleton" key={item} />)}</div> :
        projects.length ? <div className="project-grid">{projects.map((project) => (
          <button className="project-card" key={project.id} onClick={() => onOpenProject(project.id)}>
            <div className="project-icon"><FilePlus2 size={20} /></div>
            <span className="project-card-title">{project.name}</span>
            <span className="project-card-description">{project.description || "A private workspace for your agreements."}</span>
            <div className="project-card-meta"><span>{project.contract_count} {project.contract_count === 1 ? "contract" : "contracts"}</span><span>Updated {new Date(project.updated_at).toLocaleDateString()}</span><ArrowUpRight size={16} /></div>
          </button>
        ))}</div> :
        <div className="empty-panel"><FolderPlus size={24} /><h3>{query ? "No matching projects" : "Your first project starts here"}</h3><p>{query ? "Try another search." : "Create a project to upload and organize its contracts."}</p></div>}
    </div>
  );
}
