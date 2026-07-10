"""
Pramaan — Unified intake pipeline.

Every message passes through four stages regardless of input channel
(web paste, OCR screenshot, voice note, Telegram bot, WhatsApp webhook):

  Stage 1 — Fast Path (rules + fuzzy-ML, <50ms, zero external API calls)
      • Text normalization and homoglyph stripping (normalize.py)
      • Scam typology fuzzy-match classifier (classifier.py)
      • URL threat analysis (url_agent.py)
      • Regex extraction of: amount, UPI handles, dates, payment method,
        counterparty names, UPI reference IDs

  Stage 2 — LLM Fallback  (only when Stage 1 confidence < 0.65 OR the
                             message contains Indic script characters)
      • Single Gemini call returns BOTH classification AND transaction
        extraction in one structured JSON pass — no double-calling.
      • Falls back silently to Stage 1 result if the API key is absent or
        the request fails; the user never sees an error because of this.

  Stage 3 — Verification  (read-only lookups, never state-changing)
      • Sender reputation from the contacts table
      • Community scam-pattern cosine similarity against stored embeddings
      • UPI handle lookalike check against known gov/bank names

  Stage 4 — Unified Scoring
      • One 0-100 risk_score computed from the SAME feature set that feeds
        both the fraud verdict and the transaction ledger entry — this is
        the architectural expression of 'authentication and data structuring
        are the same job.'
      • Explanation string generated from exactly the signals that fired.

All results are persisted to the local SQLite DB (db.py) so the dashboard
can show live history without re-processing anything.
"""

from __future__ import annotations

import re
import json
import logging
import os

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy deps — loaded lazily so the module imports fast
# ---------------------------------------------------------------------------
_st_model = None

def _get_st_model():
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as e:
            logger.warning("SentenceTransformer unavailable (%s) — community similarity disabled.", e)
    return _st_model


_scheme_collection = None

def _get_scheme_collection():
    global _scheme_collection
    if _scheme_collection is None:
        try:
            from scheme_check import build_collection
            _scheme_collection = build_collection()
        except Exception as e:
            logger.warning("Could not load scheme collection: %s", e)
    return _scheme_collection


# ---------------------------------------------------------------------------
# Stage 1 — Fast-path regex entity extraction
# ---------------------------------------------------------------------------

# Currency amounts: ₹1,234.56 / Rs. 1234 / INR 5000
_AMOUNT_RE = re.compile(
    r'(?:₹|Rs\.?\s*|INR\s*)([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE
)

# UPI VPA handles: word@word  (e.g. ramesh@okaxis, pmkisan-gov@sbi)
_UPI_VPA_RE = re.compile(r'\b[\w.\-]+@[\w.\-]+\b')

# UPI reference / transaction IDs
_UPI_REF_RE = re.compile(
    r'\b(?:UPI\s*[Rr]ef(?:erence)?\.?\s*[:=]?\s*|[Tt]xn\s*[Ii][Dd]\s*[:=]?\s*|[Rr]ef\s*[Nn]o\.?\s*[:=]?\s*)(\d{6,20})\b'
)

# Date patterns
_DATE_RE = re.compile(
    r'\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}'
    r'|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?)\b',
    re.IGNORECASE
)

# Payment methods
_PAYMENT_RE = re.compile(
    r'\b(UPI|NEFT|RTGS|IMPS|BHIM|PhonePe|GPay|Paytm|cash|cheque|card|netbanking|net banking)\b',
    re.IGNORECASE
)

# Transaction direction keywords
_RECV_RE = re.compile(r'\b(received|credited|got|mila|aaya|credit)\b', re.IGNORECASE)
_SENT_RE = re.compile(r'\b(paid|sent|transferred|debited|bhej|diya|debit)\b', re.IGNORECASE)

# Official gov/bank names that scammers put in UPI handles to fake legitimacy
_GOV_BANK_TOKENS = {
    "pmkisan", "pm-kisan", "sbi", "rbi", "uidai", "gov", "npci",
    "incometax", "income-tax", "ayushman", "nrega", "pmay", "pf", "epfo",
    "sebi", "nabard", "irctc", "india", "bharat", "sarkar",
}


def _extract_transaction_fast(text: str) -> dict:
    """
    Extract financial entities using regex. Returns a dict with parsed fields
    and an 'extraction_confidence' key indicating how complete the extraction is.
    """
    result: dict = {}

    amounts = _AMOUNT_RE.findall(text)
    if amounts:
        try:
            result["amount"] = float(amounts[0].replace(",", ""))
            result["currency"] = "INR"
        except ValueError:
            pass

    ref = _UPI_REF_RE.search(text)
    if ref:
        result["upi_reference"] = ref.group(1)

    dates = _DATE_RE.findall(text)
    if dates:
        result["txn_date"] = dates[0]

    payment = _PAYMENT_RE.search(text)
    if payment:
        result["payment_method"] = payment.group(1).upper()

    vpas = _UPI_VPA_RE.findall(text)
    if vpas:
        # Skip email-like addresses that look obviously non-UPI
        upi_vpas = [v for v in vpas if "." not in v.split("@")[0]]
        if upi_vpas:
            result["upi_handle"] = upi_vpas[0]

    if _RECV_RE.search(text):
        result["txn_direction"] = "inflow"
    elif _SENT_RE.search(text):
        result["txn_direction"] = "outflow"

    # Confidence estimate: how many transaction-relevant fields did we find?
    n_fields = sum(1 for k, v in result.items() if v)
    result["extraction_confidence"] = min(0.35 + (n_fields * 0.13), 0.95)
    return result


def _has_upi_lookalike(text: str) -> bool:
    """
    True if the text contains a UPI handle that spoofs a gov/bank name
    (e.g. 'pmkisan-cash@paytm' or 'sbi-kyc@axis') but is NOT an actual
    .gov.in / .nic.in domain.
    """
    for vpa in _UPI_VPA_RE.findall(text):
        if "@" not in vpa:
            continue
        local_part = vpa.split("@")[0].lower()
        domain_part = vpa.split("@")[1].lower()
        # Real gov UPI addresses don't exist via consumer UPI — flag any
        # handle whose local part contains a known gov/bank token.
        for token in _GOV_BANK_TOKENS:
            if token in local_part and ".gov" not in domain_part:
                return True
    return False


def _detect_transaction_intent(text: str) -> bool:
    """Quick gate: does this message look like it could contain a transaction?"""
    return bool(_AMOUNT_RE.search(text) or _UPI_REF_RE.search(text))


# ---------------------------------------------------------------------------
# Stage 2 — LLM fallback (Gemini, single structured call)
# ---------------------------------------------------------------------------

_LLM_PROMPT = """\
You are a unified fraud-detection and transaction-extraction assistant for the Pramaan system (India).

Analyze this message and return ONLY a valid JSON object — no preamble, no markdown fences, no explanation outside the JSON:

Message:
\"\"\"
{text}
\"\"\"

Return exactly this schema:
{{
  "classification":        "scam" | "suspicious" | "legitimate",
  "confidence":            0.0 to 1.0,
  "risk_signals":          ["list of specific red flags, or empty array"],
  "explanation":           "one plain-language sentence explaining the verdict",
  "is_real_transaction":   true | false,
  "amount":                number or null,
  "currency":              "INR" or null,
  "counterparty_name":     "string or null",
  "counterparty_phone":    "10-digit string or null",
  "txn_date":              "YYYY-MM-DD or null",
  "purpose":               "short description or null",
  "payment_method":        "UPI" | "NEFT" | "cash" | "other" | null,
  "upi_reference":         "string or null",
  "txn_direction":         "inflow" | "outflow" | null
}}

Rules:
- "scam" = clear deception (urgency language, OTP/PIN request, suspicious link, fake authority)
- "suspicious" = ambiguous — treat with caution but not a definitive scam
- "legitimate" = genuine transactional message with no deception signals
- is_real_transaction = true ONLY when a completed payment event is clearly described
- NEVER invent values. Return null for any field you are uncertain about.
"""


def _call_extraction_llm_model(client, model: str, prompt: str) -> dict | None:
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        raw = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                raw += part.text
        raw = raw.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        return json.loads(raw)
    except Exception as e:
        logger.warning("Extraction LLM model %s failed: %s", model, e)
        return None


def _llm_extract(text: str) -> dict | None:
    """
    Single Gemini call for both classification AND transaction extraction.
    Tries multiple models in a priority chain with retry logic on failure.
    """
    import time
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key in ("your_gemini_api_key", ""):
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = _LLM_PROMPT.format(text=text[:900])
        
        # Priority chain — ordered by reliability on free tier.
        # gemini-2.5-flash-lite: confirmed working (used elsewhere in api.py)
        # gemini-2.5-flash: standard Gemini 2.5 model, generally available
        # gemini-3.5-flash: last resort (often 503 under load)
        model_chain = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash"]
        for model in model_chain:
            for attempt in range(2):  # 2 attempts per model
                result = _call_extraction_llm_model(client, model, prompt)
                if result is not None:
                    logger.info("Extraction LLM succeeded via %s", model)
                    return result
                if attempt == 0:
                    logger.warning("Extraction model %s failed on attempt 1, retrying...", model)
                    time.sleep(1.5)
            logger.warning("Extraction model %s failed both attempts, trying next...", model)
        return None
    except Exception as e:
        logger.error("All extraction models failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Stage 3 — Community scam pattern similarity
# ---------------------------------------------------------------------------

def _community_similarity(text: str, reports: list) -> float:
    """
    Cosine similarity between this message's embedding and the nearest stored
    community scam report. Returns 0.0 when the model is unavailable.
    """
    model = _get_st_model()
    if not model or not reports:
        return 0.0

    try:
        import numpy as np
        pairs = [
            (r, json.loads(r["embedding_json"]))
            for r in reports
            if r.get("embedding_json")
        ]
        if not pairs:
            return 0.0

        q = model.encode([text])[0]
        q_norm = q / (np.linalg.norm(q) + 1e-9)

        best = 0.0
        for _, emb in pairs:
            v = np.array(emb, dtype="float32")
            v_norm = v / (np.linalg.norm(v) + 1e-9)
            best = max(best, float(np.dot(q_norm, v_norm)))
        return best
    except Exception as e:
        logger.warning("Community similarity failed: %s", e)
        return 0.0


# ---------------------------------------------------------------------------
# Stage 4 — Unified risk scoring
# ---------------------------------------------------------------------------

def _compute_risk(
    classifier_matches: list,
    url_results: list,
    community_sim: float,
    upi_lookalike: bool,
    llm_signals: list,
) -> tuple[int, list]:
    """
    Returns (risk_score 0-100, list_of_signal_strings).
    The SAME extracted features that produce this score are also used to
    populate the ledger entry — that is the 'same job' insight in code.
    """
    score = 0
    signals: list[str] = list(llm_signals)

    # Classifier contribution — up to 45 points
    if classifier_matches:
        top = classifier_matches[0]
        score += int(top.get("confidence", 0) * 0.45)
        signals.append(f"Scam typology: {top.get('label', '')}")

    # URL threat intel — up to 35 points total across multiple URLs
    for u in url_results:
        if u.get("verdict") == "flagged_dangerous":
            score += 30
            signals.append(f"Dangerous URL: {u.get('url', '')}")
        elif u.get("verdict") == "structurally_suspicious":
            score += 12
            signals.append(f"Suspicious URL: {u.get('url', '')}")

    # Community similarity — up to 20 points
    if community_sim > 0.85:
        score += 20
        signals.append(f"Matches community-reported scam (similarity {community_sim:.0%})")
    elif community_sim > 0.70:
        score += 10
        signals.append(f"Partial match to reported scam pattern ({community_sim:.0%})")

    # UPI lookalike — 15 points
    if upi_lookalike:
        score += 15
        signals.append("UPI handle spoofs a government or bank name")

    return min(score, 100), list(dict.fromkeys(signals))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Transaction Categorization
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "restock":    ["purchase", "bought", "stock", "supply", "supplier", "material",
                   "raw", "inventory", "replenish", "order", "dal", "rice", "cement",
                   "wheat", "sugar", "oil", "flour", "grain"],
    "rent":       ["rent", "lease", "shop rent", "office rent", "space"],
    "utilities":  ["electricity", "electric", "water", "internet", "broadband",
                   "bill", "utility", "phone bill", "gas", "fuel"],
    "wages":      ["salary", "wage", "wages", "staff", "worker", "employee",
                   "labor", "labour", "helper", "payment to"],
    "personal":   ["personal", "withdraw", "self", "family", "home", "draw"],
    "income":     ["sale", "sold", "received", "credited", "income", "revenue",
                   "payment received", "customer paid"],
}


def categorize_transaction(text: str, txn_direction: str | None = None) -> str:
    """
    Keyword-match the raw text against expense buckets.
    Returns: 'restock' | 'rent' | 'utilities' | 'wages' | 'personal' | 'income' | 'other'
    """
    lower = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    # Fallback based on direction
    if txn_direction == "inflow":
        return "income"
    return "other"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_message(
    raw_text: str,
    language: str = "english",
    channel: str = "web",
    sender_id: str = "web_user",
    sender_name: str | None = None,
) -> dict:
    """
    Run the full Pramaan pipeline on one message.

    Returns a unified result dict suitable for:
      • Direct API response to the frontend
      • Persistence in the SQLite DB via db.insert_message()
    """
    import db
    from normalize import normalize
    from classifier import classify
    from url_agent import extract_urls, check_url
    from translate import to_english_for_matching

    # Translate Indic script → English for pattern matching only.
    # URL strings are taken from raw_text to avoid any alteration.
    matching_text = to_english_for_matching(raw_text)

    # ── Stage 1: Fast Path ───────────────────────────────────────────────
    normalized = normalize(matching_text)
    clean_text = normalized["clean_text"]
    classification_result = classify(matching_text)
    matches = classification_result["matches"]
    panic_tags = classification_result["panic_tags"]

    urls = extract_urls(raw_text)
    url_results = [check_url(u) for u in urls]

    fast_txn = _extract_transaction_fast(raw_text)
    extraction_conf = fast_txn.pop("extraction_confidence", 0.5)

    classifier_conf = matches[0]["confidence"] / 100.0 if matches else 0.0
    use_llm = (classifier_conf < 0.65) or (extraction_conf < 0.5)

    # ── Stage 2: LLM Fallback ────────────────────────────────────────────
    llm_data = None
    classifier_stage = "fast_path"
    if use_llm:
        llm_data = _llm_extract(raw_text)
        if llm_data:
            classifier_stage = "llm_fallback"

    # Merge classification: LLM wins when available
    if llm_data:
        classification = llm_data.get("classification", "suspicious")
        confidence = float(llm_data.get("confidence") or 0.5)
    else:
        confidence = classifier_conf
        if confidence > 0.75:
            classification = "scam"
        elif confidence > 0.40:
            classification = "suspicious"
        else:
            classification = "legitimate"

    # Merge transaction data: LLM wins when it found a real transaction
    txn: dict = {}
    if llm_data and llm_data.get("is_real_transaction"):
        txn = {k: llm_data.get(k) for k in (
            "amount", "currency", "counterparty_name", "counterparty_phone",
            "txn_date", "purpose", "payment_method", "upi_reference", "txn_direction"
        )}
    elif fast_txn.get("amount"):
        txn = fast_txn

    # ── Stage 3: Verification ────────────────────────────────────────────
    community_reports = db.get_community_reports(limit=100)
    community_sim = _community_similarity(raw_text, community_reports)
    upi_lookalike = _has_upi_lookalike(raw_text)
    llm_signals = (llm_data or {}).get("risk_signals", [])

    # ── Stage 4: Unified Scoring ─────────────────────────────────────────
    risk_score, risk_signals = _compute_risk(
        matches, url_results, community_sim, upi_lookalike, llm_signals
    )

    explanation = (llm_data or {}).get("explanation", "")
    if not explanation and matches:
        explanation = matches[0].get("advice", "")

    # ── Auto-UPI Sync ────────────────────────────────────────────────────
    # If the user has enabled auto-monitoring, clean payments are confirmed
    # automatically (risk_score < 15) — no manual click needed.
    auto_sync = db.get_setting("auto_upi_sync", "false").lower() == "true"
    ledger_status = "n/a"
    if txn.get("amount"):
        if risk_score < 50:
            ledger_status = "confirmed" if auto_sync and risk_score < 15 else "draft"
        else:
            ledger_status = "flagged"

    # ── Scheme cross-check ───────────────────────────────────────────────
    scheme_result = None
    scheme_keywords = [
        "yojana", "kisan", "pm-kisan", "pm kisan", "installment", "kist",
        "ayushman", "awas", "scholarship", "dbt", "subsidy", "scheme",
    ]
    if any(w in clean_text for w in scheme_keywords):
        try:
            collection = _get_scheme_collection()
            if collection:
                from scheme_check import check_scheme_claim
                scheme_result = check_scheme_claim(clean_text, collection)
        except Exception as e:
            logger.warning("Scheme check failed: %s", e)

    category = categorize_transaction(raw_text, txn.get("txn_direction"))
    # ── Persist to DB ────────────────────────────────────────────────────
    db_record = {
        "channel":            channel,
        "sender_id":          sender_id,
        "sender_name":        sender_name,
        "raw_text":           raw_text,
        "language":           language,
        "classification":     classification,
        "classifier_stage":   classifier_stage,
        "confidence":         round(confidence, 4),
        "risk_score":         risk_score,
        "risk_signals":       risk_signals,
        "explanation":        explanation,
        "ledger_status":      ledger_status,
        "category":           category,
    }
    # Merge transaction fields into the DB record
    for k, v in txn.items():
        if v is not None:
            db_record[k] = v

    msg_id = db.insert_message(db_record)

    # ── Smart Inventory Update ───────────────────────────────────────────
    # If auto_upi_sync is on and we have a transaction, try to match
    # the text against known inventory items and adjust stock.
    if txn.get("amount") and ledger_status in ("confirmed", "draft"):
        try:
            match_and_update_stock(
                msg_id=msg_id,
                raw_text=raw_text,
                amount=txn["amount"],
                txn_direction=txn.get("txn_direction", "inflow"),
                cost_override=None,
            )
        except Exception as e:
            logger.warning("Stock auto-update failed: %s", e)

    # ── Return unified response ──────────────────────────────────────────
    return {
        "id":               msg_id,
        "raw_text":         raw_text,
        "classification":   classification,
        "confidence":       round(confidence, 4),
        "risk_score":       risk_score,
        "risk_signals":     risk_signals,
        "explanation":      explanation,
        "matches":          matches,
        "panic_tags":       panic_tags,
        "url_results":      url_results,
        "scheme_result":    scheme_result,
        "transaction":      txn if txn.get("amount") else None,
        "ledger_status":    ledger_status,
        "classifier_stage": classifier_stage,
        "community_match":  community_sim > 0.70,
    }


# ---------------------------------------------------------------------------
# Smart Inventory Auto-update
# ---------------------------------------------------------------------------

def match_and_update_stock(
    msg_id: int,
    raw_text: str,
    amount: float,
    txn_direction: str = "inflow",
    cost_override: float | None = None,
) -> dict | None:
    """
    Scan inventory items against the raw SMS/transaction text.
    If a match is found, adjust stock quantity based on the transaction amount
    and the item's cost price.
    Returns the matched inventory item dict, or None if no match found.
    """
    items = db.get_inventory()
    if not items:
        return None

    lower = raw_text.lower()
    matched_item = None
    for item in items:
        # Token matching: check if any word of item_name appears in the message
        tokens = item["item_name"].lower().split()
        if any(tok in lower for tok in tokens if len(tok) >= 3):
            matched_item = item
            break

    if not matched_item:
        return None

    cost = cost_override or matched_item.get("cost_price") or 1.0
    # Estimate quantity from amount / unit cost price (min 1 unit)
    qty = round(amount / cost, 2) if cost > 0 else 1.0

    # Purchase/outflow = stock comes IN; Sale/inflow = stock goes OUT
    if txn_direction == "outflow":
        delta = +qty   # Buying more stock
    else:
        delta = -qty   # Selling from stock

    updated = db.adjust_stock(matched_item["item_name"], delta)
    if updated:
        logger.info(
            "Smart inventory update: '%s' qty %s%s (msg_id=%s)",
            matched_item["item_name"],
            "+" if delta > 0 else "",
            round(delta, 2),
            msg_id,
        )
    return updated


# ---------------------------------------------------------------------------
# Phase 5 — AI Invoice Intelligence
# ---------------------------------------------------------------------------

_INVOICE_LLM_PROMPT = """\
You are an invoice parsing assistant.
Analyze this invoice/receipt text and extract the line-item products restocked or purchased.
Return ONLY a valid JSON list of objects — no preamble, no markdown fences, no explanation outside the JSON:

Text:
\"\"\"
{text}
\"\"\"

Return exactly this schema:
[
  {{
    "item_name": "clean descriptive product name, e.g. 'Basmati Rice', 'Moong Dal', 'Mustard Oil'",
    "quantity": number,
    "unit_price": number,
    "unit": "descriptive unit like 'kg', 'litre', 'bottle', 'unit' or similar"
  }}
]

Rules:
- Extract quantities and unit prices as float numbers.
- If quantity is missing but total and unit price exist, compute the quantity.
- Do not invent items. Only extract items clearly listed in the text.
"""


def _call_invoice_llm_model(client, model: str, prompt: str) -> list[dict] | None:
    """
    Try a single model call, return parsed list on success or None on failure.
    """
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        raw = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                raw += part.text
        raw = raw.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        parsed = json.loads(raw)
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed
        return None
    except Exception as e:
        logger.warning("Invoice LLM model %s failed: %s", model, e)
        return None


def _extract_invoice_items_regex(text: str) -> list[dict]:
    """
    Last-resort regex-based invoice line item extractor.
    Parses simple structured text invoices without LLM.
    Handles lines like: "Moong Dal   10 kg   110.00   1100.00"
    """
    items = []
    # Pattern: item name, then qty, then unit, then price
    line_re = re.compile(
        r'([A-Za-z][A-Za-z\s]{2,30?})\s+'   # item name (3–30 chars)
        r'(\d+(?:\.\d+)?)\s*'                # quantity
        r'(kg|litre|ltr|liters|l|bottle|pcs?|unit|pack|g|gram|ml|dozen)\.?\s+'
        r'(\d+(?:\.\d+)?)',                  # unit price
        re.IGNORECASE
    )
    seen = set()
    for match in line_re.finditer(text):
        name = match.group(1).strip().title()
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        try:
            items.append({
                "item_name": name,
                "quantity": float(match.group(2)),
                "unit": match.group(3).lower(),
                "unit_price": float(match.group(4)),
            })
        except ValueError:
            continue
    return items


def extract_invoice_items_llm(text: str) -> list[dict]:
    """
    Call Gemini model to parse line items from invoice text.
    Tries multiple models with retry on 503, falls back to regex parser.
    Returns a list of dicts with keys: item_name, quantity, unit_price, unit.
    """
    import time
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    
    if api_key and api_key not in ("your_gemini_api_key", ""):
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = _INVOICE_LLM_PROMPT.format(text=text[:2000])
            
            # Try models in priority order with retry
            model_chain = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash"]
            for model in model_chain:
                for attempt in range(2):  # 2 attempts per model
                    result = _call_invoice_llm_model(client, model, prompt)
                    if result is not None:
                        logger.info("Invoice LLM extracted %d items via %s", len(result), model)
                        return result
                    if attempt == 0:
                        logger.warning("Model %s returned empty/failed on attempt 1, retrying...", model)
                        time.sleep(1.5)
                logger.warning("Model %s exhausted, trying next model...", model)
        except Exception as e:
            logger.error("Invoice LLM extraction completely failed: %s", e)
    
    # Fallback: regex-based extractor
    logger.info("Falling back to regex invoice parser")
    regex_items = _extract_invoice_items_regex(text)
    if regex_items:
        logger.info("Regex invoice parser extracted %d items", len(regex_items))
    return regex_items


def sync_invoice_to_inventory(invoice_items: list[dict]) -> list[str]:
    """
    Synchronizes parsed invoice line items into the inventory table.
    Updates quantities for existing items, or creates new items.
    Returns a list of human-readable sync log entries.
    """
    import db
    sync_logs = []
    try:
        items = db.get_inventory()
        inventory_by_name = {it["item_name"].lower().strip(): it for it in items}

        for item in invoice_items:
            name = item.get("item_name", "").strip()
            if not name:
                continue
            qty = float(item.get("quantity") or 0)
            price = float(item.get("unit_price") or 0)
            unit = (item.get("unit") or "unit").strip()

            if qty <= 0:
                continue

            name_lower = name.lower()
            if name_lower in inventory_by_name:
                # Item exists, update quantity (restock) and cost price
                matched = inventory_by_name[name_lower]
                db.add_or_update_inventory_item(
                    item_name=matched["item_name"],
                    quantity=matched["quantity"] + qty,
                    cost_price=price,
                    unit=unit
                )
                sync_logs.append(f"Restocked {qty} {unit} of {matched['item_name']} (New Price: ₹{price}/unit)")
            else:
                # Item does not exist, insert new
                db.add_or_update_inventory_item(
                    item_name=name,
                    quantity=qty,
                    cost_price=price,
                    unit=unit
                )
                sync_logs.append(f"Created new product: {name} ({qty} {unit} @ ₹{price}/unit)")
    except Exception as e:
        logger.error("sync_invoice_to_inventory failed: %s", e)
        sync_logs.append(f"Error updating inventory: {str(e)}")
        
    return sync_logs
