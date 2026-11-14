import { useEffect, useState } from "react";
import {
  FileCheck2, FileText, FolderKanban, LogOut, MessageSquareText, Settings2,
} from "lucide-react";
import AuthScreen from "../features/auth/AuthScreen";
import AssistantHub from "../features/assistant/AssistantHub";
import ContractsHub from "../features/contracts/ContractsHub";
import Dashboard from "../features/dashboard/Dashboard";
import ProjectWorkspace from "../features/projects/ProjectWorkspace";
import ContractWorkspace from "../features/contracts/ContractWorkspace";
import SettingsPage from "../features/settings/SettingsPage";
import { authClient } from "../services/auth";
import { api } from "../services/api";
import "./WorkspaceNavigation.css";

export default function Application() {
  const [user, setUser] = useState(undefined);
  const [profile, setProfile] = useState(null);
  const [page, setPage] = useState("projects");
  const [projectId, setProjectId] = useState(null);
  const [contractId, setContractId] = useState(null);
  const [contractReturnPage, setContractReturnPage] = useState("project");
  const [notice, setNotice] = useState("");

  const refreshSession = async () => {
    if (!authClient) { setUser(null); return null; }
    const result = await authClient.getSession();
    if (result.error) throw new Error(result.error.message || "Unable to restore the current session.");
    const sessionUser = result.data?.user || result.data?.session?.user || null;
    if (!sessionUser) {
      setUser(null);
      setProfile(null);
      return null;
    }
    const storedProfile = await api("/profile");
    setProfile({
      ...storedProfile,
      email: sessionUser.email || storedProfile.email,
      name: storedProfile.name || sessionUser.name || "",
    });
    setUser(sessionUser);
    setNotice("");
    return sessionUser;
  };

  useEffect(() => {
    refreshSession().catch((error) => { setNotice(error.message); setUser(null); });
  }, []);
  useEffect(() => {
    const expire = (event) => {
      setUser(null);
      setProfile(null);
      setNotice(event.detail || "Your session is no longer valid. Sign in again to continue.");
    };
    window.addEventListener("documind:session-expired", expire);
    return () => window.removeEventListener("documind:session-expired", expire);
  }, []);

  const openProject = (id) => {
    setProjectId(id);
    setContractId(null);
    setContractReturnPage("project");
    setPage("project");
  };
  const openContractFromCatalog = (nextProjectId, nextContractId) => {
    setProjectId(nextProjectId);
    setContractId(nextContractId);
    setContractReturnPage("contracts");
    setPage("contract");
  };
  const signOut = async () => {
    try {
      const result = await authClient.signOut();
      if (result.error) throw new Error(result.error.message || "Could not sign out.");
      setUser(null);
      setProfile(null);
      setProjectId(null);
      setContractId(null);
      setContractReturnPage("project");
      setPage("projects");
    } catch (error) { setNotice(error.message); }
  };

  if (user === undefined) return <div className="loading-screen"><div className="spinner" /><span>Restoring your secure session…</span></div>;
  if (!user) return <><AuthScreen onAuthenticated={refreshSession} />{notice && <div className="global-toast" role="status">{notice}</div>}</>;

  return <div className="app-shell">
    <aside className="sidebar">
      <button className="brand" onClick={() => { setPage("projects"); setProjectId(null); setContractId(null); }}><span className="brand-mark"><FileCheck2 size={19} /></span><span>DocuMind<small>CONTRACT WORKSPACE</small></span></button>
      <span className="nav-caption">WORKSPACE</span>
      <nav className="workspace-nav" aria-label="Workspace">
        <button className={`side-link ${["projects", "project"].includes(page) || (page === "contract" && contractReturnPage === "project") ? "active" : ""}`} onClick={() => { setPage("projects"); setProjectId(null); setContractId(null); }}><FolderKanban size={17} /> Projects</button>
        <button className={`side-link ${page === "contracts" || (page === "contract" && contractReturnPage === "contracts") ? "active" : ""}`} onClick={() => { setPage("contracts"); setContractId(null); }}><FileText size={17} /> Contracts</button>
        <button className={`side-link ${page === "assistant" ? "active" : ""}`} onClick={() => { setPage("assistant"); setContractId(null); }}><MessageSquareText size={17} /> Assistant</button>
      </nav>
      <div className="sidebar-bottom">
        <button className={`side-link ${page === "settings" ? "active" : ""}`} onClick={() => { setPage("settings"); setContractId(null); }}><Settings2 size={17} /> Settings</button>
        <div className="user-chip"><span className="avatar">{(profile?.name || profile?.email || "U").slice(0, 1).toUpperCase()}</span><div><b>{profile?.name || profile?.email || "User"}</b><small>{profile?.email || ""}</small></div><button title="Sign out" aria-label="Sign out" onClick={signOut}><LogOut size={15} /></button></div>
      </div>
    </aside>
    <main className="main-area">
      {page === "projects" && <Dashboard onOpenProject={openProject} notice={notice} setNotice={setNotice} />}
      {page === "project" && projectId && <ProjectWorkspace projectId={projectId} onBack={() => { setPage("projects"); setProjectId(null); }} onOpenContract={(id) => { setContractId(id); setContractReturnPage("project"); setPage("contract"); }} setNotice={setNotice} />}
      {page === "contracts" && <ContractsHub onOpenContract={openContractFromCatalog} onBrowseProjects={() => { setPage("projects"); setProjectId(null); }} setNotice={setNotice} />}
      {page === "assistant" && <AssistantHub onBrowseProjects={() => { setPage("projects"); setProjectId(null); }} setNotice={setNotice} />}
      {page === "contract" && contractId && <ContractWorkspace contractId={contractId} onBack={() => setPage(contractReturnPage)} setNotice={setNotice} />}
      {page === "settings" && <SettingsPage profile={profile} onProfile={setProfile} onSignOut={signOut} setNotice={setNotice} />}
      {notice && <div className="global-toast" role="status">{notice}<button onClick={() => setNotice("")}>Dismiss</button></div>}
    </main>
  </div>;
}
