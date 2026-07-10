"""
Preservation Property-Based Tests — Phase 2 (UNFIXED codebase)
===============================================================

These tests capture *correct* baseline behaviors that already exist on the
unfixed codebase.  They are written BEFORE any fixes are applied and must
ALL PASS on unfixed code, confirming the behavioral baseline we protect.

After fixes are applied (Phase 5), re-running this file must still produce
all-PASS results, confirming no regressions.

Properties:
  2a — Latin-script strings: _detect_indic_script() always returns None
  2b — Latin-script strings: to_english_for_matching() returns input unchanged
  2c — Randomly-nulled metadata: format_scheme_layout() uses exact fallbacks/seeds
  2d — Random URLs: check_url() never passes raw URL as first positional arg
       to requests.get or requests.post

**Validates: Requirements 3.1, 3.2, 5.2, 5.5, 8.3, 10.1**
"""

import os
import unittest.mock as mock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Suppress the FutureWarning from transformers that pollutes test output
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
# Helpers / shared strategies
# ---------------------------------------------------------------------------

# Strategy: printable Latin-script characters — uppercase, lowercase, digits,
# spaces, punctuation.  These are all ASCII/Latin-only; no code point falls in
# a Devanagari (0x0900–0x097F) or Telugu (0x0C00–0x0C7F) range, so
# _detect_indic_script() must return None for every generated string.
_LATIN_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")
    )
)

# Strategy: generate optional values for a metadata field — either a non-empty
# non-whitespace string, an empty string, or None.  The schema accepts all three.
_OPTIONAL_FIELD = st.one_of(
    st.none(),
    st.just(""),
    st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po"))).filter(lambda s: s.strip()),
)


# ---------------------------------------------------------------------------
# Property 2a — Latin-script strings always score None for Indic script
# ---------------------------------------------------------------------------

class TestProperty2aDetectIndicScript:
    """
    **Validates: Requirements 5.2, 5.5**

    For ALL strings composed of Latin-script characters (uppercase, lowercase,
    digits, spaces, common punctuation), _detect_indic_script() MUST return None.

    This confirms that to_english_for_matching() will never trigger a model call
    for English, romanized Hinglish, or any other purely Latin-script text —
    preserving the existing fast-path behavior.
    """

    @given(_LATIN_TEXT)
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_2a_latin_text_returns_none(self, s: str):
        """
        Property 2a: _detect_indic_script(s) is None for all Latin-script inputs.

        Counterexample if violated: a Latin-script string that contains >= 4
        code points inside a Devanagari or Telugu Unicode block — impossible
        by construction of the strategy above.
        """
        from translate import _detect_indic_script
        result = _detect_indic_script(s)
        assert result is None, (
            f"_detect_indic_script() returned {result!r} for Latin-script input {s!r}. "
            f"Expected None — no model call should be triggered for non-Indic text."
        )

    def test_2a_baseline_sbi_kyc_english(self):
        """Concrete baseline: the specific English KYC phrase from the spec."""
        from translate import _detect_indic_script
        assert _detect_indic_script("Your SBI KYC is pending") is None

    def test_2a_empty_string_returns_none(self):
        """Empty string has zero Indic characters — must return None."""
        from translate import _detect_indic_script
        assert _detect_indic_script("") is None

    def test_2a_mixed_latin_and_digits(self):
        """Mixed alphanumeric Latin — must return None."""
        from translate import _detect_indic_script
        assert _detect_indic_script("bijli bill 1234 KYC pending") is None


# ---------------------------------------------------------------------------
# Property 2b — Latin-script strings pass through to_english_for_matching unchanged
# ---------------------------------------------------------------------------

class TestProperty2bToEnglishPassThrough:
    """
    **Validates: Requirements 5.2, 5.5**

    For ALL strings composed of Latin-script characters, to_english_for_matching()
    MUST return the input string unchanged — no model invocation, no modification.

    This confirms that adding the translation step to the pipeline (the G4/G6 fix)
    does NOT change behavior for English or romanized Hinglish inputs that are
    already handled correctly.
    """

    @given(_LATIN_TEXT)
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_2b_latin_text_returned_unchanged(self, s: str):
        """
        Property 2b: to_english_for_matching(s) == s for all Latin-script inputs.

        Since _detect_indic_script(s) returns None for these inputs (Property 2a),
        to_english_for_matching() must take the early-return path and hand back
        the original string without loading or querying any model.
        """
        from translate import to_english_for_matching
        result = to_english_for_matching(s)
        assert result == s, (
            f"to_english_for_matching() returned {result!r} for Latin-script input {s!r}. "
            f"Expected the input unchanged — no translation should occur for Latin text."
        )

    def test_2b_baseline_hinglish_bijli(self):
        """Concrete baseline: romanized Hinglish 'bijli katne wali hai' passes through."""
        from translate import to_english_for_matching
        assert to_english_for_matching("bijli katne wali hai") == "bijli katne wali hai"

    def test_2b_english_electricity_unchanged(self):
        """English scam phrase passes through unchanged."""
        from translate import to_english_for_matching
        s = "your electricity will be disconnected tonight"
        assert to_english_for_matching(s) == s

    def test_2b_empty_string_unchanged(self):
        """Empty string passes through unchanged."""
        from translate import to_english_for_matching
        assert to_english_for_matching("") == ""


# ---------------------------------------------------------------------------
# Property 2c — format_scheme_layout() uses exact fallbacks/seeds, never empty
# ---------------------------------------------------------------------------

class TestProperty2cSchemeLayoutNoFabrication:
    """
    **Validates: Requirements 8.2, 8.3, C3**

    For randomly-generated metadata dicts where individual fields may be null
    (None), empty string (""), or a non-empty seed value, format_scheme_layout()
    MUST:
      - Return the EXACT fallback string for any null/empty field
      - Return the EXACT seed value for any non-null/non-empty field
      - Never return an empty string, a fabricated value, or a partial template

    EXPECTED_FALLBACKS:
      eligibility         → "Not mentioned"
      location            → "No location restriction -- apply online only"
      required_documents  → "Not mentioned"
      contact_info        → starts with "Visit official website:"

    This confirms the no-fabrication contract (C3) holds across all input
    combinations without requiring ChromaDB to be running.
    """

    EXPECTED_FALLBACK = {
        "eligibility": "Not mentioned",
        "location": "No location restriction -- apply online only",
        "required_documents": "Not mentioned",
        # contact_info fallback is dynamic — it starts with this prefix
        "contact_info_prefix": "Visit official website:",
    }

    @given(
        st.fixed_dictionaries({
            "eligibility": _OPTIONAL_FIELD,
            "location": _OPTIONAL_FIELD,
            "required_documents": _OPTIONAL_FIELD,
            "contact_info": _OPTIONAL_FIELD,
            "official_source": st.one_of(
                st.none(),
                st.just(""),
                st.just("example.gov.in"),
                st.just("pmkisan.gov.in"),
            ),
        })
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_2c_fallbacks_and_seeds_are_exact(self, meta: dict):
        """
        Property 2c: format_scheme_layout() returns exact fallbacks for null/empty
        fields and exact seed values for non-null fields.

        **Validates: Requirements 8.2, 8.3**
        """
        from scheme_check import format_scheme_layout
        layout = format_scheme_layout(meta)

        # --- eligibility ---
        raw_elig = meta.get("eligibility")
        if not raw_elig:  # None or ""
            assert layout["eligibility"] == self.EXPECTED_FALLBACK["eligibility"], (
                f"eligibility fallback wrong: got {layout['eligibility']!r}, "
                f"expected {self.EXPECTED_FALLBACK['eligibility']!r}"
            )
        else:
            assert layout["eligibility"] == raw_elig, (
                f"eligibility seed value changed: got {layout['eligibility']!r}, "
                f"expected {raw_elig!r}"
            )

        # --- location ---
        raw_loc = meta.get("location")
        if not raw_loc:
            assert layout["location"] == self.EXPECTED_FALLBACK["location"], (
                f"location fallback wrong: got {layout['location']!r}, "
                f"expected {self.EXPECTED_FALLBACK['location']!r}"
            )
        else:
            assert layout["location"] == raw_loc, (
                f"location seed value changed: got {layout['location']!r}, "
                f"expected {raw_loc!r}"
            )

        # --- required_documents ---
        raw_docs = meta.get("required_documents")
        if not raw_docs:
            assert layout["required_documents"] == self.EXPECTED_FALLBACK["required_documents"], (
                f"required_documents fallback wrong: got {layout['required_documents']!r}, "
                f"expected {self.EXPECTED_FALLBACK['required_documents']!r}"
            )
        else:
            assert layout["required_documents"] == raw_docs, (
                f"required_documents seed value changed: got {layout['required_documents']!r}, "
                f"expected {raw_docs!r}"
            )

        # --- contact_info ---
        raw_contact = meta.get("contact_info")
        if not raw_contact:
            assert layout["contact_info"].startswith(self.EXPECTED_FALLBACK["contact_info_prefix"]), (
                f"contact_info fallback wrong: got {layout['contact_info']!r}, "
                f"expected it to start with {self.EXPECTED_FALLBACK['contact_info_prefix']!r}"
            )
            # Also confirm it is not just the bare prefix — must include the source
            assert len(layout["contact_info"]) > len(self.EXPECTED_FALLBACK["contact_info_prefix"]), (
                f"contact_info fallback is incomplete (just the prefix): {layout['contact_info']!r}"
            )
        else:
            assert layout["contact_info"] == raw_contact, (
                f"contact_info seed value changed: got {layout['contact_info']!r}, "
                f"expected {raw_contact!r}"
            )

        # --- general: no field should be empty ---
        for field in ("eligibility", "location", "required_documents", "contact_info"):
            assert layout[field], (
                f"format_scheme_layout() returned empty string for {field!r}: "
                f"meta={meta!r}"
            )

    def test_2c_all_null_fields_use_fallbacks(self):
        """Concrete baseline: all-null metadata → all fallback strings."""
        from scheme_check import format_scheme_layout
        meta = {
            "eligibility": None,
            "location": None,
            "required_documents": None,
            "contact_info": None,
            "official_source": "example.gov.in",
        }
        layout = format_scheme_layout(meta)
        assert layout["eligibility"] == "Not mentioned"
        assert layout["location"] == "No location restriction -- apply online only"
        assert layout["required_documents"] == "Not mentioned"
        assert layout["contact_info"].startswith("Visit official website:")
        assert "example.gov.in" in layout["contact_info"]

    def test_2c_all_empty_string_fields_use_fallbacks(self):
        """Concrete baseline: all-empty-string metadata → all fallback strings."""
        from scheme_check import format_scheme_layout
        meta = {
            "eligibility": "",
            "location": "",
            "required_documents": "",
            "contact_info": "",
            "official_source": "pmkisan.gov.in",
        }
        layout = format_scheme_layout(meta)
        assert layout["eligibility"] == "Not mentioned"
        assert layout["location"] == "No location restriction -- apply online only"
        assert layout["required_documents"] == "Not mentioned"
        assert layout["contact_info"] == "Visit official website: pmkisan.gov.in"

    def test_2c_populated_fields_returned_unchanged(self):
        """Concrete baseline: non-null seed values returned as-is (PM Ujjwala style)."""
        from scheme_check import format_scheme_layout
        meta = {
            "eligibility": "All BPL families",
            "location": "Rural India",
            "required_documents": "Aadhaar",
            "contact_info": "1800-XXX",
            "official_source": "pmuy.gov.in",
        }
        layout = format_scheme_layout(meta)
        assert layout["eligibility"] == "All BPL families"
        assert layout["location"] == "Rural India"
        assert layout["required_documents"] == "Aadhaar"
        assert layout["contact_info"] == "1800-XXX"


# ---------------------------------------------------------------------------
# Property 2d — check_url() never passes raw URL as first positional arg to requests.*
# ---------------------------------------------------------------------------

class TestProperty2dUrlSecurityBoundary:
    """
    **Validates: Requirements 3.1, 3.2, C1**

    For ALL URL strings submitted to check_url(), the function must NEVER call
    requests.get() or requests.post() with the submitted URL string as the first
    positional argument (i.e., as the network target).

    The URL may appear only as a value inside a request body or path-ID parameter
    sent to an approved endpoint (Safe Browsing, VirusTotal). This is the
    URL security boundary (C1).

    When no API keys are configured, check_url() must return "unknown" without
    making any network calls at all.
    """

    @given(st.from_regex(r"https?://[a-zA-Z0-9./?=&_-]+", fullmatch=True))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_2d_raw_url_never_used_as_network_target(self, url: str):
        """
        Property 2d: check_url(url) never calls requests.get(url) or
        requests.post(url) with the submitted url as the first positional argument.

        With no API keys set, no network calls should be made at all.
        With API keys set (simulated via mocked env vars), any calls must
        target only the approved Safe Browsing / VirusTotal endpoints.

        **Validates: Requirements 3.1, 3.2, C1**
        """
        # Ensure no real API keys leak into this test
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_SAFE_BROWSING_API_KEY", None)
            os.environ.pop("VIRUSTOTAL_API_KEY", None)

            with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
                 mock.patch("url_agent.VIRUSTOTAL_API_KEY", None), \
                 mock.patch("requests.get") as mock_get, \
                 mock.patch("requests.post") as mock_post:

                from url_agent import check_url
                result = check_url(url)

                # With no API keys, no requests should be made at all
                mock_get.assert_not_called()
                mock_post.assert_not_called()

                # Verdict must be "unknown" or "structurally_suspicious"
                # (structural checks run without any network call)
                assert result["verdict"] in ("unknown", "structurally_suspicious"), (
                    f"Expected 'unknown' or 'structurally_suspicious' with no API keys, "
                    f"got {result['verdict']!r} for url={url!r}"
                )

    @given(st.from_regex(r"https?://[a-zA-Z0-9./?=&_-]+", fullmatch=True))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_2d_with_mocked_api_keys_url_never_first_arg(self, url: str):
        """
        Property 2d (extended): Even when API keys are present (simulated),
        check_url() must never pass the submitted URL as the first positional
        arg to requests.get or requests.post.

        All network calls must target only SAFE_BROWSING_ENDPOINT or the
        VT_URL_REPORT_ENDPOINT / VT_URL_SUBMIT_ENDPOINT.
        """
        SAFE_BROWSING_ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
        VT_URL_SUBMIT_ENDPOINT = "https://www.virustotal.com/api/v3/urls"
        VT_URL_REPORT_ENDPOINT_BASE = "https://www.virustotal.com/api/v3/urls/"

        mock_sb_response = mock.MagicMock()
        mock_sb_response.raise_for_status.return_value = None
        mock_sb_response.json.return_value = {}

        mock_vt_response = mock.MagicMock()
        mock_vt_response.status_code = 200
        mock_vt_response.raise_for_status.return_value = None
        mock_vt_response.json.return_value = {
            "data": {"attributes": {"last_analysis_stats": {"malicious": 0, "suspicious": 0}}}
        }

        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", "fake-sb-key"), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", "fake-vt-key"), \
             mock.patch("requests.get", return_value=mock_vt_response) as mock_get, \
             mock.patch("requests.post", return_value=mock_sb_response) as mock_post:

            from url_agent import check_url
            check_url(url)

            # For every requests.get call, the first positional arg must NOT be the raw url
            for call in mock_get.call_args_list:
                first_arg = call.args[0] if call.args else None
                assert first_arg != url, (
                    f"requests.get() called with raw submitted url as first arg: {url!r}. "
                    f"This violates the URL security boundary (C1). "
                    f"Network calls must only target approved endpoints."
                )
                # The first arg should be a VT or Safe Browsing endpoint
                if first_arg is not None:
                    assert (
                        first_arg.startswith(VT_URL_REPORT_ENDPOINT_BASE) or
                        first_arg.startswith(SAFE_BROWSING_ENDPOINT)
                    ), (
                        f"requests.get() called with unexpected endpoint: {first_arg!r}. "
                        f"Expected only VT or Safe Browsing endpoints."
                    )

            # For every requests.post call, the first positional arg must NOT be the raw url
            for call in mock_post.call_args_list:
                first_arg = call.args[0] if call.args else None
                assert first_arg != url, (
                    f"requests.post() called with raw submitted url as first arg: {url!r}. "
                    f"This violates the URL security boundary (C1)."
                )
                if first_arg is not None:
                    assert (
                        first_arg.startswith(SAFE_BROWSING_ENDPOINT) or
                        first_arg == VT_URL_SUBMIT_ENDPOINT
                    ), (
                        f"requests.post() called with unexpected endpoint: {first_arg!r}."
                    )

    def test_2d_concrete_baseline_no_keys_unknown(self):
        """Concrete baseline: check_url() returns 'unknown' when no API keys set."""
        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None):
            from url_agent import check_url
            result = check_url("https://example.com")
        assert result["verdict"] in ("unknown", "structurally_suspicious")

    def test_2d_structural_suspicious_ip_url_no_network(self):
        """
        Concrete baseline: IP-format URL gets 'structurally_suspicious' with no
        network calls — structural checks are pure string analysis.
        """
        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None), \
             mock.patch("requests.get") as mock_get, \
             mock.patch("requests.post") as mock_post:
            from url_agent import check_url
            result = check_url("http://192.168.1.1/login")
        mock_get.assert_not_called()
        mock_post.assert_not_called()
        assert result["verdict"] == "structurally_suspicious"


# ---------------------------------------------------------------------------
# Property 3 — URL security boundary re-confirmation (POST-FIX codebase)
# ---------------------------------------------------------------------------

class TestProperty3UrlSecurityBoundaryPostFix:
    """Property 3 re-confirmation: URL security boundary holds on fixed codebase.

    **Validates: Requirements 3.1, 3.2, 3.3, C1**

    For all URL strings, check_url() must NEVER pass the raw submitted URL as
    the first positional argument to requests.get() or requests.post().
    With no API keys configured, no network calls are made at all.
    This re-confirms that none of the Phase 2–4 fixes inadvertently broke the
    security boundary established in Property 2d.
    """

    # Approved endpoints — any network call must target only these
    SAFE_BROWSING_ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    VT_URL_SUBMIT_ENDPOINT = "https://www.virustotal.com/api/v3/urls"
    VT_URL_REPORT_ENDPOINT_BASE = "https://www.virustotal.com/api/v3/urls/"

    @given(st.from_regex(r"https?://[a-zA-Z0-9./?=&_-]+", fullmatch=True))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_3a_no_api_keys_no_network_calls(self, url: str):
        """With both API keys patched to None, no network calls are made at all.

        **Validates: Requirements 3.1, 3.2, C1**
        """
        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None), \
             mock.patch("requests.get") as mock_get, \
             mock.patch("requests.post") as mock_post:

            from url_agent import check_url
            result = check_url(url)

            mock_get.assert_not_called()
            mock_post.assert_not_called()

            # Must return a valid verdict — structural checks still run
            assert "verdict" in result, (
                f"check_url() returned a result without a 'verdict' key: {result!r}"
            )

    @given(st.from_regex(r"https?://[a-zA-Z0-9./?=&_-]+", fullmatch=True))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_3b_raw_url_never_first_arg_with_keys(self, url: str):
        """With mocked API keys, the submitted URL is never the first positional arg
        to any requests.get or requests.post call.  Every call must target only
        safebrowsing.googleapis.com or virustotal.com.

        **Validates: Requirements 3.1, 3.2, 3.3, C1**
        """
        mock_sb_response = mock.MagicMock()
        mock_sb_response.raise_for_status.return_value = None
        mock_sb_response.json.return_value = {}

        mock_vt_response = mock.MagicMock()
        mock_vt_response.status_code = 200
        mock_vt_response.raise_for_status.return_value = None
        mock_vt_response.json.return_value = {
            "data": {
                "attributes": {
                    "last_analysis_stats": {"malicious": 0, "suspicious": 0}
                }
            }
        }

        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", "fake-sb-key"), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", "fake-vt-key"), \
             mock.patch("requests.get", return_value=mock_vt_response) as mock_get, \
             mock.patch("requests.post", return_value=mock_sb_response) as mock_post:

            from url_agent import check_url
            check_url(url)

            # Every requests.get call: first positional arg must NOT be the raw url,
            # and must target only an approved endpoint.
            for call in mock_get.call_args_list:
                first_arg = call.args[0] if call.args else None
                assert first_arg != url, (
                    f"requests.get() called with raw submitted url as first arg: {url!r}. "
                    f"URL security boundary (C1) violated."
                )
                if first_arg is not None:
                    assert (
                        first_arg.startswith(self.VT_URL_REPORT_ENDPOINT_BASE)
                        or first_arg.startswith(self.SAFE_BROWSING_ENDPOINT)
                    ), (
                        f"requests.get() targeting unexpected endpoint: {first_arg!r}. "
                        f"Must target only VT or Safe Browsing endpoints."
                    )

            # Every requests.post call: same constraint.
            for call in mock_post.call_args_list:
                first_arg = call.args[0] if call.args else None
                assert first_arg != url, (
                    f"requests.post() called with raw submitted url as first arg: {url!r}. "
                    f"URL security boundary (C1) violated."
                )
                if first_arg is not None:
                    assert (
                        first_arg.startswith(self.SAFE_BROWSING_ENDPOINT)
                        or first_arg == self.VT_URL_SUBMIT_ENDPOINT
                    ), (
                        f"requests.post() targeting unexpected endpoint: {first_arg!r}."
                    )

    def test_3c_concrete_phishing_url_no_network(self):
        """Concrete test: a known phishing-style URL with no API keys makes no
        network calls and returns a result dict containing a 'verdict' key.

        **Validates: Requirements 3.1, C1**
        """
        phishing_url = "https://sbi-kyc-secure.in/verify"

        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None), \
             mock.patch("requests.get") as mock_get, \
             mock.patch("requests.post") as mock_post:

            from url_agent import check_url
            result = check_url(phishing_url)

            mock_get.assert_not_called()
            mock_post.assert_not_called()

            assert "verdict" in result, (
                f"check_url() must return a dict with a 'verdict' key; got: {result!r}"
            )

    @given(st.from_regex(r"https?://[a-zA-Z0-9./?=&_-]+", fullmatch=True))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_3d_structural_flags_are_always_list(self, url: str):
        """For every URL string, check_url()['structural_flags'] is always a list —
        never None, never absent from the result dict.

        **Validates: Requirements 3.1, 3.2**
        """
        with mock.patch("url_agent.SAFE_BROWSING_API_KEY", None), \
             mock.patch("url_agent.VIRUSTOTAL_API_KEY", None):

            from url_agent import check_url
            result = check_url(url)

            assert "structural_flags" in result, (
                f"check_url() result missing 'structural_flags' key for url={url!r}"
            )
            assert isinstance(result["structural_flags"], list), (
                f"check_url()['structural_flags'] must be a list, "
                f"got {type(result['structural_flags']).__name__!r} for url={url!r}"
            )


# ---------------------------------------------------------------------------
# Property 5 — Scheme no-fabrication re-confirmation (POST-FIX codebase)
# ---------------------------------------------------------------------------

class TestProperty5SchemeNoFabricationPostFix:
    """Property 5 re-confirmation: scheme no-fabrication contract holds on fixed codebase.

    **Validates: Requirements 8.2, 8.3, C3**

    For any scheme metadata dict where a seed field is null or empty,
    format_scheme_layout() MUST return exactly the specified fallback string —
    not an empty string, not a fabricated value, and not a partial template.
    For any scheme where a seed field is NOT null/empty, format_scheme_layout()
    MUST return the exact seed value unchanged.

    This re-confirms the no-fabrication contract (C3) after all Phase 2–4 fixes.
    """

    EXPECTED_FALLBACK = {
        "eligibility": "Not mentioned",
        "location": "No location restriction -- apply online only",
        "required_documents": "Not mentioned",
        # contact_info fallback starts with this prefix
        "contact_info_prefix": "Visit official website:",
    }

    # ------------------------------------------------------------------
    # test_5a — no field is ever empty, across all input combinations
    # ------------------------------------------------------------------

    @given(
        st.fixed_dictionaries({
            "eligibility": st.one_of(st.none(), st.just(""), st.text(min_size=1)),
            "location": st.one_of(st.none(), st.just(""), st.text(min_size=1)),
            "required_documents": st.one_of(st.none(), st.just(""), st.text(min_size=1)),
            "contact_info": st.one_of(st.none(), st.just(""), st.text(min_size=1)),
            "official_source": st.just("example.gov.in"),
        })
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_5a_no_field_ever_empty_post_fix(self, meta: dict):
        """No output field is ever an empty string, regardless of input combination.

        **Validates: Requirements 8.2, 8.3, C3**
        """
        from scheme_check import format_scheme_layout
        layout = format_scheme_layout(meta)

        for field in ("eligibility", "location", "required_documents", "contact_info"):
            assert layout[field] != "", (
                f"format_scheme_layout() returned empty string for field {field!r}. "
                f"Input meta={meta!r}. No output field should ever be empty."
            )
            assert layout[field] is not None, (
                f"format_scheme_layout() returned None for field {field!r}. "
                f"Input meta={meta!r}."
            )

    # ------------------------------------------------------------------
    # test_5b — non-null/non-empty input values pass through unchanged
    # ------------------------------------------------------------------

    @given(
        st.fixed_dictionaries({
            "eligibility": st.one_of(
                st.none(),
                st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")))
            ),
            "location": st.one_of(
                st.none(),
                st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")))
            ),
            "required_documents": st.one_of(
                st.none(),
                st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")))
            ),
            "contact_info": st.one_of(
                st.none(),
                st.text(min_size=1, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")))
            ),
            "official_source": st.just("example.gov.in"),
        })
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_5b_seed_values_passed_through_unchanged(self, meta: dict):
        """For every non-null/non-empty field, the output value equals the input exactly.

        format_scheme_layout() must not transform, truncate, or modify seed values.

        **Validates: Requirements 8.3, C3**
        """
        from scheme_check import format_scheme_layout
        layout = format_scheme_layout(meta)

        for field in ("eligibility", "location", "required_documents", "contact_info"):
            raw = meta.get(field)
            if raw is not None and raw != "":
                assert layout[field] == raw, (
                    f"format_scheme_layout() changed field {field!r}: "
                    f"input={raw!r}, output={layout[field]!r}. "
                    f"Seed values must pass through unchanged."
                )

    # ------------------------------------------------------------------
    # test_5c — fallback strings are the exact specified constants
    # ------------------------------------------------------------------

    @given(
        st.fixed_dictionaries({
            "eligibility": st.none(),
            "location": st.none(),
            "required_documents": st.none(),
            "contact_info": st.none(),
            "official_source": st.just("example.gov.in"),
        })
    )
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_5c_fallback_strings_are_exact_constants(self, meta: dict):
        """When all four optional fields are None, the fallback strings are exact constants.

        **Validates: Requirements 8.2, 8.3, C3**
        """
        from scheme_check import format_scheme_layout
        layout = format_scheme_layout(meta)

        assert layout["eligibility"] == "Not mentioned", (
            f"eligibility fallback wrong: got {layout['eligibility']!r}, "
            f"expected 'Not mentioned'"
        )
        assert layout["location"] == "No location restriction -- apply online only", (
            f"location fallback wrong: got {layout['location']!r}, "
            f"expected 'No location restriction -- apply online only'"
        )
        assert layout["required_documents"] == "Not mentioned", (
            f"required_documents fallback wrong: got {layout['required_documents']!r}, "
            f"expected 'Not mentioned'"
        )
        assert layout["contact_info"].startswith("Visit official website:"), (
            f"contact_info fallback wrong: got {layout['contact_info']!r}, "
            f"expected it to start with 'Visit official website:'"
        )

    # ------------------------------------------------------------------
    # test_5d — contact_info fallback contains the official_source value
    # ------------------------------------------------------------------

    def test_5d_contact_info_contains_official_source(self):
        """Concrete test: when contact_info is None and official_source is 'pmuy.gov.in',
        the returned contact_info must contain 'pmuy.gov.in'.

        **Validates: Requirements 8.2, C3**
        """
        from scheme_check import format_scheme_layout
        meta = {
            "eligibility": None,
            "location": None,
            "required_documents": None,
            "contact_info": None,
            "official_source": "pmuy.gov.in",
        }
        layout = format_scheme_layout(meta)

        assert "pmuy.gov.in" in layout["contact_info"], (
            f"contact_info fallback must contain 'pmuy.gov.in' when official_source is "
            f"'pmuy.gov.in'. Got: {layout['contact_info']!r}"
        )
        assert layout["contact_info"].startswith("Visit official website:"), (
            f"contact_info fallback must start with 'Visit official website:'. "
            f"Got: {layout['contact_info']!r}"
        )


# ---------------------------------------------------------------------------
# Property 4 — Latin-script preservation re-confirmation (POST-FIX codebase)
# ---------------------------------------------------------------------------

class TestProperty4LatinScriptPreservationPostFix:
    """Property 4 post-fix: Latin-script pass-through preserved on fixed codebase.

    **Validates: Requirements 5.2, 5.5**

    Re-confirms Properties 2a and 2b still hold after the G4/G6 fixes were
    applied to local_pipeline_test.py and translate.py.  The insertion of
    to_english_for_matching() into the pipeline must NOT alter existing
    Latin-script pass-through behaviour.
    """

    # ------------------------------------------------------------------
    # test_4a — _detect_indic_script() still returns None for Latin text
    # ------------------------------------------------------------------

    @given(_LATIN_TEXT)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_4a_detect_indic_still_none_for_latin(self, s: str):
        """Re-runs Property 2a with a higher example count after the G4/G6 fix.

        For ALL strings composed of Latin-script characters, _detect_indic_script()
        MUST still return None — confirming that the fix did not accidentally
        introduce a code path that treats Latin text as Indic.

        **Validates: Requirements 5.2, 5.5**
        """
        from translate import _detect_indic_script
        result = _detect_indic_script(s)
        assert result is None, (
            f"_detect_indic_script() returned {result!r} for Latin-script input {s!r} "
            f"after G4/G6 fix. Expected None — Latin text must never trigger a model call."
        )

    # ------------------------------------------------------------------
    # test_4b — to_english_for_matching() still returns identity for Latin
    # ------------------------------------------------------------------

    @given(_LATIN_TEXT)
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_4b_to_english_still_identity_for_latin(self, s: str):
        """Re-runs Property 2b with a higher example count after the G4/G6 fix.

        For ALL strings composed of Latin-script characters, to_english_for_matching()
        MUST return the input string unchanged — the early-return fast path must still
        be taken for every Latin-script input after the fix.

        **Validates: Requirements 5.2, 5.5**
        """
        from translate import to_english_for_matching
        result = to_english_for_matching(s)
        assert result == s, (
            f"to_english_for_matching() returned {result!r} for Latin-script input {s!r} "
            f"after G4/G6 fix. Expected the input unchanged."
        )

    # ------------------------------------------------------------------
    # test_4c — English scam phrase still classifies after fix
    # ------------------------------------------------------------------

    def test_4c_english_scam_still_classifies_after_fix(self):
        """Concrete test: the full fixed pipeline classifies an English scam message.

        Calls to_english_for_matching() on a known English KYC scam phrase, then
        passes the result to classify().  Asserts ≥1 typology match — confirming
        that inserting to_english_for_matching() into the pipeline did not break
        English-language detection.

        **Validates: Requirements 5.2, 5.5**
        """
        from translate import to_english_for_matching
        from classifier import classify

        text = "your SBI KYC is pending, account will be blocked"
        matching_text = to_english_for_matching(text)
        # Latin text must pass through unchanged
        assert matching_text == text, (
            f"to_english_for_matching() should have returned the input unchanged "
            f"for the English phrase, but returned {matching_text!r}."
        )
        result = classify(matching_text)
        assert len(result["matches"]) >= 1, (
            f"classify() returned 0 matches for English KYC scam phrase after fix. "
            f"clean_text={result['clean_text']!r}, panic_tags={result['panic_tags']!r}. "
            f"The fix must not break English-language scam detection."
        )

    # ------------------------------------------------------------------
    # test_4d — Hinglish phrase still classifies after fix
    # ------------------------------------------------------------------

    def test_4d_hinglish_still_classifies_after_fix(self):
        """Concrete test: the full fixed pipeline classifies a romanized Hinglish phrase.

        'bijli katne wali hai' is romanized Hinglish — it uses Latin script and
        must pass through to_english_for_matching() unchanged (no model call), and
        must then match the electricity_disconnection typology via classify().

        **Validates: Requirements 5.2, 5.5**
        """
        from translate import to_english_for_matching
        from classifier import classify

        text = "bijli katne wali hai"
        matching_text = to_english_for_matching(text)
        # Romanized Hinglish is Latin-script — must pass through unchanged
        assert matching_text == text, (
            f"to_english_for_matching('bijli katne wali hai') returned {matching_text!r}. "
            f"Romanized Hinglish is Latin-script and must not be sent to the translation model."
        )
        result = classify(matching_text)
        electricity_matches = [
            m for m in result["matches"] if m["typology"] == "electricity_disconnection"
        ]
        assert len(electricity_matches) >= 1, (
            f"classify() found no electricity_disconnection match for 'bijli katne wali hai' "
            f"after fix. full result={result!r}. "
            f"Romanized Hinglish electricity scam phrase must still be detected."
        )
