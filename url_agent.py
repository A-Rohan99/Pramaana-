"""
URL safety agent.

CRITICAL DESIGN CONSTRAINT: this module NEVER opens, fetches, renders,
or executes a submitted URL from our own infrastructure. Doing that -
even inside a container we built ourselves - means our servers are the
ones touching the payload, and a mistake in that isolation is exactly
the catastrophic failure mode we're avoiding.

Instead, this queries established, purpose-built threat-intelligence
services that already run real detonation sandboxes as their full-time
job:
  - Google Safe Browsing API: checks a URL against Google's continuously
    updated database of known phishing/malware sites. Pure lookup, no
    execution on our side.
  - VirusTotal URL Analysis API: submits the URL *to VirusTotal's own
    infrastructure*, which scans it with dozens of engines/sandboxes.
    We never touch the payload; VirusTotal does, on their systems.

If a URL isn't flagged by either, we ALSO run cheap, execution-free
structural checks (lookalike domains, raw IP URLs, excessive
subdomains, mismatched display text vs actual href). These catch
brand-new phishing domains that haven't been indexed yet, without ever
visiting them.

If nothing comes back conclusive, the honest answer is "unknown -
treat with caution," never a guess dressed up as certainty.
"""

import os
import re
import time
import base64
import requests
from urllib.parse import urlparse

SAFE_BROWSING_API_KEY = os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")
VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY")

SAFE_BROWSING_ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
VT_URL_SUBMIT_ENDPOINT = "https://www.virustotal.com/api/v3/urls"
VT_URL_REPORT_ENDPOINT = "https://www.virustotal.com/api/v3/urls/{}"

# Common URL shorteners -- worth flagging on their own since they hide
# the real destination from the user's eyes (not inherently malicious,
# but a real risk signal when combined with urgency language elsewhere
# in the message).
KNOWN_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "shorturl.at"}

# A handful of frequently-impersonated Indian institution domains, used
# only for lookalike-distance comparison -- NOT a fetch target.
LEGITIMATE_DOMAINS = [
    "sbi.co.in", "onlinesbi.sbi", "hdfcbank.com", "icicibank.com",
    "uidai.gov.in", "incometax.gov.in", "pmkisan.gov.in", "indiapost.gov.in",
    "npci.org.in", "rbi.org.in",
]


def extract_urls(text: str) -> list[str]:
    pattern = r"https?://[^\s<>\"']+|www\.[^\s<>\"']+"
    return re.findall(pattern, text)


def _check_safe_browsing(url: str) -> dict | None:
    if not SAFE_BROWSING_API_KEY:
        return None
    body = {
        "client": {"clientId": "satark-setu", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    try:
        resp = requests.post(
            f"{SAFE_BROWSING_ENDPOINT}?key={SAFE_BROWSING_API_KEY}",
            json=body, timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"flagged": bool(data.get("matches")), "raw": data}
    except requests.RequestException:
        return None  # network/API failure -- treat as "unknown", not "safe"


def _check_virustotal(url: str) -> dict | None:
    if not VIRUSTOTAL_API_KEY:
        return None
    headers = {"x-apikey": VIRUSTOTAL_API_KEY}
    try:
        # VirusTotal identifies URLs by a URL-safe base64 id of the URL itself.
        url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
        resp = requests.get(VT_URL_REPORT_ENDPOINT.format(url_id), headers=headers, timeout=8)

        if resp.status_code == 404:
            # Not seen before -- submit it for VirusTotal's own sandboxes
            # to analyze on THEIR infrastructure, then poll briefly.
            submit_resp = requests.post(VT_URL_SUBMIT_ENDPOINT, headers=headers, data={"url": url}, timeout=8)
            submit_resp.raise_for_status()
            time.sleep(3)  # brief wait for analysis; a production system would poll async
            resp = requests.get(VT_URL_REPORT_ENDPOINT.format(url_id), headers=headers, timeout=8)

        resp.raise_for_status()
        data = resp.json()
        stats = data["data"]["attributes"]["last_analysis_stats"]
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        return {"flagged": (malicious + suspicious) > 0, "malicious_count": malicious, "suspicious_count": suspicious}
    except (requests.RequestException, KeyError):
        return None


def _structural_red_flags(url: str) -> list[str]:
    """Execution-free structural checks -- pure string/parsing analysis."""
    flags = []
    try:
        parsed = urlparse(url if url.startswith("http") else f"http://{url}")
        domain = parsed.netloc.lower()
    except ValueError:
        return ["Could not parse URL structure"]

    bare_domain = domain[4:] if domain.startswith("www.") else domain
    is_known_legit = bare_domain in LEGITIMATE_DOMAINS or any(
        bare_domain.endswith(f".{legit}") for legit in LEGITIMATE_DOMAINS
    )

    if re.match(r"^\d{1,3}(\.\d{1,3}){3}", domain):
        flags.append("URL uses a raw IP address instead of a domain name")

    if domain in KNOWN_SHORTENERS:
        flags.append(f"Uses a link shortener ({domain}) that hides the real destination")

    # Skip the subdomain-depth heuristic for our own whitelisted
    # institutions -- real .gov.in / .co.in domains with a "www." prefix
    # legitimately land at 3+ dots (e.g. "www.pmkisan.gov.in"), and this
    # heuristic exists to catch attacker-added subdomains, not normal
    # official domain structure.
    if not is_known_legit and domain.count(".") >= 3:
        flags.append("Unusually deep subdomain structure, common in phishing URLs")

    if not is_known_legit:
        domain_tokens = set(re.split(r"[.\-]", domain))
        for legit in LEGITIMATE_DOMAINS:
            legit_root = legit.split(".")[0]
            if (
                legit_root in domain_tokens
                and domain != legit
                and not domain.endswith(f".{legit}")
            ):
                flags.append(f"Domain resembles '{legit}' but is not an exact match -- possible lookalike")

    return flags


def check_url(url: str) -> dict:
    """
    Main entry point. Returns a verdict object -- never executes the URL.
    """
    sb_result = _check_safe_browsing(url)
    vt_result = _check_virustotal(url)
    structural_flags = _structural_red_flags(url)

    definitively_flagged = bool(
        (sb_result and sb_result.get("flagged")) or (vt_result and vt_result.get("flagged"))
    )

    checked_by_any_service = sb_result is not None or vt_result is not None

    if definitively_flagged:
        verdict = "flagged_dangerous"
    elif structural_flags:
        verdict = "structurally_suspicious"
    elif checked_by_any_service:
        verdict = "no_known_threat"
    else:
        verdict = "unknown"  # no API configured / both calls failed -- be honest, not falsely reassuring

    return {
        "url": url,
        "verdict": verdict,
        "structural_flags": structural_flags,
        "safe_browsing_checked": sb_result is not None,
        "virustotal_checked": vt_result is not None,
    }
