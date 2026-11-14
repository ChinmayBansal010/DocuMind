import time
from pathlib import Path

import requests

from documind.config import settings


def _safety_headers():
    return {
        "Ocp-Apim-Subscription-Key": settings.content_safety_key,
        "Content-Type": "application/json"
    }


def _chunks(text, size=9000):
    value = text or ""
    return [value[index:index + size] for index in range(0, len(value), size)] or [""]


def analyze_with_document_intelligence(path):
    if not (settings.document_intelligence_endpoint and settings.document_intelligence_key):
        return {"configured": False, "fields": {}, "error": "Azure Document Intelligence is not configured."}
    try:
        url = f"{settings.document_intelligence_endpoint}/documentintelligence/documentModels/{settings.document_intelligence_model}:analyze"
        headers = {"Ocp-Apim-Subscription-Key": settings.document_intelligence_key, "Content-Type": "application/octet-stream"}
        file_bytes = Path(path).read_bytes()
        if len(file_bytes) > 4 * 1024 * 1024:
            raise ValueError("Azure Document Intelligence F0 supports files up to 4 MB. Use local extraction or reduce the file size.")
        response = requests.post(url, params={"api-version": "2024-11-30"}, headers=headers, data=file_bytes, timeout=45)
        response.raise_for_status()
        operation = response.headers.get("Operation-Location")
        if not operation:
            raise RuntimeError("Azure did not return Operation-Location.")
        for _ in range(45):
            poll = requests.get(operation, headers={"Ocp-Apim-Subscription-Key": settings.document_intelligence_key}, timeout=20)
            poll.raise_for_status()
            payload = poll.json()
            if payload.get("status") == "succeeded":
                fields = {}
                for document in payload.get("analyzeResult", {}).get("documents", []):
                    for key, value in document.get("fields", {}).items():
                        fields[key] = {
                            "value": value.get("content") or value.get("valueString") or str(value.get("value", "")),
                            "confidence": float(value.get("confidence", 0.0)),
                            "source": "Azure Document Intelligence"
                        }
                analyze_result = payload.get("analyzeResult", {})
                tables = []
                for table in analyze_result.get("tables", []):
                    cells = {}
                    for cell in table.get("cells", []):
                        cells.setdefault(cell.get("rowIndex", 0), {})[cell.get("columnIndex", 0)] = cell.get("content", "")
                    tables.append([[cells[row].get(column, "") for column in range(max(cells[row].keys(), default=-1) + 1)] for row in sorted(cells)])
                return {
                    "configured": True,
                    "fields": fields,
                    "extracted_text": analyze_result.get("content", ""),
                    "tables": tables,
                    "pages_analyzed": len(analyze_result.get("pages", []))
                }
            if payload.get("status") == "failed":
                raise RuntimeError(payload.get("error", {}).get("message", "Analysis failed"))
            time.sleep(2)
        raise TimeoutError("Document Intelligence analysis timed out.")
    except Exception as exc:
        return {"configured": True, "fields": {}, "error": str(exc)}


def moderate_text(text):
    if settings.content_safety_endpoint and settings.content_safety_key:
        try:
            categories = {}
            for part in _chunks(text, 9000):
                response = requests.post(
                    settings.content_safety_endpoint + "/contentsafety/text:analyze",
                    params={"api-version": "2024-09-01"},
                    headers=_safety_headers(),
                    json={"text": part},
                    timeout=25
                )
                response.raise_for_status()
                for item in response.json().get("categoriesAnalysis", []):
                    categories[item["category"]] = max(categories.get(item["category"], 0), int(item["severity"]))
            return {
                "configured": True,
                "provider": "Azure AI Content Safety",
                "categories": categories,
                "blocked": any(value >= 4 for value in categories.values()),
                "status": "blocked" if any(value >= 4 for value in categories.values()) else "passed"
            }
        except Exception as exc:
            return {"configured": True, "provider": "Azure AI Content Safety", "categories": {}, "blocked": True, "status": "unavailable", "error": str(exc), "fail_closed": True}
    terms = ["kill yourself", "self harm", "hate all", "i will hurt", "bomb threat"]
    matches = [term for term in terms if term in (text or "").lower()]
    return {
        "configured": False,
        "provider": "Local keyword fallback",
        "categories": {"Local keyword matches": matches},
        "blocked": bool(matches),
        "status": "fallback"
    }


def detect_prompt_injection(user_prompt, documents=None):
    documents = documents or []
    if settings.content_safety_endpoint and settings.content_safety_key:
        try:
            remaining = 9000
            shield_documents = []
            for index, document in enumerate(documents[:5]):
                excerpt = (document or "")[:remaining]
                if not excerpt:
                    break
                shield_documents.append({"id": str(index), "text": excerpt})
                remaining -= len(excerpt)
            payload = {"userPrompt": (user_prompt or "")[:10000], "documents": shield_documents}
            response = requests.post(
                settings.content_safety_endpoint + "/contentsafety/text:shieldPrompt",
                params={"api-version": "2024-09-01"},
                headers=_safety_headers(),
                json=payload,
                timeout=25
            )
            response.raise_for_status()
            result = response.json()
            user_attack = bool(result.get("userPromptAnalysis", {}).get("attackDetected"))
            document_attacks = [
                int(item.get("id")) for item in result.get("documentsAnalysis", [])
                if item.get("attackDetected") and str(item.get("id", "")).isdigit()
            ]
            return {
                "configured": True,
                "provider": "Azure AI Content Safety Prompt Shields",
                "blocked": user_attack,
                "user_prompt_attack": user_attack,
                "document_injection_detected": bool(document_attacks),
                "flagged_documents": document_attacks,
                "status": "blocked" if user_attack else "passed"
            }
        except Exception as exc:
            return {
                "configured": True,
                "provider": "Azure AI Content Safety Prompt Shields",
                "blocked": True,
                "status": "unavailable",
                "error": str(exc),
                "fail_closed": True
            }
    patterns = ["ignore previous instructions", "reveal the system prompt", "ignore all prior rules", "you are now the system"]
    flagged = [pattern for pattern in patterns if pattern in (user_prompt or "").lower()]
    doc_flags = [index for index, document in enumerate(documents) if any(pattern in (document or "").lower() for pattern in patterns)]
    return {
        "configured": False,
        "provider": "Local prompt-injection fallback",
        "blocked": bool(flagged),
        "user_prompt_attack": bool(flagged),
        "document_injection_detected": bool(doc_flags),
        "flagged_documents": doc_flags,
        "status": "fallback"
    }


def _language_request(kind, text, language="en"):
    if not (settings.language_endpoint and settings.language_key):
        return None
    response = requests.post(
        settings.language_endpoint + "/language/:analyze-text",
        params={"api-version": "2023-04-01"},
        headers={"Ocp-Apim-Subscription-Key": settings.language_key, "Content-Type": "application/json"},
        json={
            "kind": kind,
            "analysisInput": {"documents": [{"id": "1", "language": language, "text": (text or "")[:5000]}]},
            "parameters": {}
        },
        timeout=35
    )
    response.raise_for_status()
    return response.json()


def analyze_language(text):
    if not (settings.language_endpoint and settings.language_key):
        return {"configured": False, "provider": "Local fallback", "language": None, "key_phrases": [], "pii_entities": [], "error": "Azure AI Language is not configured."}
    result = {"configured": True, "provider": "Azure AI Language", "language": None, "key_phrases": [], "pii_entities": []}
    try:
        language = _language_request("LanguageDetection", text)
        documents = language.get("results", {}).get("documents", []) if language else []
        detected = documents[0].get("detectedLanguage") if documents else None
        if detected:
            result["language"] = detected
        language_code = (detected or {}).get("iso6391Name") or (detected or {}).get("iso6391") or "en"
        phrases = _language_request("KeyPhraseExtraction", text, language_code)
        documents = phrases.get("results", {}).get("documents", []) if phrases else []
        if documents:
            result["key_phrases"] = documents[0].get("keyPhrases", [])
        pii = _language_request("PiiEntityRecognition", text, language_code)
        documents = pii.get("results", {}).get("documents", []) if pii else []
        if documents:
            result["pii_entities"] = [
                {"category": item.get("category"), "text": item.get("text"), "confidence": item.get("confidenceScore")}
                for item in documents[0].get("entities", [])
            ]
        return result
    except Exception as exc:
        return {**result, "error": str(exc)}


def translate_text(text, target_language, source_language=None):
    if not (settings.translator_key and settings.translator_region):
        return {"configured": False, "provider": "Not configured", "error": "Azure AI Translator is not configured."}
    if not text or len(text) > 45000:
        return {"configured": True, "error": "Text must contain between 1 and 45,000 characters."}
    try:
        headers = {
            "Ocp-Apim-Subscription-Key": settings.translator_key,
            "Ocp-Apim-Subscription-Region": settings.translator_region,
            "Content-Type": "application/json"
        }
        params = {"api-version": "3.0", "to": target_language}
        if source_language:
            params["from"] = source_language
        response = requests.post(
            settings.translator_endpoint + "/translate",
            params=params,
            headers=headers,
            json=[{"text": text}],
            timeout=35
        )
        response.raise_for_status()
        item = response.json()[0]
        return {
            "configured": True,
            "provider": "Azure AI Translator",
            "detected_language": item.get("detectedLanguage", {}).get("language"),
            "translations": item.get("translations", [])
        }
    except Exception as exc:
        return {"configured": True, "provider": "Azure AI Translator", "error": str(exc)}
