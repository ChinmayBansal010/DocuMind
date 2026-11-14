import { useEffect, useState } from "react";
import { FolderKanban, MessageSquareText } from "lucide-react";
import { api } from "../../services/api";
import AssistantChat from "./AssistantChat";
import "./AssistantHub.css";

export default function AssistantHub({ onBrowseProjects, setNotice }) {
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api("/projects")
      .then((result) => {
        if (!active) return;
        setProjects(result);
        setProjectId(result.find((project) => project.contract_count > 0)?.id || result[0]?.id || "");
      })
      .catch((error) => {
        if (active) setNotice(error.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [setNotice]);

  const selectedProject = projects.find((project) => project.id === projectId);
  if (loading) return <div className="page-wrap"><div className="skeleton large-skeleton" /></div>;
  if (!projects.length) {
    return (
      <div className="page-wrap">
        <div className="empty-panel assistant-hub-empty">
          <FolderKanban size={25} />
          <h2>Create a project to start a chat</h2>
          <p>Every conversation is scoped to one project, so documents from other projects are never included.</p>
          <button type="button" className="button primary" onClick={onBrowseProjects}>Go to projects</button>
        </div>
      </div>
    );
  }

  return (
    <div className="page-wrap assistant-hub">
      <header className="assistant-hub-header">
        <div><span className="eyebrow">PRIVATE, PROJECT-SCOPED CHAT</span><h1><MessageSquareText size={23} /> Contract assistant</h1><p>Choose a project to search its latest contract versions and continue its saved conversations.</p></div>
        <label className="assistant-project-picker">
          <span>Search within project</span>
          <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            {projects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}
          </select>
        </label>
      </header>
      {selectedProject ? (
        <div className="assistant-hub-panel" key={selectedProject.id}>
          <div className="assistant-hub-scope"><FolderKanban size={15} /><span>Current scope: <b>{selectedProject.name}</b></span><small>{selectedProject.contract_count} contract{selectedProject.contract_count === 1 ? "" : "s"}</small></div>
          {selectedProject.contract_count > 0
            ? <AssistantChat key={selectedProject.id} projectId={selectedProject.id} setNotice={setNotice} />
            : (
              <div className="empty-panel assistant-hub-empty">
                <MessageSquareText size={25} />
                <h3>No contracts in this project yet</h3>
                <p>Upload contracts to this project, or choose a project that already contains contracts to ask evidence-based questions.</p>
              </div>
            )}
        </div>
      ) : null}
    </div>
  );
}
