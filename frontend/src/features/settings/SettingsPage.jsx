import { useEffect, useState } from "react";
import { KeyRound, LogOut, Save, ShieldCheck } from "lucide-react";
import { api } from "../../services/api";

export default function SettingsPage({ profile, onProfile, onSignOut, setNotice }) {
  const [name, setName] = useState(profile?.name || "");
  const [settings, setSettings] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { setName(profile?.name || ""); }, [profile]);
  useEffect(() => { api("/settings").then(setSettings).catch((error) => setNotice(error.message)); }, [setNotice]);

  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const updated = await api("/profile", { method: "PATCH", body: JSON.stringify({ name: name.trim() }) });
      onProfile(updated);
      setNotice("Profile updated.");
    } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  };

  const azureServices = settings?.azure_services || {};
  const serviceLabels = {
    document_intelligence: "Document Intelligence",
    language: "Language",
    translator: "Translator",
    content_safety: "Content Safety",
    search: "AI Search",
  };

  return <div className="page-wrap settings-page">
    <span className="eyebrow">PREFERENCES</span><h1>Settings</h1><p className="subtle-copy">Manage your profile and review how this workspace is configured.</p>
    <section className="surface"><div className="surface-title"><KeyRound size={17} /><h2>Profile</h2></div><form className="settings-form" onSubmit={save}><label>Display name<input value={name} onChange={(event) => setName(event.target.value)} required maxLength={200} /></label><label>Email address<input value={profile?.email || ""} readOnly /></label><button className="button primary" disabled={busy || !name.trim()}><Save size={15} />{busy ? "Saving…" : "Save profile"}</button></form></section>
    <section className="surface"><div className="surface-title"><ShieldCheck size={17} /><h2>Workspace configuration</h2></div>{settings && <><div className="settings-grid"><div><small>Storage database</small><b>Neon PostgreSQL</b></div><div><small>Supported uploads</small><b>{settings.supported_file_types.join(", ").toUpperCase()}</b></div><div><small>Maximum upload</small><b>{settings.upload_limit_mb} MB per file</b></div><div><small>Local document files</small><b>{settings.document_encryption_enabled ? "AES-GCM encryption enabled" : "Application encryption not configured"}</b></div><div><small>Ollama analysis</small><b>{settings.ollama_configured ? "Configured" : "Not configured; rule-based review available"}</b></div><div><small>Ollama embedding model</small><b>{settings.ollama_embedding_model}</b></div></div><h3 className="history-heading">Required Azure AI services</h3><div className="settings-grid azure-service-grid">{Object.entries(serviceLabels).map(([key, label]) => <div key={key}><small>{label}</small><b className={azureServices[key] ? "service-configured" : "service-unavailable"}>{azureServices[key] ? "Configured" : "Not configured"}</b></div>)}</div><p className="subtle-copy">F0 limits are enforced for document pages, Language and Content Safety records, and Translator characters. Azure AI Search Free has a 50 MB index limit. Native document-format translation is not included in F0; translation applies to extracted text.</p></>}<p className="disclaimer">DOCUMENT_ENCRYPTION_KEY protects stored source files only. Extracted text, chunks, metadata, and analysis remain in PostgreSQL and rely on database/provider controls. Configure key management and secure backups before production use.</p></section>
    <section className="surface signout-panel"><div><b>End this session</b><p>Sign out of DocuMind on this browser.</p></div><button className="button danger-ghost" onClick={onSignOut}><LogOut size={15} /> Sign out</button></section>
  </div>;
}
