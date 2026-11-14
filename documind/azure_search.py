import requests
from documind.config import settings

def _headers():
    if not (settings.search_endpoint and settings.search_key):
        raise RuntimeError("Azure AI Search is not configured.")
    return {"Content-Type":"application/json","api-key":settings.search_key}

def create_index(vector_dimensions=384):
    url = f"{settings.search_endpoint}/indexes/{settings.search_index}"
    body = {"name":settings.search_index,"fields":[
        {"name":"id","type":"Edm.String","key":True,"filterable":True},
        {"name":"document_name","type":"Edm.String","searchable":True,"filterable":True},
        {"name":"chunk_index","type":"Edm.Int32","filterable":True,"sortable":True},
        {"name":"content","type":"Edm.String","searchable":True},
        {"name":"contentVector","type":"Collection(Edm.Single)","searchable":True,"dimensions":vector_dimensions,"vectorSearchProfile":"default-profile"}],
        "vectorSearch":{"algorithms":[{"name":"hnsw-config","kind":"hnsw"}],"profiles":[{"name":"default-profile","algorithm":"hnsw-config"}]}}
    r = requests.put(url,params={"api-version":settings.search_api_version},headers=_headers(),json=body,timeout=30)
    r.raise_for_status()
    return r.json()

def upload_chunks(chunks):
    docs = [{"@search.action":"mergeOrUpload","id":str(x["id"]),"document_name":x["document_name"],
             "chunk_index":x["chunk_index"],"content":x["text"],"contentVector":x["vector"]} for x in chunks]
    r = requests.post(f"{settings.search_endpoint}/indexes/{settings.search_index}/docs/index",
        params={"api-version":settings.search_api_version},headers=_headers(),json={"value":docs},timeout=45)
    r.raise_for_status()
    return r.json()

def vector_search(query_vector, top=5):
    r = requests.post(f"{settings.search_endpoint}/indexes/{settings.search_index}/docs/search",
        params={"api-version":settings.search_api_version},headers=_headers(),
        json={"vectorQueries":[{"kind":"vector","vector":query_vector,"fields":"contentVector","k":top}],
              "select":"id,document_name,chunk_index,content"},timeout=30)
    r.raise_for_status()
    return r.json().get("value",[])
