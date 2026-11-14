import requests
from documind.config import settings


def is_configured():
    return bool(settings.search_endpoint and settings.search_key and settings.search_index)


def _headers():
    if not is_configured():
        raise RuntimeError("Azure AI Search endpoint, admin key and index are required.")
    return {"Content-Type": "application/json", "api-key": settings.search_key}


def create_index():
    url = f"{settings.search_endpoint}/indexes/{settings.search_index}"
    payload = {
        "name": settings.search_index,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True},
            {"name": "document_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "document_sha256", "type": "Edm.String", "filterable": True},
            {"name": "chunk_index", "type": "Edm.Int32", "filterable": True, "sortable": True},
            {"name": "content", "type": "Edm.String", "searchable": True}
        ]
    }
    response = requests.put(url, params={"api-version": settings.search_api_version}, headers=_headers(), json=payload, timeout=30)
    if response.status_code == 409:
        return {"status": "exists"}
    response.raise_for_status()
    return response.json()


def upload_chunks(document_name, document_sha256, chunks):
    create_index()
    documents = [{
        "@search.action": "mergeOrUpload",
        "id": f"{document_sha256}-{index}",
        "document_name": document_name,
        "document_sha256": document_sha256,
        "chunk_index": index,
        "content": chunk
    } for index, chunk in enumerate(chunks)]
    url = f"{settings.search_endpoint}/indexes/{settings.search_index}/docs/index"
    results = []
    for start in range(0, len(documents), 1000):
        response = requests.post(url, params={"api-version": settings.search_api_version}, headers=_headers(), json={"value": documents[start:start + 1000]}, timeout=45)
        response.raise_for_status()
        results.extend(response.json().get("value", []))
    failures = [item for item in results if not item.get("status")]
    if failures:
        raise RuntimeError(f"Azure AI Search rejected {len(failures)} chunk(s): {failures[:3]}")
    return results


def search_chunks(query, document_names=None, top=5):
    body = {"search": query, "top": top, "select": "document_name,chunk_index,content", "queryType": "simple"}
    if document_names:
        escaped = [name.replace("'", "''") for name in document_names]
        body["filter"] = " or ".join(f"document_name eq '{name}'" for name in escaped)
    url = f"{settings.search_endpoint}/indexes/{settings.search_index}/docs/search"
    response = requests.post(url, params={"api-version": settings.search_api_version}, headers=_headers(), json=body, timeout=30)
    response.raise_for_status()
    return [{"document_name": item["document_name"], "chunk_index": item["chunk_index"], "text": item["content"], "score": float(item.get("@search.score", 0))} for item in response.json().get("value", [])]

def delete_document_chunks(document_sha256):
    if not is_configured():
        return {"deleted": 0, "configured": False}
    url = f"{settings.search_endpoint}/indexes/{settings.search_index}/docs"
    headers = _headers()
    response = requests.post(
        url,
        params={"api-version": settings.search_api_version},
        headers=headers,
        json={"search": "*", "filter": f"document_sha256 eq '{document_sha256}'", "select": "id", "top": 1000},
        timeout=30
    )
    response.raise_for_status()
    keys = [{"@search.action": "delete", "id": item["id"]} for item in response.json().get("value", [])]
    if keys:
        result = requests.post(
            f"{settings.search_endpoint}/indexes/{settings.search_index}/docs/index",
            params={"api-version": settings.search_api_version},
            headers=headers,
            json={"value": keys},
            timeout=30
        )
        result.raise_for_status()
    return {"deleted": len(keys), "configured": True}
