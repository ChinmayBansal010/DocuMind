import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUp, BookOpenText, Copy, Download, MoreHorizontal, Pencil,
  Plus, Search, Sparkles, Trash2,
} from "lucide-react";
import { api } from "../../services/api";
import "./AssistantChat.css";

const STARTERS = [
  "Summarize the key responsibilities.",
  "What can end this agreement, and how much notice is required?",
  "What payment dates, amounts, or conditions are stated?",
];

export default function AssistantChat({ projectId, contractId = null, setNotice }) {
  const [conversations, setConversations] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [openMenuId, setOpenMenuId] = useState(null);
  const composerRef = useRef(null);
  const endOfMessagesRef = useRef(null);
  const scopeIdentity = `${projectId}:${contractId || "project"}`;
  const scopeRef = useRef(scopeIdentity);
  const scopeQuery = contractId ? `?contract_id=${encodeURIComponent(contractId)}` : "";
  const listUrl = `/projects/${projectId}/conversations${scopeQuery}`;

  const loadConversations = useCallback(async (preferredId = null, expectedScope = scopeIdentity) => {
    try {
      const result = await api(listUrl);
      if (scopeRef.current !== expectedScope) return;
      const selected = result.find((item) => item.id === preferredId) || result[0] || null;
      setConversations(result);
      setActiveId(selected?.id || null);
      setMessages(selected?.messages || []);
    } catch (error) {
      if (scopeRef.current === expectedScope) setNotice(error.message);
    } finally {
      if (scopeRef.current === expectedScope) setLoading(false);
    }
  }, [listUrl, scopeIdentity, setNotice]);

  useEffect(() => {
    scopeRef.current = scopeIdentity;
    setLoading(true);
    setConversations([]);
    setActiveId(null);
    setMessages([]);
    setQuestion("");
    setSearch("");
    loadConversations(null, scopeIdentity);
  }, [loadConversations, scopeIdentity]);
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView?.({ behavior: busy ? "smooth" : "auto" });
  }, [busy, messages, pendingQuestion]);

  const activeConversation = conversations.find((item) => item.id === activeId) || null;
  const visibleConversations = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return conversations;
    return conversations.filter((item) => (
      item.title.toLowerCase().includes(query)
      || item.messages.some((message) => message.content.toLowerCase().includes(query))
    ));
  }, [conversations, search]);

  const startNewConversation = () => {
    setActiveId(null);
    setMessages([]);
    setQuestion("");
    setOpenMenuId(null);
    composerRef.current?.focus();
  };

  const submitQuestion = async (event) => {
    event.preventDefault();
    const currentQuestion = question.trim();
    if (!currentQuestion || busy) return;
    setBusy(true);
    setPendingQuestion(currentQuestion);
    try {
      const endpoint = contractId
        ? `/contracts/${contractId}/ask`
        : `/projects/${projectId}/assistant/ask`;
      const result = await api(endpoint, {
        method: "POST",
        body: JSON.stringify({
          question: currentQuestion,
          conversation_id: activeId,
        }),
      });
      setQuestion("");
      setPendingQuestion("");
      await loadConversations(result.conversation_id);
    } catch (error) {
      setNotice(error.message);
    } finally {
      setBusy(false);
      setPendingQuestion("");
    }
  };

  const renameConversation = async (conversation) => {
    const title = window.prompt("Conversation name", conversation.title);
    if (!title?.trim()) return;
    try {
      await api(
        `/projects/${projectId}/conversations/${conversation.id}${scopeQuery}`,
        { method: "PATCH", body: JSON.stringify({ title: title.trim() }) },
      );
      setOpenMenuId(null);
      await loadConversations(conversation.id);
    } catch (error) {
      setNotice(error.message);
    }
  };

  const deleteConversation = async (conversation) => {
    if (!window.confirm(`Delete "${conversation.title}" and its messages?`)) return;
    try {
      await api(
        `/projects/${projectId}/conversations/${conversation.id}${scopeQuery}`,
        { method: "DELETE" },
      );
      setOpenMenuId(null);
      await loadConversations(null);
    } catch (error) {
      setNotice(error.message);
    }
  };

  const copyAnswer = async (content) => {
    try {
      await navigator.clipboard.writeText(stripSourceMarkers(content));
      setNotice("Answer copied.");
    } catch (error) {
      setNotice(`Could not copy the answer: ${error.message}`);
    }
  };

  const exportConversation = () => {
    if (!messages.length) return;
    const lines = [
      `# ${activeConversation?.title || "Contract conversation"}`,
      "",
      ...messages.flatMap((message) => {
        const role = message.role === "user" ? "You" : "DocuMind";
        const section = [`## ${role}`, "", stripSourceMarkers(message.content), ""];
        if (message.role === "assistant" && message.citations?.length) {
          section.push("### Supporting evidence");
          for (const citation of message.citations) {
            section.push(
              `- ${citation.document}${citation.page ? `, page ${citation.page}` : ""}: ${citation.excerpt}`,
            );
          }
          section.push("");
        }
        return section;
      }),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${safeFilename(activeConversation?.title || "contract-chat")}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const conversationLabel = contractId ? "This contract" : "This project";
  return (
    <section className="assistant-chat" aria-label={`${conversationLabel} assistant`}>
      <aside className="assistant-history">
        <div className="assistant-history-heading">
          <div><span className="eyebrow">SAVED CHATS</span><h2>Conversations</h2></div>
          <button type="button" className="assistant-new-chat" onClick={startNewConversation} aria-label="Start new conversation">
            <Plus size={16} />
          </button>
        </div>
        <label className="assistant-search">
          <Search size={15} />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search conversations"
            aria-label="Search conversations"
          />
        </label>
        <div className="assistant-thread-list" role="list" aria-label="Saved conversations">
          {loading ? <div className="assistant-history-loading">Loading saved chats…</div>
            : visibleConversations.length ? visibleConversations.map((conversation) => (
              <div className={`assistant-thread ${activeId === conversation.id ? "active" : ""}`} key={conversation.id} role="listitem">
                <button
                  type="button"
                  className="assistant-thread-select"
                  onClick={() => {
                    setActiveId(conversation.id);
                    setMessages(conversation.messages);
                    setOpenMenuId(null);
                  }}
                  aria-current={activeId === conversation.id ? "true" : undefined}
                >
                  <b>{conversation.title}</b>
                  <small>{conversation.messages.length} messages · {formatDate(conversation.created_at)}</small>
                </button>
                <div className="assistant-thread-actions">
                  <button
                    type="button"
                    className="assistant-menu-trigger"
                    aria-label={`Conversation actions: ${conversation.title}`}
                    aria-expanded={openMenuId === conversation.id}
                    onClick={() => setOpenMenuId(openMenuId === conversation.id ? null : conversation.id)}
                  ><MoreHorizontal size={16} /></button>
                  {openMenuId === conversation.id && (
                    <div className="assistant-thread-menu">
                      <button type="button" onClick={() => renameConversation(conversation)}><Pencil size={14} />Rename</button>
                      <button type="button" onClick={() => deleteConversation(conversation)}><Trash2 size={14} />Delete chat</button>
                    </div>
                  )}
                </div>
              </div>
            )) : <p className="assistant-no-threads">{search ? "No saved conversations match." : "Your questions will be saved here."}</p>}
        </div>
      </aside>

      <div className="assistant-chat-main">
        <header className="assistant-chat-header">
          <div>
            <span className="eyebrow">{contractId ? "CONTRACT ASSISTANT" : "PROJECT ASSISTANT"}</span>
            <h2>{activeConversation?.title || "Ask about your agreements"}</h2>
            <p>{contractId ? "Answers use only this contract’s indexed versions." : "Answers search only the latest versions in this project."} Evidence stays tucked away unless you open it.</p>
          </div>
          <button
            type="button"
            className="assistant-export"
            onClick={exportConversation}
            disabled={!messages.length}
            title="Download this conversation as Markdown"
          ><Download size={15} /><span>Export</span></button>
        </header>

        <div className="assistant-message-list" aria-live="polite">
          {messages.length ? messages.map((message) => (
            <ChatMessage key={message.id} message={message} onCopy={copyAnswer} />
          )) : (
            <div className="assistant-welcome">
              <span className="assistant-welcome-icon"><Sparkles size={20} /></span>
              <h3>Start with a question</h3>
              <p>Ask a follow-up at any time. Each conversation is saved to {contractId ? "this contract" : "this project"}.</p>
              <div className="assistant-starters">
                {STARTERS.map((starter) => (
                  <button type="button" key={starter} disabled={busy} onClick={() => { setQuestion(starter); composerRef.current?.focus(); }}>
                    {starter}<ArrowUp size={14} />
                  </button>
                ))}
              </div>
            </div>
          )}
          {pendingQuestion && <div className="assistant-message user"><span>You</span><p>{pendingQuestion}</p></div>}
          {busy && <div className="assistant-working" role="status"><span className="assistant-dots" /> Searching the selected contract material…</div>}
          <div ref={endOfMessagesRef} />
        </div>

        <form className="assistant-composer" onSubmit={submitQuestion}>
          <textarea
            ref={composerRef}
            rows="2"
            maxLength={10000}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={`Ask a question about ${contractId ? "this contract" : "this project"}…`}
            aria-label="Ask DocuMind"
          />
          <div className="assistant-composer-footer">
            <span>Source-grounded · {contractId ? "Contract" : "Project"} scope · Enter to send</span>
            <button type="submit" className="assistant-send" disabled={busy || !question.trim()} aria-label="Send question">
              <ArrowUp size={17} />{busy ? "Searching" : "Send"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

function ChatMessage({ message, onCopy }) {
  const isAssistant = message.role === "assistant";
  const citations = message.citations || [];
  return (
    <article className={`assistant-message ${isAssistant ? "bot" : "user"}`}>
      <div className="assistant-message-heading">
        <span>{isAssistant ? "DocuMind" : "You"}</span>
        {isAssistant && (
          <button type="button" className="assistant-copy" onClick={() => onCopy(message.content)} aria-label="Copy answer">
            <Copy size={14} />Copy
          </button>
        )}
      </div>
      <p>{isAssistant ? stripSourceMarkers(message.content) : message.content}</p>
      {isAssistant && citations.length > 0 ? (
        <details className="assistant-evidence">
          <summary><BookOpenText size={14} />Show supporting evidence ({citations.length})</summary>
          <div className="assistant-evidence-list">
            {citations.map((citation, index) => (
              <article className="assistant-evidence-item" key={citation.chunk_id || `${citation.document}-${index}`}>
                <b>{citation.document || "Contract"}{citation.page ? ` · page ${citation.page}` : ""}</b>
                <p>{citation.excerpt}</p>
              </article>
            ))}
          </div>
        </details>
      ) : null}
    </article>
  );
}

function stripSourceMarkers(text) {
  return text.replace(/\s*\[S\d+\]/g, "").replace(/\n{3,}/g, "\n\n").trim();
}

function safeFilename(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "contract-chat";
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString();
}
