import hashlib
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.azure_ai import request, response_object
from app.services.errors import AzureServiceError


def _index_url(suffix: str = "") -> str:
    name = quote(settings.search_index, safe="")
    return f"{settings.search_endpoint}/indexes/{name}{suffix}?api-version={settings.search_api_version}"


def _headers() -> dict[str, str]:
    return {"api-key": settings.search_key, "Content-Type": "application/json"}


def _owner_key(owner_id: str) -> str:
    return hashlib.sha256(f"documind-owner:{owner_id}".encode("utf-8")).hexdigest()


def _documents(result: dict) -> list[dict]:
    documents = result.get("value")
    if not isinstance(documents, list) or any(not isinstance(item, dict) for item in documents):
        raise AzureServiceError("Search", "returned an invalid document response.", status_code=502)
    return documents


def _required_fields() -> set[str]:
    return {
        "id",
        "owner_id",
        "project_id",
        "contract_id",
        "version_id",
        "document_name",
        "page",
        "content",
        "content_vector",
    }


def ensure_index() -> None:
    response = request(
        "Search",
        "GET",
        _index_url(),
        headers=_headers(),
        acceptable_statuses=(404,),
    )
    if response.status_code == 404:
        body = {
            "name": settings.search_index,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
                {"name": "owner_id", "type": "Edm.String", "filterable": True},
                {"name": "project_id", "type": "Edm.String", "filterable": True},
                {"name": "contract_id", "type": "Edm.String", "filterable": True},
                {"name": "version_id", "type": "Edm.String", "filterable": True},
                {"name": "document_name", "type": "Edm.String", "searchable": True},
                {"name": "page", "type": "Edm.Int32", "filterable": True},
                {"name": "content", "type": "Edm.String", "searchable": True},
                {
                    "name": "content_vector",
                    "type": "Collection(Edm.Single)",
                    "searchable": True,
                    "vectorSearchDimensions": settings.search_vector_dimensions,
                    "vectorSearchProfile": "documind-vector-profile",
                },
            ],
            "vectorSearch": {
                "algorithms": [
                    {"name": "documind-hnsw", "kind": "hnsw"}
                ],
                "profiles": [
                    {
                        "name": "documind-vector-profile",
                        "algorithm": "documind-hnsw",
                    }
                ],
            },
        }
        request("Search", "PUT", _index_url(), headers=_headers(), json=body)
        return
    index = response_object("Search", response)
    index_fields = index.get("fields")
    if not isinstance(index_fields, list):
        raise AzureServiceError("Search", "returned an invalid index schema.", status_code=502)
    fields = {
        field.get("name"): field
        for field in index_fields
        if isinstance(field, dict)
    }
    if not _required_fields().issubset(fields):
        raise AzureServiceError(
            "Search",
            "the configured index has an incompatible schema; create a new index name without deleting the existing index.",
            status_code=409,
        )
    expected = {
        "id": ("Edm.String", "key"),
        "owner_id": ("Edm.String", "filterable"),
        "project_id": ("Edm.String", "filterable"),
        "contract_id": ("Edm.String", "filterable"),
        "version_id": ("Edm.String", "filterable"),
        "document_name": ("Edm.String", "searchable"),
        "page": ("Edm.Int32", "filterable"),
        "content": ("Edm.String", "searchable"),
        "content_vector": ("Collection(Edm.Single)", "searchable"),
    }
    if any(
        fields[name].get("type") != data_type or not fields[name].get(attribute)
        for name, (data_type, attribute) in expected.items()
    ):
        raise AzureServiceError(
            "Search",
            "the configured index fields are incompatible; create a new index name without deleting the existing index.",
            status_code=409,
        )
    vector_field = fields["content_vector"]
    if (
        vector_field.get("vectorSearchDimensions") != settings.search_vector_dimensions
        or not vector_field.get("vectorSearchProfile")
    ):
        raise AzureServiceError(
            "Search",
            "the configured index vector dimensions or profile do not match this application's settings.",
            status_code=409,
        )


def upsert_version(
    *,
    owner_id: str,
    project_id: str,
    contract_id: str,
    version_id: str,
    document_name: str,
    chunks: list[dict],
) -> None:
    if any(not isinstance(item.get("embedding"), list) for item in chunks):
        raise AzureServiceError(
            "Search",
            "local Ollama embeddings are unavailable; hybrid indexing cannot continue.",
            status_code=503,
        )
    ensure_index()
    for offset in range(0, len(chunks), 500):
        documents = [
            {
                "@search.action": "mergeOrUpload",
                "id": f"{version_id}:{item['index']}",
                "owner_id": _owner_key(owner_id),
                "project_id": project_id,
                "contract_id": contract_id,
                "version_id": version_id,
                "document_name": document_name,
                "page": item["page_number"],
                "content": item["text"],
                "content_vector": item["embedding"],
            }
            for item in chunks[offset : offset + 500]
        ]
        response = request(
            "Search",
            "POST",
            _index_url("/docs/index"),
            headers=_headers(),
            json={"value": documents},
        )
        result = response_object("Search", response)
        indexed = _documents(result)
        if len(indexed) != len(documents) or any(
            not item.get("status", False) for item in indexed
        ):
            raise AzureServiceError(
                "Search",
                "rejected one or more contract chunks; check Free-tier storage capacity and index schema.",
                status_code=502,
            )


def hybrid_search(
    *,
    owner_id: str,
    project_id: str,
    latest_version_ids: list[str],
    query: str,
    query_vector: list[float],
    contract_id: str | None,
    top_k: int = 5,
) -> list[dict]:
    if not latest_version_ids:
        return []
    ensure_index()
    versions = ",".join(latest_version_ids)
    filters = [
        f"owner_id eq '{_owner_key(owner_id)}'",
        f"project_id eq '{project_id.replace(chr(39), chr(39) * 2)}'",
        f"search.in(version_id, '{versions}', ',')",
    ]
    if contract_id:
        filters.append(f"contract_id eq '{contract_id.replace(chr(39), chr(39) * 2)}'")
    body = {
        "search": query,
        "searchFields": "content",
        "searchMode": "any",
        "queryType": "simple",
        "filter": " and ".join(filters),
        "select": "id,owner_id,project_id,contract_id,version_id,document_name,page,content",
        "top": top_k,
        "vectorQueries": [
            {
                "kind": "vector",
                "vector": query_vector,
                "fields": "content_vector",
                "k": top_k,
            }
        ],
    }
    response = request(
        "Search",
        "POST",
        _index_url("/docs/search"),
        headers=_headers(),
        json=body,
    )
    result = response_object("Search", response)
    hits = []
    for item in _documents(result):
        if (
            item.get("owner_id") != _owner_key(owner_id)
            or item.get("project_id") != project_id
            or item.get("version_id") not in latest_version_ids
            or (contract_id and item.get("contract_id") != contract_id)
            or not isinstance(item.get("document_name"), str)
            or not isinstance(item.get("content"), str)
            or not item.get("content")
            or (
                item.get("page") is not None
                and not isinstance(item.get("page"), int)
            )
        ):
            continue
        hits.append(
            {
                "chunk_id": item.get("id"),
                "contract_id": item.get("contract_id"),
                "version_id": item.get("version_id"),
                "document_name": item.get("document_name"),
                "page": item.get("page"),
                "text": item.get("content", ""),
                "score": item.get("@search.score", 0.0),
            }
        )
    return hits


def _delete_by_filter(filter_query: str) -> None:
    ensure_index()
    ids = []
    skip = 0
    while True:
        response = request(
            "Search",
            "POST",
            _index_url("/docs/search"),
            headers=_headers(),
            json={
                "search": "*",
                "filter": filter_query,
                "select": "id",
                "top": 1000,
                "skip": skip,
            },
        )
        result = response_object("Search", response)
        page = [item["id"] for item in _documents(result) if item.get("id")]
        ids.extend(page)
        if len(page) < 1000:
            break
        skip += 1000
    for offset in range(0, len(ids), 500):
        response = request(
            "Search",
            "POST",
            _index_url("/docs/index"),
            headers=_headers(),
            json={
                "value": [
                    {"@search.action": "delete", "id": document_id}
                    for document_id in ids[offset : offset + 500]
                ]
            },
        )
        deleted = response_object("Search", response)
        deletion_results = _documents(deleted)
        expected_count = min(500, len(ids) - offset)
        if len(deletion_results) != expected_count or any(
            not item.get("status", False) for item in deletion_results
        ):
            raise AzureServiceError(
                "Search", "could not delete all contract index records.", status_code=502
            )


def delete_contract_documents(
    *, owner_id: str, project_id: str, contract_id: str
) -> None:
    _delete_by_filter(
        f"owner_id eq '{_owner_key(owner_id)}' "
        f"and project_id eq '{project_id.replace(chr(39), chr(39) * 2)}' "
        f"and contract_id eq '{contract_id.replace(chr(39), chr(39) * 2)}'"
    )


def delete_project_documents(*, owner_id: str, project_id: str) -> None:
    _delete_by_filter(
        f"owner_id eq '{_owner_key(owner_id)}' "
        f"and project_id eq '{project_id.replace(chr(39), chr(39) * 2)}'"
    )


def delete_version_documents(
    *, owner_id: str, project_id: str, version_id: str
) -> None:
    _delete_by_filter(
        f"owner_id eq '{_owner_key(owner_id)}' "
        f"and project_id eq '{project_id.replace(chr(39), chr(39) * 2)}' "
        f"and version_id eq '{version_id.replace(chr(39), chr(39) * 2)}'"
    )
