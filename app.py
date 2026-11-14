import hashlib
import json
import pandas as pd
import streamlit as st

from documind.database import initialize_db, add_document, record_event, get_stats, get_events
from documind.documents import extract_document, split_text
from documind.storage import save_upload, list_documents, delete_document
from documind.search import search_chunks, answer_question
from documind.azure_services import analyze_with_document_intelligence, moderate_text
from documind.config import settings
from documind.extraction import extract_fields_locally

st.set_page_config(page_title="DocuMind AI", page_icon="D", layout="wide")
initialize_db()

st.markdown("""
<style>
.block-container{max-width:1440px;padding-top:1.6rem}
.dm-kicker{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:#77849a;font-weight:700}
.dm-title{font-size:2.15rem;font-weight:760;letter-spacing:-.045em;margin:.1rem 0}
.dm-sub{color:#77849a;font-size:.95rem}
[data-testid=stMetric]{border:1px solid rgba(120,140,160,.22);padding:14px;border-radius:12px}
</style>
""", unsafe_allow_html=True)

def header(section, title, subtitle):
    st.markdown(f'<div class="dm-kicker">{section}</div><div class="dm-title">{title}</div><div class="dm-sub">{subtitle}</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## DocuMind AI")
    st.caption("Intelligent document workspace")
    page = st.radio("WORKSPACE", ["Overview","Documents","Ask documents","Extraction","Responsible AI","Activity","Settings"], label_visibility="collapsed")
    st.divider()
    st.success("Local-first processing")
    st.caption("Azure calls are optional and credential-gated.")

docs = list_documents()

if page == "Overview":
    header("WORKSPACE / OVERVIEW","Your documents, understood.","A local-first document intelligence workspace with optional Azure integrations.")
    st.write("")
    a,b,c,d = st.columns(4)
    stats = get_stats()
    a.metric("Documents",stats["documents"])
    b.metric("Indexed chunks",stats["chunks"])
    c.metric("Questions",stats["queries"])
    d.metric("Azure services","Configured" if settings.azure_configured else "Optional")
    st.write("")
    left,right = st.columns([1.4,1])
    with left:
        st.subheader("Recent documents")
        if docs:
            st.dataframe(pd.DataFrame([{"Document":x["name"],"Type":x["file_type"].upper(),"Pages":x["pages"],"Chunks":x["chunk_count"],"Added":x["created_at"][:16]} for x in docs[:8]]),use_container_width=True,hide_index=True)
        else:
            st.info("Your library is empty. Upload a document to get started.")
    with right:
        st.subheader("Processing pipeline")
        st.markdown("**01 · Ingest** — PDF, DOCX, PPTX, XLSX, CSV and images\n\n**02 · Understand** — text extraction and OCR\n\n**03 · Index** — SQLite and TF-IDF retrieval\n\n**04 · Ask** — grounded answers with source passages\n\n**05 · Protect** — optional Azure Content Safety")
elif page == "Documents":
    header("WORKSPACE / DOCUMENTS","Document library","Upload, process and manage the documents used across the workspace.")
    uploaded = st.file_uploader("Add documents",type=["pdf","docx","txt","md","pptx","xlsx","csv","png","jpg","jpeg","tif","tiff"],accept_multiple_files=True)
    if uploaded and st.button("Process files",type="primary"):
        bar = st.progress(0)
        for i,f in enumerate(uploaded):
            try:
                raw=f.getvalue()
                digest=hashlib.sha256(raw).hexdigest()
                if any(x["sha256"]==digest for x in list_documents()):
                    st.warning(f"{f.name}: already exists.")
                    continue
                path=save_upload(f.name,raw)
                parsed=extract_document(path)
                chunks=split_text(parsed["text"],settings.chunk_size,settings.chunk_overlap)
                add_document(f.name,path,parsed["file_type"],parsed["text"],parsed["pages"],digest,chunks)
                record_event("upload",f.name,f"{len(chunks)} chunks indexed")
                st.success(f"{f.name}: processed.")
            except Exception as e:
                st.error(f"{f.name}: {e}")
            bar.progress((i+1)/len(uploaded))
        st.rerun()
    st.subheader("Stored documents")
    if docs:
        for doc in docs:
            with st.container(border=True):
                x,y,z=st.columns([5,1,1])
                x.markdown(f"**{doc['name']}**")
                x.caption(f"{doc['file_type'].upper()} · {doc['pages']} pages · {doc['created_at'][:16]}")
                y.metric("Chunks",doc["chunk_count"])
                if z.button("Delete",key=f"delete-{doc['id']}"):
                    delete_document(doc["id"])
                    record_event("delete",doc["name"],"Document removed")
                    st.rerun()
    else:
        st.info("No documents uploaded.")
elif page == "Ask documents":
    header("WORKSPACE / KNOWLEDGE ASSISTANT","Ask your documents","Retrieve relevant passages and receive answers grounded in your uploaded material.")
    if not docs:
        st.info("Upload documents before asking questions.")
    else:
        selected=st.multiselect("Restrict to documents (optional)",[x["name"] for x in docs])
        question=st.text_area("Question",placeholder="What are the key points in these documents?",height=100)
        top=st.selectbox("Number of sources",[3,5,8],index=1)
        if st.button("Search and answer",type="primary",disabled=not question.strip()):
            safety=moderate_text(question)
            if safety.get("blocked"):
                st.error("The configured safety check flagged this query.")
            else:
                hits=search_chunks(question,selected or None,top)
                answer=answer_question(question,hits)
                record_event("query","Knowledge Assistant",question[:240])
                st.subheader("Answer")
                st.write(answer)
                st.subheader("Retrieved sources")
                for i,h in enumerate(hits,1):
                    with st.expander(f"{i}. {h['document_name']} · score {h['score']:.3f}"):
                        st.write(h["text"])
                        st.caption(f"Chunk {h['chunk_index']+1}")
                if not hits: st.warning("No relevant passages found.")
elif page == "Extraction":
    header("WORKSPACE / EXTRACTION","Structured field extraction","Use Azure Document Intelligence when configured; otherwise use the local demonstration extractor.")
    if not docs:
        st.info("Upload a document first.")
    else:
        selected=st.selectbox("Document",[x["name"] for x in docs])
        doc=next(x for x in docs if x["name"]==selected)
        requested=st.text_input("Fields (comma-separated)","InvoiceNumber, InvoiceDate, CustomerName, TaxAmount, TotalAmount")
        if st.button("Extract fields",type="primary"):
            result=analyze_with_document_intelligence(doc["path"])
            if result.get("fields"):
                fields=result["fields"]
                method="Azure Document Intelligence"
            else:
                fields=extract_fields_locally(doc["text"],[x.strip() for x in requested.split(",") if x.strip()])
                method="Local pattern-based extraction"
                if result.get("error"): st.warning(result["error"])
            record_event("extraction",selected,method)
            st.caption(f"Method: {method}")
            st.dataframe(pd.DataFrame([{"Field":k,"Value":v.get("value",""),"Confidence":v.get("confidence",0),"Source":v.get("source","")} for k,v in fields.items()]),use_container_width=True,hide_index=True)
            st.download_button("Download JSON",json.dumps(fields,indent=2,ensure_ascii=False),"extraction.json","application/json")
elif page == "Responsible AI":
    header("WORKSPACE / RESPONSIBLE AI","Content safety","Azure AI Content Safety is optional. The offline keyword fallback is only a demonstration, not a safety classifier.")
    text=st.text_area("Text to analyze",height=180)
    if st.button("Analyze",type="primary",disabled=not text.strip()):
        result=moderate_text(text)
        record_event("moderation","Content Safety",f"{len(text)} characters analyzed")
        if result.get("configured"):
            st.json(result.get("categories",{}))
            st.error("Potentially harmful content detected.") if result.get("blocked") else st.success("No category exceeded the configured threshold.")
            if result.get("error"): st.warning(result["error"])
        else:
            st.warning("Azure is not configured; this is a basic local keyword screen only.")
            st.json(result.get("categories",{}))
            st.write("Flagged" if result.get("blocked") else "No configured keyword match")
elif page == "Activity":
    header("WORKSPACE / AUDIT","Activity log","Recent document operations and analysis events.")
    events=get_events(250)
    if events:
        frame=pd.DataFrame(events)
        st.dataframe(frame,use_container_width=True,hide_index=True)
        st.download_button("Export CSV",frame.to_csv(index=False),"documind_activity.csv","text/csv")
    else: st.info("No activity yet.")
else:
    header("WORKSPACE / CONFIGURATION","Settings and integrations","Optional Azure services are only called when endpoints and credentials are configured.")
    checks=[
        ("Azure AI Document Intelligence",bool(settings.document_intelligence_endpoint and settings.document_intelligence_key)),
        ("Azure AI Content Safety",bool(settings.content_safety_endpoint and settings.content_safety_key)),
        ("Azure AI Search helper",bool(settings.search_endpoint and settings.search_key)),
        ("Ollama",bool(settings.ollama_model))
    ]
    for name,enabled in checks: st.write(("🟢 " if enabled else "⚪ ")+name+(" · configured" if enabled else " · not configured"))
    st.subheader("Strict cost policy")
    st.markdown("- No Azure resources are provisioned by the application.\n- Local disk, SQLite and TF-IDF are the defaults.\n- No Azure OpenAI or paid model endpoint is required.\n- Blob Storage is intentionally not enabled by default.\n- Free-tier availability and quotas must be verified in the Azure portal.")
    st.subheader("Configuration")
    st.code("cp .env.example .env   # Fedora\nCopy-Item .env.example .env   # Windows PowerShell",language="powershell")
