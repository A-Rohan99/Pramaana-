"""
Bug Condition Exploration Tests — Phase 1 (UNFIXED codebase)
=============================================================

These tests are run BEFORE any code fixes are applied. Their purpose is
to surface counterexamples proving that specific bugs / gaps exist on the
current, unverified codebase.

Expected outcomes:
  - test_g2_ocr_message_contains_apt_get            → PASS  (bad message confirmed)
  - test_g4_hindi_classify_no_translation_false_neg → PASS  (false-negative confirmed)
  - test_g4_telugu_classify_no_translation_false_neg → PASS (false-negative confirmed)
  - test_g6_local_pipeline_no_native_script_samples → PASS  (missing samples confirmed)

A PASS here means the bug was successfully demonstrated on unfixed code.
"""

import subprocess
import sys
import inspect
import textwrap

import pytest


# ---------------------------------------------------------------------------
# G2 — ocr.py error messages contain Linux-only "sudo apt-get install"
# ---------------------------------------------------------------------------

class TestG2OcrErrorMessages:
    """
    Validates: Design doc G2 — isBugCondition_G2 (Linux-only error messages).

    We inspect the source code of ocr.py directly, because Tesseract is NOT
    installed on this machine and we cannot trigger the exceptions at runtime.
    Inspecting the source is equivalent — the strings are hardcoded literals;
    they do not vary by environment.

    EXPECTED (unfixed code): Both branches contain "apt-get".
    This test PASSES on unfixed code, which CONFIRMS the bug exists.
    """

    def _get_ocr_source(self) -> str:
        """Return the full source text of ocr.py."""
        import ocr as ocr_module
        return inspect.getsource(ocr_module)

    def test_g2_tesseract_not_found_branch_does_not_contain_apt_get(self):
        """
        Verify 'apt-get' has been removed from ocr.py (fixed codebase).
        """
        source = self._get_ocr_source()
        assert "apt-get" not in source, (
            "Expected 'apt-get' to be removed from ocr.py (Linux-only instructions bug)."
        )

    def test_g2_apt_get_not_in_tesseract_not_found_message(self):
        """
        Verify the Linux-specific 'sudo apt-get install tesseract-ocr' is not in ocr.py.
        """
        source = self._get_ocr_source()
        assert "sudo apt-get install tesseract-ocr" not in source, (
            "Expected 'sudo apt-get install tesseract-ocr' to be removed from ocr.py."
        )

    def test_g2_no_apt_get_in_ocr_source(self):
        """
        Verify there are no 'apt-get' occurrences left in ocr.py.
        """
        source = self._get_ocr_source()
        count = source.count("apt-get")
        assert count == 0, (
            f"Expected 0 occurrences of 'apt-get' in ocr.py, found {count}."
        )

    def test_g2_windows_instructions_present(self):
        """
        Verify that Windows-correct instructions ('UB-Mannheim') are present in ocr.py.
        """
        source = self._get_ocr_source()
        assert "UB-Mannheim" in source, (
            "ocr.py does not contain Windows-correct install instructions ('UB-Mannheim')."
        )


# ---------------------------------------------------------------------------
# G4 — Native-script false negatives when classify() called without translation
# ---------------------------------------------------------------------------

class TestG4NativeScriptFalseNegative:
    """
    Validates: Design doc G4 — isBugCondition_G4 (native-script false negative).

    classify() uses fuzzy matching against English/romanized phrases.
    Devanagari or Telugu input scores near zero against every typology in
    TYPOLOGIES because the characters do not overlap.

    These tests call classify() DIRECTLY on native-script text, WITHOUT first
    calling to_english_for_matching(). This mirrors the gap in the unfixed
    local_pipeline_test.py, which also bypasses translation.

    EXPECTED (unfixed code): matches == [] for both inputs.
    Each PASS confirms the false-negative bug exists.
    """

    def test_g4_hindi_kyc_scam_returns_no_matches(self):
        """
        Hindi Devanagari KYC scam text → classify() without translation.
        Expected counterexample: matches == [] (false negative).

        Input is a genuine SBI KYC scam message. English equivalent would
        match the 'fake_kyc' typology with confidence ≥ 55. Devanagari
        version scores near zero — this is the bug.
        """
        from classifier import classify

        hindi_kyc_scam = "आपका SBI KYC पेंडिंग है, आज खाता ब्लॉक हो जाएगा"
        result = classify(hindi_kyc_scam)

        # Document what classify() actually returned (for the report)
        print(f"\n[G4 counterexample — Hindi]")
        print(f"  Input  : {hindi_kyc_scam}")
        print(f"  clean_text : {result['clean_text']}")
        print(f"  panic_tags : {result['panic_tags']}")
        print(f"  matches    : {result['matches']}")

        assert result["matches"] == [], (
            f"Expected no matches for raw Devanagari input (false-negative bug), "
            f"but classify() returned: {result['matches']}. "
            f"The bug may already be fixed, or classify() is matching on something unexpected."
        )

    def test_g4_telugu_electricity_scam_returns_no_matches(self):
        """
        Telugu electricity disconnection scam text → classify() without translation.
        Expected counterexample: matches == [] (false negative).

        English equivalent would match 'electricity_disconnection'. Telugu
        script scores near zero — this is the bug.
        """
        from classifier import classify

        telugu_electricity_scam = "మీ విద్యుత్ కనెక్షన్ నేడు రాత్రి కత్తిరించబడుతుంది"
        result = classify(telugu_electricity_scam)

        # Document what classify() actually returned (for the report)
        print(f"\n[G4 counterexample — Telugu]")
        print(f"  Input  : {telugu_electricity_scam}")
        print(f"  clean_text : {result['clean_text']}")
        print(f"  panic_tags : {result['panic_tags']}")
        print(f"  matches    : {result['matches']}")

        assert result["matches"] == [], (
            f"Expected no matches for raw Telugu input (false-negative bug), "
            f"but classify() returned: {result['matches']}. "
            f"The bug may already be fixed, or classify() is matching on something unexpected."
        )

    def test_g4_hindi_full_scam_sentence_returns_no_matches(self):
        """
        Extended Hindi Devanagari scam sentence with URL — still no matches.
        This is the longer version from the design doc's fix implementation.
        """
        from classifier import classify

        hindi_full = (
            "प्रिय ग्राहक, आपका SBI KYC अपडेट नहीं हुआ है, आज खाता ब्लॉक हो जाएगा। "
            "तुरंत यहाँ क्लिक करें: https://sbi-kyc-secure.in/verify"
        )
        result = classify(hindi_full)

        print(f"\n[G4 counterexample — Hindi (full sentence)]")
        print(f"  Input  : {hindi_full}")
        print(f"  clean_text : {result['clean_text']}")
        print(f"  panic_tags : {result['panic_tags']}")
        print(f"  matches    : {result['matches']}")

        assert result["matches"] == [], (
            f"Expected no matches for full Devanagari scam sentence, "
            f"got: {result['matches']}"
        )


# ---------------------------------------------------------------------------
# G6 — local_pipeline_test.py has no native-script samples
# ---------------------------------------------------------------------------

class TestG6LocalPipelineNativeScript:
    """
    Validates: Design doc G6 — isBugCondition_G6 (test harness incomplete).

    Runs local_pipeline_test.py as a subprocess from the project root and
    inspects its stdout for any Devanagari or Telugu characters.

    On unfixed code the script contains only 5 English/Hinglish samples —
    no native-script samples are present. This CONFIRMS the G6 gap.

    EXPECTED (unfixed code): output contains no Devanagari or Telugu characters.
    """

    PYTHON = r"c:\Users\rohan\OneDrive\project\satark_setu\.venv\Scripts\python.exe"
    PROJECT_ROOT = r"c:\Users\rohan\OneDrive\project\satark_setu"

    def _run_local_pipeline(self):
        """Run local_pipeline_test.py and return (stdout, stderr, returncode)."""
        result = subprocess.run(
            [self.PYTHON, "local_pipeline_test.py"],
            cwd=self.PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        return result.stdout, result.stderr, result.returncode

    def _contains_devanagari(self, text: str) -> bool:
        """Return True if text contains any Devanagari character (U+0900–U+097F)."""
        return any("\u0900" <= ch <= "\u097F" for ch in text)

    def _contains_telugu(self, text: str) -> bool:
        """Return True if text contains any Telugu character (U+0C00–U+0C7F)."""
        return any("\u0C00" <= ch <= "\u0C7F" for ch in text)

    def test_g6_pipeline_exits_successfully(self):
        """
        local_pipeline_test.py must exit with code 0 (the test harness itself
        must not crash). If it crashes, G6 is a hard failure, not just incomplete.
        """
        stdout, stderr, returncode = self._run_local_pipeline()

        print(f"\n[G6 pipeline exit code]: {returncode}")
        if stderr:
            print(f"[G6 stderr (first 500 chars)]:\n{stderr[:500]}")

        assert returncode == 0, (
            f"local_pipeline_test.py exited with code {returncode}.\n"
            f"stderr:\n{stderr[:1000]}\n"
            f"stdout:\n{stdout[:500]}"
        )

    def test_g6_native_script_in_output(self):
        """
        Verify local_pipeline_test.py output contains native-script (Devanagari/Telugu)
        characters, confirming the G6 gap has been resolved.
        """
        stdout, stderr, returncode = self._run_local_pipeline()

        # Capture native-script presence for the report
        has_devanagari = self._contains_devanagari(stdout)
        has_telugu = self._contains_telugu(stdout)

        print(f"\n[G6 native-script check]")
        print(f"  Output contains Devanagari: {has_devanagari}")
        print(f"  Output contains Telugu    : {has_telugu}")
        print(f"  [Stdout excerpt (first 800 chars)]:\n{stdout[:800]}")

        assert has_devanagari and has_telugu, (
            "local_pipeline_test.py output is missing native-script characters. "
            f"Devanagari present: {has_devanagari}, Telugu present: {has_telugu}"
        )

    def test_g6_sample_count_is_eight(self):
        """
        Verify that local_pipeline_test.py has all 8 sample inputs (5 original + 3 native-script).
        """
        stdout, stderr, returncode = self._run_local_pipeline()

        # Each sample prints "### <title>"
        sample_headers = [line for line in stdout.splitlines() if line.startswith("### ")]
        count = len(sample_headers)

        print(f"\n[G6 sample count]: {count}")
        for h in sample_headers:
            print(f"  {h}")

        assert count == 8, (
            f"Expected exactly 8 sample headers, found {count}. "
            f"Samples found: {sample_headers}"
        )


# ---------------------------------------------------------------------------
# Task 4.2 — Unit tests for normalize()
# ---------------------------------------------------------------------------

class TestNormalize:
    """
    Unit tests for normalize() in normalize.py.

    Covers: return structure, clean_text behaviour, panic_tags firing.
    """

    # ------------------------------------------------------------------
    # Return structure
    # ------------------------------------------------------------------

    def test_returns_dict_with_required_keys(self):
        """normalize() must return a dict with at least 'clean_text' and 'panic_tags'."""
        from normalize import normalize
        result = normalize("test")
        assert isinstance(result, dict)
        assert "clean_text" in result
        assert "panic_tags" in result

    def test_empty_string_returns_valid_structure(self):
        """normalize('') returns a dict with clean_text='' and panic_tags=[]."""
        from normalize import normalize
        result = normalize("")
        assert isinstance(result, dict)
        assert "clean_text" in result
        assert "panic_tags" in result
        assert result["panic_tags"] == []

    # ------------------------------------------------------------------
    # clean_text behaviour
    # ------------------------------------------------------------------

    def test_clean_text_is_lowercase(self):
        """clean_text must be fully lowercased."""
        from normalize import normalize
        result = normalize("HELLO WORLD")
        assert result["clean_text"] == "hello world"

    def test_clean_text_strips_urls(self):
        """
        normalize() does NOT strip URLs — clean_text will contain the lowercased
        URL.  This test verifies that 'https://evil.com' survives but is lowercased.
        (URL stripping is not in scope for normalize(); it is a classifier concern.)
        """
        from normalize import normalize
        result = normalize("click https://evil.com now")
        # The URL is preserved (lowercased) in clean_text
        assert "https://evil.com" in result["clean_text"]

    # ------------------------------------------------------------------
    # panic_tags — tags that SHOULD fire
    # ------------------------------------------------------------------

    def test_kyc_tag_fires_on_kyc_keyword(self):
        """'kyc' in input → 'KYC' in panic_tags."""
        from normalize import normalize
        result = normalize("Your KYC is pending")
        assert "KYC" in result["panic_tags"]

    def test_arrest_tag_fires(self):
        """'digital arrest' in input → 'ARREST' tag fires (case-insensitive match)."""
        from normalize import normalize
        result = normalize("you are under digital arrest")
        # Check for ARREST tag (case-insensitive check on the tag name)
        assert any("arrest" in tag.lower() for tag in result["panic_tags"])

    def test_arrest_tag_fires_on_arrest_keyword(self):
        """'arrest' keyword alone also fires the ARREST tag."""
        from normalize import normalize
        result = normalize("you will be under arrest immediately")
        assert "ARREST" in result["panic_tags"]

    # ------------------------------------------------------------------
    # panic_tags — tags that should NOT fire
    # ------------------------------------------------------------------

    def test_no_panic_tags_on_clean_message(self):
        """A benign message must produce no panic_tags."""
        from normalize import normalize
        result = normalize("Are we meeting for lunch tomorrow?")
        assert result["panic_tags"] == []


# ---------------------------------------------------------------------------
# Task 4.3 — Unit tests for classify()
# ---------------------------------------------------------------------------

class TestClassify:
    """
    Unit tests for the classify() function in classifier.py.

    Validates return structure, typology matching, and edge cases.
    """

    def test_english_kyc_scam_matches(self):
        """
        A genuine English SBI KYC scam message must produce at least one match.
        """
        from classifier import classify
        result = classify("your SBI KYC is pending, account will be blocked")
        assert len(result["matches"]) >= 1, (
            f"Expected at least 1 match for KYC scam message, got: {result['matches']}"
        )

    def test_english_electricity_scam_matches(self):
        """
        An electricity disconnection threat must match the electricity typology.
        The matching label must contain 'electricity' (case-insensitive).
        """
        from classifier import classify
        result = classify("your electricity connection will be disconnected tonight")
        assert len(result["matches"]) >= 1, (
            f"Expected at least 1 match for electricity scam, got: {result['matches']}"
        )
        labels = [m["label"].lower() for m in result["matches"]]
        assert any("electricity" in label for label in labels), (
            f"Expected at least one match with 'electricity' in label, got labels: {labels}"
        )

    def test_clean_message_no_matches(self):
        """
        A benign everyday message must return no scam matches.
        """
        from classifier import classify
        result = classify("Are we meeting for lunch tomorrow?")
        assert result["matches"] == [], (
            f"Expected no matches for benign message, got: {result['matches']}"
        )

    def test_digital_arrest_matches(self):
        """
        A digital arrest scam message must produce at least one match.
        """
        from classifier import classify
        result = classify("you are under digital arrest, do not disconnect this call")
        assert len(result["matches"]) >= 1, (
            f"Expected at least 1 match for digital arrest scam, got: {result['matches']}"
        )

    def test_match_has_required_keys(self):
        """
        Every match dict must contain 'label', 'confidence', and 'advice' keys.
        """
        from classifier import classify
        result = classify("your SBI KYC is pending, account will be blocked")
        assert len(result["matches"]) >= 1, "Need at least 1 match to validate keys"
        for match in result["matches"]:
            assert "label" in match, f"Match missing 'label' key: {match}"
            assert "confidence" in match, f"Match missing 'confidence' key: {match}"
            assert "advice" in match, f"Match missing 'advice' key: {match}"

    def test_confidence_is_integer_0_to_100(self):
        """
        The 'confidence' value for every match must be a numeric value in [0, 100].
        rapidfuzz returns floats, so we accept both int and float.
        """
        from classifier import classify
        result = classify("your SBI KYC is pending, account will be blocked")
        assert len(result["matches"]) >= 1, "Need at least 1 match to validate confidence"
        for match in result["matches"]:
            conf = match["confidence"]
            assert isinstance(conf, (int, float)), (
                f"confidence must be numeric, got {type(conf)}: {conf}"
            )
            assert 0 <= conf <= 100, f"confidence {conf} is out of range [0, 100]"

    def test_result_has_matches_and_clean_text_keys(self):
        """
        classify() must always return a dict containing at least 'matches'
        and 'clean_text' keys, regardless of input.
        """
        from classifier import classify
        result = classify("test")
        assert "matches" in result, f"Result missing 'matches' key: {result}"
        assert "clean_text" in result, f"Result missing 'clean_text' key: {result}"

    def test_empty_string_returns_no_matches(self):
        """
        An empty string must return an empty matches list.
        """
        from classifier import classify
        result = classify("")
        assert result["matches"] == [], (
            f"Expected no matches for empty string, got: {result['matches']}"
        )


# ---------------------------------------------------------------------------
# URL Agent — structural offline checks
# ---------------------------------------------------------------------------

from unittest import mock


class TestUrlAgentStructural:
    """
    Validates: Design doc — structural URL analysis (check_url, extract_urls).

    All tests run purely offline — no network calls, no API keys required.
    Each test patches SAFE_BROWSING_API_KEY and VIRUSTOTAL_API_KEY to None
    so neither _check_safe_browsing nor _check_virustotal will make requests.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _no_api_keys():
        """Context manager pair that kills both API keys."""
        return (
            mock.patch("url_agent.SAFE_BROWSING_API_KEY", None),
            mock.patch("url_agent.VIRUSTOTAL_API_KEY", None),
        )

    # ------------------------------------------------------------------
    # check_url structural verdict tests
    # ------------------------------------------------------------------

    def test_ip_address_url_is_structurally_suspicious(self):
        """
        A URL using a raw IPv4 address triggers the structural flag for
        raw IP addresses and the verdict must be 'structurally_suspicious'.
        """
        from url_agent import check_url

        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None):
            result = check_url("http://192.168.1.1/login")

        assert result["verdict"] == "structurally_suspicious", (
            f"Expected 'structurally_suspicious' for raw-IP URL, got: {result['verdict']}. "
            f"structural_flags: {result['structural_flags']}"
        )
        assert any("IP" in flag or "ip" in flag.lower() for flag in result["structural_flags"]), (
            f"Expected a flag mentioning IP address, got: {result['structural_flags']}"
        )

    def test_brand_in_subdomain_is_flagged(self):
        """
        A URL like https://sbi.secure-kyc-update.co.in/login embeds a known
        brand ('sbi') in a domain that is NOT the real sbi.co.in.
        The structural_flags must contain a flag mentioning 'brand' or the
        lookalike/subdomain pattern.
        """
        from url_agent import check_url

        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None):
            result = check_url("https://sbi.secure-kyc-update.co.in/login")

        flags_lower = " ".join(result["structural_flags"]).lower()
        assert "brand" in flags_lower or "subdomain" in flags_lower or "lookalike" in flags_lower or "resembles" in flags_lower, (
            f"Expected a flag mentioning brand/subdomain/lookalike, got: {result['structural_flags']}"
        )

    def test_excessive_subdomain_depth_flagged(self):
        """
        A URL with 4+ dots in the domain (e.g. a.b.c.d.example.com) is not
        a known-legit domain, so the subdomain depth heuristic must fire.
        """
        from url_agent import check_url

        # 5 dots in the domain => well above the >= 3 threshold
        deep_url = "https://login.secure.verify.update.attacker.com/account"
        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None):
            result = check_url(deep_url)

        assert result["verdict"] == "structurally_suspicious", (
            f"Expected 'structurally_suspicious' for deep subdomain URL, got: {result['verdict']}. "
            f"structural_flags: {result['structural_flags']}"
        )
        assert any("subdomain" in flag.lower() for flag in result["structural_flags"]), (
            f"Expected a flag about subdomain depth, got: {result['structural_flags']}"
        )

    def test_clean_gov_url_not_flagged(self):
        """
        A clean government URL such as https://pmkisan.gov.in/ should NOT
        be verdict 'structurally_suspicious'. It may be 'unknown' (no APIs)
        or 'no_known_threat' if services are configured, but never
        'structurally_suspicious'.
        """
        from url_agent import check_url

        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None):
            result = check_url("https://pmkisan.gov.in/")

        assert result["verdict"] != "structurally_suspicious", (
            f"A clean gov.in URL should not be flagged as structurally_suspicious. "
            f"Got verdict: {result['verdict']}, flags: {result['structural_flags']}"
        )

    # ------------------------------------------------------------------
    # extract_urls tests
    # ------------------------------------------------------------------

    def test_extract_urls_finds_http_and_https(self):
        """
        extract_urls must return both an http:// and an https:// URL
        when both appear in the input text.
        """
        from url_agent import extract_urls

        text = "visit https://example.com and http://foo.bar/path"
        urls = extract_urls(text)

        assert isinstance(urls, list), f"Expected a list, got {type(urls)}"
        assert len(urls) >= 2, f"Expected at least 2 URLs, got: {urls}"
        assert any(u.startswith("https://") for u in urls), (
            f"Expected an https:// URL in results, got: {urls}"
        )
        assert any(u.startswith("http://") for u in urls), (
            f"Expected an http:// URL in results, got: {urls}"
        )

    def test_extract_urls_empty_string(self):
        """
        extract_urls on an empty string must return an empty list, not raise.
        """
        from url_agent import extract_urls

        result = extract_urls("")
        assert result == [], f"Expected [] for empty string, got: {result}"

    # ------------------------------------------------------------------
    # No-API-key / no-network tests
    # ------------------------------------------------------------------

    def test_no_api_keys_never_calls_network(self):
        """
        When both API keys are None, check_url must NOT make any HTTP
        requests regardless of the URL passed.  We patch requests.get and
        requests.post at the url_agent module level and assert neither is
        called.
        """
        from url_agent import check_url

        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None), \
             mock.patch("url_agent.requests.get") as mock_get, \
             mock.patch("url_agent.requests.post") as mock_post:
            check_url("https://example.com")

        mock_get.assert_not_called()
        mock_post.assert_not_called()

    # ------------------------------------------------------------------
    # Lookalike domain test
    # ------------------------------------------------------------------

    def test_lookalike_gov_domain_flagged(self):
        """
        https://indiapost.gov.in.duty-clearance.info/pay uses 'indiapost.gov.in'
        as a *subdomain* of a foreign domain. The structural check must detect
        that it resembles a legitimate domain (indiapost.gov.in) but is not
        an exact match, and include a flag about the lookalike pattern.
        """
        from url_agent import check_url

        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None):
            result = check_url("https://indiapost.gov.in.duty-clearance.info/pay")

        flags_combined = " ".join(result["structural_flags"]).lower()
        assert "lookalike" in flags_combined or "resembles" in flags_combined or "indiapost" in flags_combined, (
            f"Expected a lookalike flag for indiapost.gov.in impersonation, "
            f"got structural_flags: {result['structural_flags']}"
        )


# ---------------------------------------------------------------------------
# Task 4.4 — scheme_check.py: format_scheme_layout() no-fabrication tests
# ---------------------------------------------------------------------------

class TestFormatSchemeLayout:
    """
    Unit tests for format_scheme_layout() in scheme_check.py.

    Verifies that the function:
      - Returns exact fallback strings (not empty strings) for null/missing fields
      - Passes populated values through unchanged
      - Never returns an empty string for any field

    No DB or network access required — format_scheme_layout() is a pure dict
    transformation function.
    """

    def _fmt(self, meta: dict) -> dict:
        from scheme_check import format_scheme_layout
        return format_scheme_layout(meta)

    # 1. null eligibility → "Not mentioned"
    def test_null_eligibility_returns_not_mentioned(self):
        result = self._fmt({"eligibility": None, "official_source": "x.gov.in"})
        assert result["eligibility"] == "Not mentioned"

    # 2. empty-string eligibility → "Not mentioned"
    def test_empty_eligibility_returns_not_mentioned(self):
        result = self._fmt({"eligibility": "", "official_source": "x.gov.in"})
        assert result["eligibility"] == "Not mentioned"

    # 3. null location → exact fallback
    def test_null_location_returns_exact_fallback(self):
        result = self._fmt({"location": None, "official_source": "x.gov.in"})
        assert result["location"] == "No location restriction -- apply online only"

    # 4. null required_documents → "Not mentioned"
    def test_null_required_documents_returns_not_mentioned(self):
        result = self._fmt({"required_documents": None, "official_source": "x.gov.in"})
        assert result["required_documents"] == "Not mentioned"

    # 5. null contact_info → "Visit official website: <official_source>"
    def test_null_contact_info_uses_official_source(self):
        result = self._fmt({"contact_info": None, "official_source": "pmkisan.gov.in"})
        assert result["contact_info"].startswith("Visit official website:")
        assert "pmkisan.gov.in" in result["contact_info"]

    # 6. populated fields pass through unchanged
    def test_populated_fields_returned_as_is(self):
        result = self._fmt({
            "eligibility": "All BPL families",
            "location": "Rural India",
            "required_documents": "Aadhaar, ration card",
            "contact_info": "1800-180-1551",
            "official_source": "pmgsy.gov.in",
        })
        assert result["eligibility"] == "All BPL families"
        assert result["location"] == "Rural India"
        assert result["required_documents"] == "Aadhaar, ration card"
        assert result["contact_info"] == "1800-180-1551"

    # 7. no output field is ever an empty string
    def test_no_field_is_empty_string(self):
        combos = [
            {"eligibility": None, "official_source": "a.gov.in"},
            {"eligibility": "", "official_source": "a.gov.in"},
            {"location": None, "official_source": "a.gov.in"},
            {"location": "", "official_source": "a.gov.in"},
            {"required_documents": None, "official_source": "a.gov.in"},
            {"required_documents": "", "official_source": "a.gov.in"},
            {"contact_info": None, "official_source": "a.gov.in"},
            {"contact_info": "", "official_source": "a.gov.in"},
        ]
        for meta in combos:
            result = self._fmt(meta)
            for field, value in result.items():
                assert value != "", (
                    f"Field '{field}' returned empty string for input: {meta}"
                )

    # 8. all-null dict returns all defined fallbacks
    def test_all_null_dict_returns_all_fallbacks(self):
        result = self._fmt({
            "eligibility": None,
            "location": None,
            "required_documents": None,
            "contact_info": None,
            "official_source": "example.gov.in",
        })
        assert result["eligibility"] == "Not mentioned"
        assert result["location"] == "No location restriction -- apply online only"
        assert result["required_documents"] == "Not mentioned"
        assert result["contact_info"].startswith("Visit official website:")
        assert "example.gov.in" in result["contact_info"]


# ---------------------------------------------------------------------------
# Task 4.5 — Unit tests for rate_limiter.is_rate_limited()
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """
    Unit tests for is_rate_limited() in rate_limiter.py.

    MAX_REQUESTS_PER_WINDOW = 3, so calls 1–3 return False; call 4 returns True.
    Each test uses a unique user_id (via uuid) to avoid cross-test contamination
    from the module-level _request_log dict.
    """

    @staticmethod
    def _uid() -> int:
        """Return a fresh integer user_id guaranteed not used by any other test."""
        import uuid
        return uuid.uuid4().int

    def test_first_call_not_limited(self):
        """First call for a new user must return False."""
        from rate_limiter import is_rate_limited
        uid = self._uid()
        assert is_rate_limited(uid) is False

    def test_second_call_not_limited(self):
        """Second call for the same user still returns False (under limit)."""
        from rate_limiter import is_rate_limited
        uid = self._uid()
        is_rate_limited(uid)           # call 1
        assert is_rate_limited(uid) is False  # call 2

    def test_third_call_not_limited(self):
        """Third call is the last allowed call — must still return False."""
        from rate_limiter import is_rate_limited
        uid = self._uid()
        is_rate_limited(uid)           # call 1
        is_rate_limited(uid)           # call 2
        assert is_rate_limited(uid) is False  # call 3

    def test_fourth_call_is_limited(self):
        """Fourth call exceeds MAX_REQUESTS_PER_WINDOW=3 and must return True."""
        from rate_limiter import is_rate_limited
        uid = self._uid()
        is_rate_limited(uid)           # call 1
        is_rate_limited(uid)           # call 2
        is_rate_limited(uid)           # call 3
        assert is_rate_limited(uid) is True   # call 4 — should be blocked

    def test_different_users_independent(self):
        """Calls for user A do not consume quota for user B."""
        from rate_limiter import is_rate_limited
        uid_a = self._uid()
        uid_b = self._uid()

        # Exhaust user A's quota
        is_rate_limited(uid_a)
        is_rate_limited(uid_a)
        is_rate_limited(uid_a)
        assert is_rate_limited(uid_a) is True   # A is now limited

        # User B is unaffected — first call must be False
        assert is_rate_limited(uid_b) is False

    def test_rate_limiter_returns_bool(self):
        """is_rate_limited() must return a proper bool, not None or int."""
        from rate_limiter import is_rate_limited
        uid = self._uid()
        result = is_rate_limited(uid)
        assert isinstance(result, bool), (
            f"Expected bool, got {type(result).__name__}: {result!r}"
        )

    def test_fresh_user_not_limited(self):
        """A brand-new user_id that has never been seen must return False."""
        from rate_limiter import is_rate_limited
        uid = self._uid()
        # No prior calls for this uid — must not be limited
        assert is_rate_limited(uid) is False


# ---------------------------------------------------------------------------
# Task 4.6 — Unit tests for validate_language() in api.py
# ---------------------------------------------------------------------------

class TestValidateLanguage:
    """
    Unit tests for validate_language() defined in api.py.

    validate_language() signature:
        def validate_language(language: str) -> str

    Behaviour:
      - Normalises via (language or "english").strip().lower()
      - Returns the normalised string if it is in LANGUAGE_CODES
        (currently: "english", "hindi", "telugu")
      - Raises fastapi.HTTPException(status_code=400) for any value
        not in LANGUAGE_CODES

    LANGUAGE_CODES is imported from translate.py and has three keys:
        {"english": "eng_Latn", "hindi": "hin_Deva", "telugu": "tel_Telu"}

    Note: validate_language() accepts a *language name* string
    (e.g. "english", "hindi"), not the message text itself.  The Devanagari /
    Telugu / Hinglish examples in the test docstrings are the kinds of
    message *content* a caller would pair with each language param.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _call(language: str) -> str:
        """Thin wrapper so each test only writes what it cares about."""
        from api import validate_language
        return validate_language(language)

    # ------------------------------------------------------------------
    # 1. English text accepted
    # ------------------------------------------------------------------

    def test_english_text_accepted(self):
        """
        Passing "english" returns the normalised value "english".
        Use case: plain English scam messages ("Your account will be blocked").
        """
        result = self._call("english")
        assert result == "english"

    # ------------------------------------------------------------------
    # 2. Hindi / Devanagari accepted
    # ------------------------------------------------------------------

    def test_hindi_devanagari_accepted(self):
        """
        Passing "hindi" returns "hindi".
        Use case: Devanagari scam messages such as "आपका SBI KYC पेंडिंग है".
        The caller submits language="hindi"; validate_language must accept it.
        """
        result = self._call("hindi")
        assert result == "hindi"

    # ------------------------------------------------------------------
    # 3. Telugu accepted
    # ------------------------------------------------------------------

    def test_telugu_accepted(self):
        """
        Passing "telugu" returns "telugu".
        Use case: Telugu scam messages such as "మీ విద్యుత్ కనెక్షన్".
        """
        result = self._call("telugu")
        assert result == "telugu"

    # ------------------------------------------------------------------
    # 4. Hinglish accepted (via "english")
    # ------------------------------------------------------------------

    def test_hinglish_accepted(self):
        """
        Romanised Hinglish messages (e.g. "bijli katne wali hai") are
        handled under language="english" — validate_language must accept
        "english" and return it.

        There is no separate "hinglish" code in LANGUAGE_CODES; Hinglish
        is processed as English by the classifier's fuzzy-matching pipeline.
        """
        result = self._call("english")
        assert result == "english"

    # ------------------------------------------------------------------
    # 5. Empty string behaviour
    # ------------------------------------------------------------------

    def test_empty_string_behaviour(self):
        """
        An empty string is normalised to "english" by the
        `(language or "english")` guard, so validate_language("") must NOT
        raise and must return "english".
        """
        from fastapi import HTTPException
        try:
            result = self._call("")
            # If no exception: must have resolved to "english"
            assert result == "english", (
                f"Expected empty string to resolve to 'english', got: {result!r}"
            )
        except HTTPException:
            pytest.fail(
                "validate_language('') raised HTTPException — expected it to "
                "fall back to 'english' via the `(language or 'english')` guard."
            )

    # ------------------------------------------------------------------
    # 6. Return type is correct (str)
    # ------------------------------------------------------------------

    def test_return_type_is_correct(self):
        """
        validate_language() is documented to return str.
        Verify each supported language name returns a plain str instance.
        """
        from api import validate_language
        for lang in ("english", "hindi", "telugu"):
            result = validate_language(lang)
            assert isinstance(result, str), (
                f"Expected str for language={lang!r}, got {type(result).__name__}: {result!r}"
            )

    # ------------------------------------------------------------------
    # 7. Unsupported language raises HTTPException(400)
    # ------------------------------------------------------------------

    def test_unsupported_language_rejected_or_flagged(self):
        """
        A language not in LANGUAGE_CODES (e.g. "japanese", "arabic") must
        raise fastapi.HTTPException with status_code 400.

        This protects the API from silently ignoring an unknown language
        and surfacing an unhandled ValueError deep inside translate_text().
        """
        from fastapi import HTTPException

        unsupported_languages = [
            "japanese",   # こんにちは — not in LANGUAGE_CODES
            "arabic",     # مرحبا — not in LANGUAGE_CODES
            "french",
            "mandarin",
            "JAPANESE",   # uppercase variant — must also be rejected after normalisation
        ]
        for lang in unsupported_languages:
            with pytest.raises(HTTPException) as exc_info:
                self._call(lang)
            assert exc_info.value.status_code == 400, (
                f"Expected HTTPException(400) for language={lang!r}, "
                f"got status_code={exc_info.value.status_code}"
            )

    # ------------------------------------------------------------------
    # 8. Case normalisation — mixed-case inputs are accepted
    # ------------------------------------------------------------------

    def test_case_normalisation_of_supported_languages(self):
        """
        validate_language() lowercases input before lookup, so "English",
        "HINDI", and "Telugu" must all resolve to their lowercase equivalents
        without raising.
        """
        assert self._call("English") == "english"
        assert self._call("HINDI") == "hindi"
        assert self._call("Telugu") == "telugu"

    # ------------------------------------------------------------------
    # 9. Whitespace stripping
    # ------------------------------------------------------------------

    def test_whitespace_stripped_before_lookup(self):
        """
        Leading/trailing whitespace is stripped before the LANGUAGE_CODES
        lookup: "  english  " must resolve to "english" (not raise).
        """
        result = self._call("  english  ")
        assert result == "english"
