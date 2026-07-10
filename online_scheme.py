"""
Online government scheme lookup and verification module.

When a user asks about a scheme that the local ChromaDB doesn't recognise
(i.e. the closest vector-search match has distance > UNKNOWN_DISTANCE_THRESHOLD),
this module:

  1. Searches the web using the Gemini API with Google Search grounding.
  2. Instructs the model to determine whether the scheme is a real, active
     Indian government scheme or a known scam/fake.
  3. Returns a structured dict in the same layout used by format_scheme_layout()
     in scheme_check.py so the frontend renders it identically.
  4. If the scheme is real and new, the caller can persist it to ChromaDB and
     to the seed JSON file for future use.

Security posture
----------------
* The Gemini model is instructed to source only from official government
  domains (gov.in, nic.in, india.gov.in) and reject unofficial/blog sources.
* If the model reports is_real=false (or returns something that doesn't parse),
  the scheme is returned as a ⚠️ FAKE flag card, NOT added to the DB.
* No user-submitted content is ever sent to Gemini as a URL to open -- only
  the extracted scheme *name* (a short text string) is passed as a query.
"""

import os
import json
import re
import logging

logger = logging.getLogger(__name__)

# Requires: pip install google-genai
try:
    from google import genai
    from google.genai import types as genai_types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logger.warning("google-genai not installed -- online scheme lookup disabled.")

# Distance threshold: ChromaDB L2-style cosine distance above which we
# consider the query to not have matched any known scheme.
UNKNOWN_DISTANCE_THRESHOLD = 1.0

_PROMPT_TEMPLATE = """
You are a factual Indian government scheme verification assistant.
A user is asking about: "{scheme_query}"

Your task:
1. Search the web and determine if this is a REAL, currently active Indian government scheme.
2. Only accept information from official government sources: gov.in, nic.in, india.gov.in, or official ministry websites.
3. Return a JSON object (and ONLY a JSON object, no extra text or markdown fences) with exactly these keys:

{{
  "is_real": true or false,
  "scheme_name": "Short official scheme name (e.g. PM-KISAN)",
  "full_name": "Full official name of the scheme",
  "benefit": "What the scheme provides to beneficiaries",
  "eligibility": "Who is eligible",
  "location": "Any geographic restriction, or null if nationwide",
  "required_documents": "Comma-separated list of documents needed",
  "contact_info": "Helpline number or official contact, or null",
  "real_process": "How the scheme actually works -- what steps are real vs what scammers typically fake",
  "official_source": "Official website URL (gov.in domain only)",
  "fake_reason": "If is_real is false, explain why this scheme is fake or a scam. Otherwise null."
}}

Rules:
- If you cannot find credible official information, set is_real to false.
- NEVER invent or hallucinate scheme details. If uncertain about any field, set it to null.
- If the scheme sounds like a scam (e.g. \"free laptop\", \"PM cash prize\", \"WhatsApp lottery\"), set is_real to false and explain in fake_reason.
"""


def lookup_scheme_online(scheme_query: str) -> dict | None:
    """
    Perform an online Gemini-grounded search for a government scheme.

    Returns a dict with the scheme layout (matching format_scheme_layout()
    output), or None if the API key is not configured or a network error
    occurs. The dict always includes an 'is_real' key.
    """
    if not _GENAI_AVAILABLE:
        return None

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key":
        logger.warning("GEMINI_API_KEY not set -- skipping online scheme lookup.")
        return None

    try:
        client = genai.Client(api_key=api_key)
        prompt = _PROMPT_TEMPLATE.format(scheme_query=scheme_query[:200])
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
            ),
        )
        # Extract text from the first candidate
        raw = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                raw += part.text
        raw = raw.strip()

        # Strip markdown code fences if present (e.g. ```json ... ```)
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)
        return _normalise_response(data)

    except json.JSONDecodeError as e:
        logger.error("Gemini returned non-JSON for scheme query '%s': %s", scheme_query, e)
        return None
    except Exception as e:
        logger.error("Online scheme lookup failed for '%s': %s", scheme_query, e)
        return None


def _normalise_response(data: dict) -> dict:
    """
    Normalise the raw Gemini JSON into the same layout as
    format_scheme_layout() so the frontend renders it identically.
    Adds is_real and is_online_result flags so callers know the provenance.
    """
    is_real = bool(data.get("is_real", False))

    if not is_real:
        fake_reason = data.get("fake_reason") or "This scheme could not be verified as an official Indian government scheme."
        scheme_name = data.get("scheme_name") or "Unrecognised Scheme"
        return {
            "is_real": False,
            "is_online_result": True,
            "scheme_name": f"⚠️ Not a real scheme: {scheme_name}",
            "eligibility": "N/A — this scheme does not appear to be real.",
            "location": "N/A",
            "required_documents": "N/A",
            "contact_info": "If you received this as a message, treat it as a scam attempt.",
            "real_process": fake_reason,
            "official_source": "N/A",
        }

    return {
        "is_real": True,
        "is_online_result": True,
        "scheme_name": data.get("scheme_name") or "Unknown",
        "full_name": data.get("full_name") or "",
        "benefit": data.get("benefit") or "",
        "eligibility": data.get("eligibility") or "Not mentioned",
        "location": data.get("location") or "No location restriction -- apply online only",
        "required_documents": data.get("required_documents") or "Not mentioned",
        "contact_info": data.get("contact_info") or f"Visit official website: {data.get('official_source', 'N/A')}",
        "real_process": data.get("real_process") or "",
        "official_source": data.get("official_source") or "N/A",
    }
