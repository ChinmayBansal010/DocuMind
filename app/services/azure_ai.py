import re
import threading
import time
from urllib.parse import quote, urlencode, urlsplit

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.azure_quota import reserve_monthly_usage, text_records
from app.services.errors import AzureServiceError

_rate_lock = threading.Lock()
_last_request: dict[str, float] = {}


def _throttle(service: str, interval: float) -> None:
    with _rate_lock:
        delay = interval - (time.monotonic() - _last_request.get(service, 0.0))
        if delay > 0:
            time.sleep(delay)
        _last_request[service] = time.monotonic()


def _provider_error_details(response: requests.Response) -> str:
    try:
        payload = response.json()
    except (AttributeError, ValueError, TypeError):
        return ""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return ""
    code = error.get("code")
    message = error.get("message")
    details = []
    if isinstance(code, str) and code.strip():
        details.append(re.sub(r"[\r\n\t]+", " ", code).strip()[:100])
    if isinstance(message, str) and message.strip():
        details.append(re.sub(r"[\r\n\t]+", " ", message).strip()[:300])
    return ": ".join(details)


def request(
    service: str,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[int, int] = (5, 45),
    interval: float = 0.0,
    acceptable_statuses: tuple[int, ...] = (),
    **kwargs,
) -> requests.Response:
    _throttle(service, interval)
    try:
        response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        raise AzureServiceError(
            service, "is unavailable because the request could not reach the service."
        ) from exc
    if response.status_code in acceptable_statuses:
        return response
    if response.status_code == 429:
        details = _provider_error_details(response)
        raise AzureServiceError(
            service,
            "rejected the request because its rate limit or quota was reached; retry after the quota resets."
            + (f" Provider details: {details}" if details else ""),
            status_code=429,
        )
    if response.status_code in (401, 403):
        details = _provider_error_details(response)
        raise AzureServiceError(
            service,
            f"rejected the request (HTTP {response.status_code}); check the key, endpoint, region, and tier."
            + (f" Provider details: {details}" if details else ""),
            status_code=503,
        )
    if not response.ok:
        details = _provider_error_details(response)
        raise AzureServiceError(
            service,
            f"could not complete the request (HTTP {response.status_code})"
            + (f": {details}" if details else "."),
            status_code=502,
        )
    return response


def response_json(service: str, response: requests.Response) -> dict | list:
    try:
        payload = response.json()
    except (ValueError, TypeError) as exc:
        raise AzureServiceError(
            service, "returned an invalid response.", status_code=502
        ) from exc
    if not isinstance(payload, (dict, list)):
        raise AzureServiceError(service, "returned an invalid response.", status_code=502)
    return payload


def response_object(service: str, response: requests.Response) -> dict:
    payload = response_json(service, response)
    if not isinstance(payload, dict):
        raise AzureServiceError(service, "returned an invalid response.", status_code=502)
    return payload


def _result_list(service: str, payload: dict, key: str) -> list:
    result = payload.get("results", {})
    items = result.get(key) if isinstance(result, dict) else None
    if not isinstance(items, list):
        raise AzureServiceError(service, "returned an invalid response.", status_code=502)
    return items


def analyze_document_bytes(
    content: bytes,
    *,
    content_type: str,
    db: Session,
    pages: str | None = None,
    page_units: int = 1,
) -> dict:
    reserve_monthly_usage(db, "document_intelligence", page_units)
    query = {"api-version": settings.document_intelligence_api_version}
    if pages:
        query["pages"] = pages
    url = (
        f"{settings.document_intelligence_endpoint}/documentintelligence/documentModels/"
        f"{quote(settings.document_intelligence_model, safe='')}:analyze?{urlencode(query)}"
    )
    response = request(
        "Document Intelligence",
        "POST",
        url,
        headers={
            "Ocp-Apim-Subscription-Key": settings.document_intelligence_key,
            "Content-Type": content_type,
        },
        data=content,
        interval=1.0,
    )
    operation_url = response.headers.get("Operation-Location")
    if not operation_url:
        raise AzureServiceError(
            "Document Intelligence", "returned no operation status URL.", status_code=502
        )
    operation = urlsplit(operation_url)
    endpoint = urlsplit(settings.document_intelligence_endpoint)
    if operation.scheme != "https" or operation.netloc != endpoint.netloc:
        raise AzureServiceError(
            "Document Intelligence", "returned an invalid operation status URL.", status_code=502
        )
    for _ in range(60):
        time.sleep(2)
        status_response = request(
            "Document Intelligence",
            "GET",
            operation_url,
            headers={"Ocp-Apim-Subscription-Key": settings.document_intelligence_key},
            interval=1.0,
        )
        result = response_object("Document Intelligence", status_response)
        status = result.get("status")
        if status == "succeeded":
            analyze_result = result.get("analyzeResult")
            if not isinstance(analyze_result, dict):
                raise AzureServiceError(
                    "Document Intelligence", "returned no structured analysis result.", status_code=502
                )
            return analyze_result
        if status in ("failed", "canceled"):
            raise AzureServiceError(
                "Document Intelligence",
                "could not extract this document. Verify its format, page range, and file size.",
                status_code=422,
            )
    raise AzureServiceError(
        "Document Intelligence", "processing timed out; retry the upload.", status_code=504
    )


def _language_request(
    kind: str, text: str, db: Session, language: str | None = None
) -> dict:
    reserve_monthly_usage(db, "language", text_records(text))
    url = f"{settings.language_endpoint}/language/:analyze-text?api-version={settings.language_api_version}"
    body = {
        "kind": kind,
        "analysisInput": {
            "documents": [
                {
                    "id": "1",
                    "text": text[:5120],
                    **({"language": language} if language else {}),
                }
            ]
        },
        "parameters": {"modelVersion": "latest"},
    }
    response = request(
        "Language",
        "POST",
        url,
        headers={
            "Ocp-Apim-Subscription-Key": settings.language_key,
            "Content-Type": "application/json",
        },
        json=body,
        interval=0.01,
    )
    return response_object("Language", response)


def analyze_language(text: str, db: Session) -> dict:
    results: dict[str, list] = {
        "detected_languages": [],
        "entities": [],
        "key_phrases": [],
    }
    for offset in range(0, len(text), 5000):
        segment = text[offset : offset + 5000]
        detection = _language_request("LanguageDetection", segment, db)
        detected_documents = _result_list("Language", detection, "documents")
        if any(not isinstance(item, dict) for item in detected_documents):
            raise AzureServiceError("Language", "returned an invalid response.", status_code=502)
        if len(detected_documents) != 1:
            raise AzureServiceError(
                "Language", "could not detect the extracted contract language.", status_code=502
            )
        detected = detected_documents[0].get("detectedLanguage", {}) if detected_documents else {}
        if (
            not isinstance(detected, dict)
            or not isinstance(detected.get("iso6391Name"), str)
            or not isinstance(detected.get("name"), str)
        ):
            raise AzureServiceError("Language", "returned an invalid response.", status_code=502)
        language = detected.get("iso6391Name")
        if detected:
            results["detected_languages"].append(
                {
                    "language": language or detected.get("name", "unknown"),
                    "name": detected.get("name", "Unknown"),
                    "confidence": detected.get("confidenceScore"),
                }
            )
        for kind, field, result_key in (
            ("EntityRecognition", "entities", "entities"),
            ("KeyPhraseExtraction", "keyPhrases", "key_phrases"),
        ):
            payload = _language_request(kind, segment, db, language)
            documents = _result_list("Language", payload, "documents")
            if any(not isinstance(item, dict) for item in documents):
                raise AzureServiceError("Language", "returned an invalid response.", status_code=502)
            if len(documents) != 1:
                raise AzureServiceError(
                    "Language", "could not analyze the extracted contract text.", status_code=502
                )
            found = documents[0].get(field, [])
            if not isinstance(found, list) or any(
                not isinstance(item, dict if result_key == "entities" else str)
                for item in found
            ):
                raise AzureServiceError("Language", "returned an invalid response.", status_code=502)
            if result_key == "entities":
                for entity in found:
                    if isinstance(entity.get("offset"), int):
                        entity["offset"] += offset
            results[result_key].extend(found)
    unique_languages = {}
    for item in results["detected_languages"]:
        unique_languages[item["language"]] = item
    results["detected_languages"] = list(unique_languages.values())
    return results


def analyze_content_safety(text: str, db: Session) -> dict:
    findings = []
    for offset in range(0, len(text), 10_000):
        segment = text[offset : offset + 10_000]
        reserve_monthly_usage(db, "content_safety", text_records(segment))
        url = (
            f"{settings.content_safety_endpoint}/contentsafety/text:analyze"
            f"?api-version={settings.content_safety_api_version}"
        )
        payload = request(
            "Content Safety",
            "POST",
            url,
            headers={
                "Ocp-Apim-Subscription-Key": settings.content_safety_key,
                "Content-Type": "application/json",
            },
            json={
                "text": segment,
                "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],
                "outputType": "FourSeverityLevels",
            },
            interval=0.2,
        )
        payload = response_object("Content Safety", payload)
        categories = payload.get("categoriesAnalysis")
        if not isinstance(categories, list) or any(
            not isinstance(item, dict)
            or not isinstance(item.get("category"), str)
            or not isinstance(item.get("severity"), int)
            for item in categories
        ):
            raise AzureServiceError("Content Safety", "returned an invalid response.", status_code=502)
        if {item["category"] for item in categories} != {"Hate", "SelfHarm", "Sexual", "Violence"}:
            raise AzureServiceError("Content Safety", "returned incomplete category analysis.", status_code=502)
        findings.extend(categories)
    threshold = settings.content_safety_block_severity
    return {
        "provider": "Azure AI Content Safety",
        "threshold": threshold,
        "categories": findings,
        "blocked": any(item.get("severity", 0) >= threshold for item in findings),
    }


def shield_prompt(
    user_prompt: str, documents: list[str], db: Session
) -> dict:
    user_prompt = user_prompt[:10_000]
    prompt_attack = False
    flagged_documents = []
    batches = [documents[index : index + 5] for index in range(0, len(documents), 5)] or [[]]
    for batch_start, batch in enumerate(batches):
        document_text = [item[:10_000] for item in batch]
        if sum(map(len, document_text)) > 10_000:
            raise AzureServiceError(
                "Content Safety",
                "Prompt Shields document input exceeds the 10,000-character request limit.",
                status_code=413,
            )
        reserve_monthly_usage(
            db, "content_safety", text_records(user_prompt) + sum(text_records(item) for item in document_text)
        )
        url = (
            f"{settings.content_safety_endpoint}/contentsafety/text:shieldPrompt"
            f"?api-version={settings.content_safety_api_version}"
        )
        payload = request(
            "Content Safety",
            "POST",
            url,
            headers={
                "Ocp-Apim-Subscription-Key": settings.content_safety_key,
                "Content-Type": "application/json",
            },
            json={
                "userPrompt": user_prompt,
                "documents": document_text,
            },
            interval=0.2,
        )
        payload = response_object("Content Safety", payload)
        prompt_analysis = payload.get("userPromptAnalysis")
        document_analysis = payload.get("documentsAnalysis", [] if not document_text else None)
        if (
            not isinstance(prompt_analysis, dict)
            or not isinstance(prompt_analysis.get("attackDetected"), bool)
            or not isinstance(document_analysis, list)
            or len(document_analysis) != len(document_text)
            or any(
                not isinstance(item, dict)
                or not isinstance(item.get("attackDetected"), bool)
                for item in document_analysis
            )
        ):
            raise AzureServiceError("Content Safety", "returned an invalid response.", status_code=502)
        prompt_attack = prompt_attack or prompt_analysis.get("attackDetected", False)
        flagged_documents.extend(
            str(batch_start * 5 + index)
            for index, item in enumerate(document_analysis)
            if item["attackDetected"]
        )
    return {
        "provider": "Azure AI Content Safety Prompt Shields",
        "user_prompt_attack": bool(prompt_attack),
        "flagged_document_ids": flagged_documents,
    }


def translate_text(
    text: str, target_language: str, source_language: str | None, db: Session
) -> dict:
    translated = []
    detected_sources = set()
    for offset in range(0, len(text), 50_000):
        segment = text[offset : offset + 50_000]
        reserve_monthly_usage(db, "translator", len(segment))
        query = {"api-version": settings.translator_api_version, "to": target_language}
        if source_language:
            query["from"] = source_language
        response = request(
            "Translator",
            "POST",
            f"{settings.translator_endpoint}/translate?{urlencode(query)}",
            headers={
                "Ocp-Apim-Subscription-Key": settings.translator_key,
                "Ocp-Apim-Subscription-Region": settings.translator_region,
                "Content-Type": "application/json",
            },
            json=[{"text": segment}],
            interval=0.01,
        )
        response = response_json("Translator", response)
        if (
            not isinstance(response, list)
            or not response
            or not isinstance(response[0], dict)
            or not isinstance(response[0].get("translations"), list)
            or not response[0]["translations"]
            or not isinstance(response[0]["translations"][0], dict)
            or not isinstance(response[0]["translations"][0].get("text"), str)
        ):
            raise AzureServiceError("Translator", "returned no translated text.", status_code=502)
        translated.append(response[0]["translations"][0]["text"])
        if source_language is None:
            detected_language = response[0].get("detectedLanguage")
            if isinstance(detected_language, dict) and detected_language.get("language"):
                detected_sources.add(detected_language["language"])
    return {
        "text": "".join(translated),
        "source_language": source_language or ", ".join(sorted(detected_sources)) or "auto-detected",
        "target_language": target_language,
        "provider": "Azure AI Translator Text API (F0)",
    }
