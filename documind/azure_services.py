import time
import requests
from pathlib import Path
from documind.config import settings

def analyze_with_document_intelligence(path):
    if not (settings.document_intelligence_endpoint and settings.document_intelligence_key):
        return {"configured":False,"fields":{},"error":"Azure Document Intelligence is not configured."}
    try:
        url = f"{settings.document_intelligence_endpoint}/documentintelligence/documentModels/{settings.document_intelligence_model}:analyze"
        headers = {"Ocp-Apim-Subscription-Key":settings.document_intelligence_key,"Content-Type":"application/octet-stream"}
        response = requests.post(url, params={"api-version":"2024-11-30"}, headers=headers, data=Path(path).read_bytes(), timeout=45)
        response.raise_for_status()
        operation = response.headers.get("Operation-Location")
        if not operation: raise RuntimeError("Azure did not return Operation-Location.")
        for _ in range(45):
            poll = requests.get(operation, headers={"Ocp-Apim-Subscription-Key":settings.document_intelligence_key}, timeout=20)
            poll.raise_for_status()
            payload = poll.json()
            if payload.get("status") == "succeeded":
                fields = {}
                for document in payload.get("analyzeResult",{}).get("documents",[]):
                    for key,value in document.get("fields",{}).items():
                        fields[key] = {"value":value.get("content") or value.get("valueString") or str(value.get("value","")),
                                       "confidence":float(value.get("confidence",0.0)),"source":"Azure Document Intelligence"}
                return {"configured":True,"fields":fields}
            if payload.get("status") == "failed": raise RuntimeError(payload.get("error",{}).get("message","Analysis failed"))
            time.sleep(2)
        raise TimeoutError("Document Intelligence analysis timed out.")
    except Exception as exc:
        return {"configured":True,"fields":{},"error":str(exc)}

def moderate_text(text):
    if settings.content_safety_endpoint and settings.content_safety_key:
        try:
            url = settings.content_safety_endpoint + "/contentsafety/text:analyze"
            response = requests.post(url, params={"api-version":"2024-09-01"},
                headers={"Ocp-Apim-Subscription-Key":settings.content_safety_key,"Content-Type":"application/json"},
                json={"text":text}, timeout=25)
            response.raise_for_status()
            categories = {x["category"]:x["severity"] for x in response.json().get("categoriesAnalysis",[])}
            return {"configured":True,"categories":categories,"blocked":any(v >= 4 for v in categories.values())}
        except Exception as exc:
            return {"configured":True,"categories":{},"blocked":False,"error":str(exc)}
    terms = ["kill yourself","self harm","hate all","i will hurt","bomb threat"]
    matches = [term for term in terms if term in text.lower()]
    return {"configured":False,"categories":{"Local keyword matches":matches},"blocked":bool(matches)}
