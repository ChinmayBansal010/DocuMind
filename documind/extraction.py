import re

PATTERNS = {
    "InvoiceNumber": [
        r"(?:invoice\s*(?:number|no\.?|#))\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]+)",
        r"(?:invoice\s*(?:number|no\.?|#))\s*[:#-]?\s*(?:#)?\s*([A-Z0-9][A-Z0-9/-]+)",
    ],
    "InvoiceDate": [r"(?:invoice\s*date|date)\s*[:#-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"],
    "CustomerName": [
        r"(?:customer(?:\s+name)?|bill\s*to|client)\s*[:#-]?\s*([A-Za-z][A-Za-z0-9 &.,'/-]{2,})",
        r"(?:customer(?:\s+name)?|bill\s*to|client)\s*[:#-]?\s*(?:name\s*)?([A-Za-z][A-Za-z0-9 &.,'/-]{2,})",
    ],
    "TaxAmount": [r"(?:tax|gst|vat)\s*(?:amount)?\s*[:#-]?\s*(?:₹|INR|Rs\.?)?\s*([0-9,]+(?:\.\d{1,2})?)"],
    "TotalAmount": [r"(?:grand\s*total|total\s*(?:amount|due)?)\s*[:#-]?\s*(?:₹|INR|Rs\.?)?\s*([0-9,]+(?:\.\d{1,2})?)"]
}

def extract_fields_locally(text, requested_fields):
    result = {}
    for field in requested_fields:
        found = ""
        for pattern in PATTERNS.get(field, []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                found = match.group(1).strip().rstrip(".,")
                break
        result[field] = {"value": found, "confidence": 0.55 if found else 0.0, "source": "local regex; indicative only"}
    return result
