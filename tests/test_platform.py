from types import SimpleNamespace

import jwt
import fitz
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import assistant as assistant_routes
from app.api.v1 import contracts as contract_routes
from app.api.v1 import projects as project_routes
from app.core import security
from app.core.config import settings
from app.db.models import Base, Project, User
from app.db.session import get_db
from app.engines.analysis import analyze_contract
from app.engines.comparison import compare_obligations, compare_texts
from app.engines.extraction import chunks_with_pages, extract
from app.main import app
from app.services.azure_quota import reserve_monthly_usage
from app.services.errors import AzureServiceError
from app.services import azure_search


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    owner = User(id="user-owner", email="owner@example.test", name="Owner")
    other = User(id="user-other", email="other@example.test", name="Other")
    with test_sessions() as session:
        session.add_all([owner, other])
        session.commit()
        foreign_project = Project(owner_id=other.id, name="Private project")
        session.add(foreign_project)
        session.commit()
        foreign_project_id = foreign_project.id

    def override_db():
        with test_sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[security.get_current_user] = lambda: owner
    app.state.rate_limit_disabled = True
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "ollama_model", "")
    for name in (
        "document_intelligence_endpoint",
        "language_endpoint",
        "translator_endpoint",
        "content_safety_endpoint",
        "search_endpoint",
    ):
        monkeypatch.setattr(settings, name, "https://azure.example.test")
    for name in (
        "document_intelligence_key",
        "language_key",
        "translator_key",
        "translator_region",
        "content_safety_key",
        "search_key",
        "search_index",
        "document_intelligence_model",
    ):
        monkeypatch.setattr(settings, name, "test-config")
    monkeypatch.setattr(settings, "search_vector_dimensions", 768)
    safe_result = {"provider": "Azure AI Content Safety", "blocked": False, "categories": []}
    safe_shield = {
        "provider": "Azure AI Content Safety Prompt Shields",
        "user_prompt_attack": False,
        "flagged_document_ids": [],
    }
    monkeypatch.setattr(contract_routes, "analyze_content_safety", lambda _text, _db: safe_result)
    monkeypatch.setattr(contract_routes, "shield_prompt", lambda _prompt, _docs, _db: safe_shield)
    monkeypatch.setattr(contract_routes, "analyze_language", lambda _text, _db: {"detected_languages": ["en"]})
    monkeypatch.setattr(contract_routes, "embed", lambda texts: [[0.0] * 768 for _ in texts])
    monkeypatch.setattr(contract_routes, "upsert_version", lambda **_kwargs: None)
    monkeypatch.setattr(contract_routes, "delete_version_documents", lambda **_kwargs: None)
    monkeypatch.setattr(contract_routes, "delete_contract_documents", lambda **_kwargs: None)
    monkeypatch.setattr(project_routes, "delete_project_documents", lambda **_kwargs: None)
    monkeypatch.setattr(assistant_routes, "analyze_content_safety", lambda _text, _db: safe_result)
    monkeypatch.setattr(assistant_routes, "shield_prompt", lambda _prompt, _docs, _db: safe_shield)
    monkeypatch.setattr(
        assistant_routes,
        "retrieve",
        lambda _question, **_kwargs: [
            {
                "chunk_id": "version:0",
                "contract_id": "contract",
                "version_id": "version",
                "document_name": "terms.txt",
                "page": None,
                "text": "Payment shall be made within 30 days.",
                "score": 1.0,
            }
        ],
    )
    monkeypatch.setattr(
        contract_routes,
        "translate_text",
        lambda text, target, source, _db: {
            "text": f"{target}: {text}",
            "source_language": source or "en",
            "target_language": target,
            "provider": "Azure AI Translator Text API (F0)",
        },
    )
    with TestClient(app) as test_client:
        test_client.foreign_project_id = foreign_project_id
        yield test_client
    app.dependency_overrides.clear()
    app.state.rate_limit_disabled = False
    engine.dispose()


def test_jwks_token_validation_requires_valid_issuer_and_expiry(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    monkeypatch.setattr(settings, "auth_base_url", "https://auth.example.test/project")
    monkeypatch.setattr(settings, "auth_jwks_url", "https://auth.example.test/project/jwks")
    auth_origin = "https://auth.example.test"
    monkeypatch.setattr(
        security,
        "_jwks_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=public_key)
        ),
    )
    token = jwt.encode(
        {
            "sub": "user-1",
            "iss": auth_origin,
            "aud": auth_origin,
            "exp": 4_102_444_800,
        },
        private_key,
        algorithm="EdDSA",
    )
    assert security.decode_access_token(token)["sub"] == "user-1"
    wrong_issuer = jwt.encode(
        {
            "sub": "user-1",
            "iss": settings.auth_base_url,
            "aud": auth_origin,
            "exp": 4_102_444_800,
        },
        private_key,
        algorithm="EdDSA",
    )
    with pytest.raises(HTTPException) as issuer_error:
        security.decode_access_token(wrong_issuer)
    assert issuer_error.value.status_code == 401
    wrong_audience = jwt.encode(
        {
            "sub": "user-1",
            "iss": auth_origin,
            "aud": "https://other.example.test",
            "exp": 4_102_444_800,
        },
        private_key,
        algorithm="EdDSA",
    )
    with pytest.raises(HTTPException) as audience_error:
        security.decode_access_token(wrong_audience)
    assert audience_error.value.status_code == 401
    with pytest.raises(HTTPException) as error:
        security.decode_access_token("not-a-token")
    assert error.value.status_code == 401


def test_authenticated_user_profile_is_persisted_by_neon_subject(tmp_path, monkeypatch):
    from fastapi.security import HTTPAuthorizationCredentials

    engine = create_engine(f"sqlite:///{tmp_path / 'auth-profile.db'}")
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(
        security,
        "decode_access_token",
        lambda _token: {"sub": "neon-user-id", "email": "person@example.test", "name": "Avery"},
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")

    with test_sessions() as session:
        user = security.get_current_user(credentials=credentials, db=session)
        assert user.id == "neon-user-id"
        assert user.email == "person@example.test"
        assert user.name == "Avery"

    with test_sessions() as session:
        persisted = session.get(User, "neon-user-id")
        assert persisted is not None
        assert session.query(User).count() == 1
    engine.dispose()


def test_project_crud_and_cross_user_isolation(client):
    created = client.post(
        "/api/v1/projects",
        json={"name": "Vendor review", "description": "Supply agreement"},
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert client.get("/api/v1/projects").json()[0]["name"] == "Vendor review"
    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated review", "description": ""},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated review"
    assert client.get(f"/api/v1/projects/{client.foreign_project_id}").status_code == 404
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 200
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404


def test_upload_validation_analysis_assistant_and_exports(client):
    project = client.post("/api/v1/projects", json={"name": "Agreements"}).json()
    project_id = project["id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/contracts",
        files=[
            (
                "files",
                (
                    "terms.txt",
                    b"Payment shall be made within 30 days. Either party may terminate with 30 days notice.",
                    "text/plain",
                ),
            )
        ],
    )
    assert response.status_code == 201
    uploaded = response.json()["results"][0]
    assert uploaded["status"] == "processed"
    contract_id = uploaded["contract_id"]
    version_id = uploaded["version_id"]

    invalid = client.post(
        f"/api/v1/projects/{project_id}/contracts",
        files=[("files", ("fake.pdf", b"not a pdf", "application/pdf"))],
    )
    assert invalid.json()["results"][0]["status"] == "error"

    analyzed = client.post(f"/api/v1/contracts/{contract_id}/analyze")
    assert analyzed.status_code == 200
    result = analyzed.json()["analysis"]
    assert any("Payment" in item["category"] for item in result["clauses"])
    assert result["clauses"][0]["evidence_type"] == "rule_based"
    assert client.get(f"/api/v1/versions/{version_id}/analysis").status_code == 200
    history = client.get(f"/api/v1/contracts/{contract_id}/analyses")
    assert history.status_code == 200
    assert len(history.json()) == 1

    question = client.post(
        f"/api/v1/contracts/{contract_id}/ask",
        json={"question": "When is payment due?"},
    )
    assert question.status_code == 200
    assert question.json()["citations"]
    assert question.json()["citations"][0]["page"] is None
    assert "30 days" in question.json()["answer"]

    markdown = client.get(f"/api/v1/versions/{version_id}/report?format=md")
    assert markdown.status_code == 200
    assert "Executive summary" in markdown.text
    pdf = client.get(f"/api/v1/versions/{version_id}/report?format=pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/v1/versions/{version_id}/report?format=json").json()["contract"]
    translated = client.post(
        f"/api/v1/versions/{version_id}/translate",
        json={"target_language": "es", "scope": "contract"},
    )
    assert translated.status_code == 201
    assert translated.json()["text"].startswith("es: ")
    assert client.get(f"/api/v1/versions/{version_id}/translations").json()[0]["target_language"] == "es"


def test_upload_new_version_and_compare(client):
    project = client.post("/api/v1/projects", json={"name": "Versions"}).json()
    uploaded = client.post(
        f"/api/v1/projects/{project['id']}/contracts",
        files=[("files", ("agreement.txt", b"1. Payment is due within 30 days.", "text/plain"))],
    ).json()["results"][0]
    second = client.post(
        f"/api/v1/projects/{project['id']}/contracts",
        data={"contract_id": uploaded["contract_id"]},
        files=[("files", ("agreement-v2.txt", b"1. Payment is due within 45 days.", "text/plain"))],
    )
    assert second.json()["results"][0]["version_number"] == 2
    compared = client.post(
        f"/api/v1/contracts/{uploaded['contract_id']}/compare",
        json={
            "first_version_id": uploaded["version_id"],
            "second_version_id": second.json()["results"][0]["version_id"],
        },
    )
    assert compared.status_code == 200
    assert compared.json()["modified"] >= 1


def test_analysis_evidence_and_page_number_are_source_grounded(monkeypatch):
    monkeypatch.setattr(settings, "ollama_model", "")
    text = "[Page 1]\nOther text.\n[Page 2]\nThis agreement renews automatically every year."
    analysis, model = analyze_contract(text)
    renewal = next(item for item in analysis["clauses"] if item["category"] == "Renewal")
    assert renewal["excerpt"] in text
    assert renewal["page"] == 2
    assert model == "Rule-based text matching"


def test_chunk_pages_and_comparison():
    chunks = chunks_with_pages(
        "[Page 1]\n" + "first page text. " * 25 + "\n[Page 2]\n" + "second page text. " * 25,
        chunk_size=100,
        overlap=15,
    )
    assert {chunk["page_number"] for chunk in chunks} == {1, 2}
    assert all(not ("first page text." in chunk["text"] and "second page text." in chunk["text"]) for chunk in chunks)
    comparison = compare_texts("1. Payment is due in 30 days.", "1. Payment is due in 45 days.")
    assert comparison["modified"] == 1
    obligation_changes = compare_obligations(
        [{"responsible_party": "Buyer", "obligation": "Pay invoices", "deadline": "30 days"}],
        [{"responsible_party": "Buyer", "obligation": "Pay invoices", "deadline": "45 days"}],
    )
    assert obligation_changes[0]["status"] == "modified"


def test_document_intelligence_splits_pdf_requests_and_preserves_page_numbers(tmp_path, monkeypatch):
    path = tmp_path / "five-pages.pdf"
    document = fitz.open()
    for page_number in range(1, 6):
        page = document.new_page()
        page.insert_text((72, 72), f"Contract page {page_number}")
    document.save(path)
    document.close()
    requests_seen = []

    def fake_analyze(content, *, page_units, **_kwargs):
        with fitz.open(stream=content, filetype="pdf") as segment:
            requests_seen.append((segment.page_count, len(content), page_units))
            return {
                "pages": [
                    {"lines": [{"content": page.get_text().strip()}]}
                    for page in segment
                ],
                "tables": [],
                "paragraphs": [],
            }

    monkeypatch.setattr("app.engines.extraction.analyze_document_bytes", fake_analyze)
    extracted = extract(path, db=None)
    assert all(1 <= pages <= 2 and size <= 4 * 1024 * 1024 and pages == units
               for pages, size, units in requests_seen)
    assert all(f"[Page {page}]" in extracted["text"] for page in range(1, 6))
    assert [page["pageNumber"] for page in extracted["layout_data"]["pages"]] == list(range(1, 6))


def test_azure_provider_rate_limit_has_service_specific_error(monkeypatch):
    from app.services.azure_ai import request

    monkeypatch.setattr(
        "app.services.azure_ai.requests.request",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=429, ok=False),
    )
    with pytest.raises(AzureServiceError, match="Azure Search") as error:
        request("Search", "POST", "https://search.example.test", headers={})
    assert error.value.status_code == 429


def test_azure_request_includes_safe_provider_error_details(monkeypatch):
    from app.services.azure_ai import request

    monkeypatch.setattr(
        "app.services.azure_ai.requests.request",
        lambda *_args, **_kwargs: SimpleNamespace(
            status_code=400,
            ok=False,
            json=lambda: {
                "error": {
                    "code": "InvalidRequestBody",
                    "message": "Can't parse your request correctly.\nCheck the API definition.",
                }
            },
        ),
    )
    with pytest.raises(AzureServiceError, match="InvalidRequestBody") as error:
        request("Content Safety", "POST", "https://safety.example.test", headers={})
    assert "Can't parse your request correctly." in str(error.value)
    assert error.value.status_code == 502


def test_azure_f0_quota_is_tracked_and_enforced(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'quota.db'}")
    Base.metadata.create_all(engine)
    test_sessions = sessionmaker(bind=engine)
    with test_sessions() as session:
        reserve_monthly_usage(session, "document_intelligence", 500)
        with pytest.raises(AzureServiceError, match="monthly allowance"):
            reserve_monthly_usage(session, "document_intelligence", 1)
    engine.dispose()


def test_language_analysis_uses_detection_entities_and_key_phrases(monkeypatch):
    from app.services import azure_ai

    monkeypatch.setattr(azure_ai, "reserve_monthly_usage", lambda *_args: None)
    requests_seen = []

    def fake_request(_service, _method, _url, *, json, **_kwargs):
        requests_seen.append(json["kind"])
        if json["kind"] == "LanguageDetection":
            payload = {
                "results": {
                    "documents": [
                        {
                            "detectedLanguage": {
                                "iso6391Name": "en",
                                "name": "English",
                                "confidenceScore": 0.99,
                            }
                        }
                    ]
                }
            }
        elif json["kind"] == "EntityRecognition":
            payload = {"results": {"documents": [{"entities": [{"text": "Acme", "category": "Organization", "offset": 0}]}]}}
        else:
            payload = {"results": {"documents": [{"keyPhrases": ["payment terms"]}]}}
        return SimpleNamespace(json=lambda: payload)

    monkeypatch.setattr(azure_ai, "request", fake_request)
    insights = azure_ai.analyze_language("Acme contract payment terms", db=None)
    assert requests_seen == ["LanguageDetection", "EntityRecognition", "KeyPhraseExtraction"]
    assert insights["detected_languages"][0]["language"] == "en"
    assert insights["entities"][0]["text"] == "Acme"
    assert insights["key_phrases"] == ["payment terms"]


def test_prompt_shields_fails_closed_on_missing_document_analysis(monkeypatch):
    from app.services import azure_ai

    monkeypatch.setattr(azure_ai, "reserve_monthly_usage", lambda *_args: None)
    monkeypatch.setattr(
        azure_ai,
        "request",
        lambda *_args, **_kwargs: SimpleNamespace(
            json=lambda: {"userPromptAnalysis": {"attackDetected": False}}
        ),
    )
    with pytest.raises(AzureServiceError, match="Azure Content Safety"):
        azure_ai.shield_prompt("Summarize this contract.", ["source passage"], db=None)


def test_prompt_shields_uses_string_documents_and_maps_flagged_chunk_indexes(monkeypatch):
    from app.services import azure_ai

    monkeypatch.setattr(azure_ai, "reserve_monthly_usage", lambda *_args: None)
    requests_seen = []

    def fake_request(_service, _method, _url, *, json, **_kwargs):
        requests_seen.append(json)
        document_results = [
            {"attackDetected": index == 3}
            for index in range(len(json["documents"]))
        ]
        if len(requests_seen) == 2:
            document_results[0]["attackDetected"] = True
        return SimpleNamespace(
            json=lambda: {
                "userPromptAnalysis": {"attackDetected": False},
                "documentsAnalysis": document_results,
            }
        )

    monkeypatch.setattr(azure_ai, "request", fake_request)
    findings = azure_ai.shield_prompt(
        "Summarize this contract.",
        [f"source passage {index}" for index in range(6)],
        db=None,
    )

    assert requests_seen[0]["documents"] == [f"source passage {i}" for i in range(5)]
    assert requests_seen[1]["documents"] == ["source passage 5"]
    assert findings["flagged_document_ids"] == ["3", "5"]


def test_translator_splits_text_at_f0_request_limit(monkeypatch):
    from app.services import azure_ai

    monkeypatch.setattr(azure_ai, "reserve_monthly_usage", lambda *_args: None)
    segments = []

    def fake_request(_service, _method, _url, *, json, **_kwargs):
        segments.append(json[0]["text"])
        return SimpleNamespace(
            json=lambda: [
                {
                    "detectedLanguage": {"language": "en"},
                    "translations": [{"text": json[0]["text"]}],
                }
            ]
        )

    monkeypatch.setattr(azure_ai, "request", fake_request)
    translated = azure_ai.translate_text("x" * 50_001, "es", None, db=None)
    assert [len(segment) for segment in segments] == [50_000, 1]
    assert len(translated["text"]) == 50_001
    assert translated["source_language"] == "en"


def test_azure_search_hybrid_query_is_tenant_and_version_scoped(monkeypatch):
    observed = {}
    monkeypatch.setattr(azure_search, "ensure_index", lambda: None)

    def fake_request(_service, _method, _url, *, json, **_kwargs):
        observed.update(json)
        return SimpleNamespace(
            json=lambda: {
                "value": [
                    {
                        "owner_id": azure_search._owner_key("owner"),
                        "project_id": "project",
                        "contract_id": "contract",
                        "version_id": "latest",
                        "document_name": "agreement.pdf",
                        "page": 3,
                        "content": "The notice period is thirty days.",
                        "@search.score": 1.0,
                    },
                    {
                        "owner_id": azure_search._owner_key("other-owner"),
                        "project_id": "project",
                        "contract_id": "contract",
                        "version_id": "latest",
                        "document_name": "private.pdf",
                        "page": 1,
                        "content": "Private text.",
                    },
                    {
                        "owner_id": azure_search._owner_key("owner"),
                        "project_id": "project",
                        "contract_id": "contract",
                        "version_id": "old",
                        "document_name": "agreement.pdf",
                        "page": 2,
                        "content": "Old version.",
                    },
                ]
            }
        )

    monkeypatch.setattr(azure_search, "request", fake_request)
    hits = azure_search.hybrid_search(
        owner_id="owner",
        project_id="project",
        latest_version_ids=["latest"],
        query="notice period",
        query_vector=[0.0] * settings.search_vector_dimensions,
        contract_id="contract",
    )
    assert len(hits) == 1
    assert hits[0]["version_id"] == "latest"
    assert f"owner_id eq '{azure_search._owner_key('owner')}'" in observed["filter"]
    assert "project_id eq 'project'" in observed["filter"]
    assert "search.in(version_id, 'latest', ',')" in observed["filter"]
    assert observed["vectorQueries"][0]["fields"] == "content_vector"


def test_upload_reports_azure_service_failure(client, monkeypatch):
    project = client.post("/api/v1/projects", json={"name": "Azure errors"}).json()

    def fail_language(_text, _db):
        raise AzureServiceError("Language", "the monthly allowance was reached.", status_code=429)

    monkeypatch.setattr(contract_routes, "analyze_language", fail_language)
    response = client.post(
        f"/api/v1/projects/{project['id']}/contracts",
        files=[("files", ("terms.txt", b"Payment is due within 30 days.", "text/plain"))],
    )
    result = response.json()["results"][0]
    assert result["status"] == "error"
    assert "Azure Language" in result["message"]
    assert "monthly allowance" in result["message"]
