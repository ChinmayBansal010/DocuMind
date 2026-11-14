import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from documind.database import get_all_chunks
from documind.config import settings

def search_chunks(query, document_names=None, top_k=5):
    rows = get_all_chunks(document_names)
    if not rows: return []
    texts = [r["text"] for r in rows]
    try:
        vectorizer = TfidfVectorizer(ngram_range=(1,2), stop_words="english", max_features=30000, sublinear_tf=True)
        matrix = vectorizer.fit_transform(texts + [query])
        scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    except ValueError:
        scores = np.zeros(len(rows))
    order = np.argsort(scores)[::-1][:top_k]
    return [{"document_name": rows[i]["document_name"], "chunk_index": rows[i]["chunk_index"], "text": rows[i]["text"], "score": float(scores[i])} for i in order if scores[i] > 0]

def answer_question(question, hits):
    if not hits:
        return "I could not find relevant information in the uploaded documents. Try rephrasing the question or adding a relevant document."
    context = "\n\n".join(f"[{i+1}] {h['document_name']}: {h['text']}" for i,h in enumerate(hits[:5]))
    if settings.ollama_model:
        try:
            import requests
            prompt = "Answer only from the supplied context. If absent, say so. Cite sources as [1], [2].\n\nCONTEXT:\n" + context + "\n\nQUESTION: " + question
            response = requests.post(settings.ollama_url.rstrip("/") + "/api/generate", json={"model":settings.ollama_model,"prompt":prompt,"stream":False}, timeout=(5, 240))
            response.raise_for_status()
            generated = response.json().get("response", "").strip()
            if not generated:
                raise RuntimeError("Ollama returned an empty response.")
            return generated
        except Exception as exc:
            return f"Ollama unavailable at {settings.ollama_url} for model {settings.ollama_model}: {exc}. Retrieved passages are shown below instead.\n\n" + "\n\n".join(h["text"] for h in hits[:3])
    return "Extractive result from the most relevant passage (not LLM-generated):\n\n" + hits[0]["text"] + "\n\nSources: " + ", ".join(dict.fromkeys(h["document_name"] for h in hits[:5]))
