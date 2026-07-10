# Satark Setu — Verification & Gap-Check Design

## Overview

This document defines the design for the **satark-setu-verification** mission: a systematic
gap-check that closes the distance between "the code reads correctly" and "the system runs
correctly on a real Windows machine."

The prior audit confirmed code structure, logic, and internal consistency. This verification
mission addresses five concrete gaps that the prior audit explicitly could not close:

1. IndicTrans2 model download and inference — never attempted
2. Full `requirements.txt` install without conflicts — never attempted
3. FastAPI app running end-to-end — never started
4. Native-script (Devanagari/Telugu) classification path — never exercised
5. `local_pipeline_test.py` — written but never executed

The methodology is the **bug condition methodology**: for each gap, we define C(X) — the
condition that causes incorrect or unverified behavior — and validate that the fix/execution
produces P(result) — the correct, expected behavior — while preserving all existing behaviors
for inputs where C(X) does not hold.

Four non-negotiable constraints (C1–C4) must be independently re-confirmed, not assumed from
the prior audit.

## Glossary

- **Bug_Condition (C)**: An input condition (or system state) that causes incorrect, unverified,
  or unsafe behavior — either a runtime failure, a false classification result, a security
  boundary violation, or a degraded response that surfaces a stack trace instead of a proper
  HTTP error code.
- **Property (P)**: The desired, correct behavior when C(X) holds — what the system must
  actually produce after a gap is closed or a fix is applied.
- **Preservation**: All existing behaviors for inputs where C(X) does NOT hold must remain
  unchanged by any fix applied during this verification mission.
- **F (original)**: The current codebase state — some behavior is correct, some is unverified,
  some is definitively broken.
- **F' (fixed)**: The codebase after targeted repairs. Minimally different from F — fixes are
  scoped strictly to the identified gap, nothing more.
- **`to_english_for_matching()`**: Function in `translate.py` that detects native-script Indic
  input and translates it to English for classification. Input-side translation only.
- **`translate_text()`**: Function in `translate.py` that translates English output to Hindi or
  Telugu for display. Output-side translation only.
- **`format_scheme_layout()`**: Function in `scheme_check.py` that enforces the strict four-field
  output layout with specified fallback strings — the no-fabrication contract.
- **`classify()`**: Function in `classifier.py` that runs fuzzy matching against six typologies.
  Operates on English/romanized text only; native-script input scores near zero without prior
  translation.
- **`is_rate_limited()`**: Function in `rate_limiter.py`. Enforces MAX_REQUESTS_PER_WINDOW=3
  per WINDOW_SECONDS=60 per client IP.
- **`OcrUnavailableError`**: Custom exception in `ocr.py` — signals missing Tesseract binary or
  language pack; maps to HTTP 503 in `api.py`.
- **`AudioExtractionError`**: Custom exception in `voice_pipeline.py` — signals missing ffmpeg;
  maps to HTTP 503 in `api.py`.
- **C1**: URL security boundary constraint — `url_agent.py` must never fetch a submitted URL.
- **C2**: No paid APIs constraint — IndicTrans2 runs locally; Safe Browsing and VirusTotal are
  free-tier only.
- **C3**: No-fabrication constraint — `format_scheme_layout()` must use exact fallback strings.
- **C4**: Graceful degradation constraint — all failure paths produce 4xx/5xx, never raw traces.

## Bug Details

This verification mission covers six distinct bug conditions, each corresponding to a
specific gap or constraint that must be validated. They are numbered G1–G6 to match the
gap list in the Overview.

---

### G1 — Dependency Install Fails or Conflicts

**The bug manifests when** `pip install -r requirements.txt` fails, produces version
conflicts, or leaves imports broken — meaning the application cannot start on a fresh
machine at all.

The known risk vector is the `git+https://github.com/VarunGumma/IndicTransToolkit` line:
it is not on PyPI, requires network access, and may depend on exact `transformers` /
`sentencepiece` versions. A secondary risk is `torch==2.4.1` + `transformers==4.44.2`
compatibility on a CPU-only Windows machine.

**Formal Specification:**

```
FUNCTION isBugCondition_G1(environment)
  INPUT: environment (Python version, pip state, network access)
  OUTPUT: boolean

  RETURN pip_install_exits_nonzero(requirements.txt)
         OR any_module_raises_ImportError_on_import()
         OR any_cross_module_reference_is_missing()
END FUNCTION
```

**Concrete Examples:**

- `pip install` exits with a ResolutionImpossible error on `torch==2.4.1` vs `transformers`
- `from IndicTransToolkit.processor import IndicProcessor` raises `ModuleNotFoundError`
- `from translate import to_english_for_matching` works but calling it raises
  `AttributeError` because `IndicProcessor` API changed in an updated commit

---

### G2 — System Dependencies Missing (Tesseract / ffmpeg)

**The bug manifests when** Tesseract is absent or missing `hin`/`tel` language packs, or
ffmpeg is absent on Windows — causing OCR and voice endpoints to fail with raw exceptions
rather than clean HTTP 503 responses.

Note: `ocr.py` error messages reference `sudo apt-get install` — this is incorrect for
Windows. The install command in the error string is a documentation bug that must be fixed
(C4 requires a real, actionable message).

**Formal Specification:**

```
FUNCTION isBugCondition_G2(system_state)
  INPUT: system_state (installed binaries, PATH)
  OUTPUT: boolean

  RETURN tesseract_not_in_PATH()
         OR tesseract_missing_lang("hin")
         OR tesseract_missing_lang("tel")
         OR ffmpeg_not_in_PATH()
         OR (ffmpeg_absent AND voice_endpoint_raises_unhandled_exception())
END FUNCTION
```

**Concrete Examples:**

- `tesseract --list-langs` exits 1 or does not list `hin`
- `POST /api/verify-image` returns HTTP 500 with `TesseractNotFoundError` traceback instead
  of HTTP 503 with `OcrUnavailableError` message
- `ocr.py`'s error message says `sudo apt-get install` on a Windows machine — unhelpful

---

### G3 — URL Security Boundary (C1 Re-Confirmation)

**The bug manifests when** any code path in `url_agent.py` uses a submitted URL as a direct
network target — i.e., opens a connection to the URL itself rather than to the Safe Browsing
or VirusTotal endpoints.

This must be re-confirmed with line-level evidence, not assumed from the prior audit.

**Formal Specification:**

```
FUNCTION isBugCondition_G3(url_agent_code)
  INPUT: url_agent_code (source text of url_agent.py)
  OUTPUT: boolean

  RETURN any_line_contains_network_call_targeting_submitted_url(url_agent_code)
         -- Where "network call" = requests.get/post/put, urllib.urlopen,
         --   socket.connect, subprocess with curl/wget, httpx.get/post
         -- And "targeting submitted_url" = the url variable is the
         --   first positional arg or the 'url' kwarg of that call
         --   (not SAFE_BROWSING_ENDPOINT or VT_URL_REPORT_ENDPOINT)
END FUNCTION
```

**Concrete Examples:**

- Any `requests.get(url, ...)` where `url` is the submitted URL string — VIOLATION
- `requests.post(SAFE_BROWSING_ENDPOINT + "?key=...", json=body)` where body contains
  `{"threatEntries": [{"url": url}]}` — NOT a violation (url string sent as data to
  an approved endpoint, not used as the network target)
- `requests.post(VT_URL_SUBMIT_ENDPOINT, data={"url": url})` — NOT a violation (same logic)

---

### G4 — Native-Script Classification Fails (False "No Match")

**The bug manifests when** a scam message written in native Devanagari or Telugu script is
submitted to `/api/verify-text` and returns zero typology matches — a false negative that
would let a real scam message through undetected.

Root cause: `classify()` uses fuzzy matching against English/romanized phrases. A message
like `आपका खाता ब्लॉक हो जाएगा, अभी KYC अपडेट करें` scores near zero against every typology
because the Devanagari characters do not overlap with any phrase in `TYPOLOGIES`. The fix
path is `to_english_for_matching()` in `translate.py` which, as of this audit, has never
been run with actual model weights downloaded.

**Formal Specification:**

```
FUNCTION isBugCondition_G4(input_text)
  INPUT: input_text (string)
  OUTPUT: boolean

  script_tag = _detect_indic_script(input_text)
  RETURN script_tag IS NOT None
         AND indictrans2_indic_en_model_not_loaded()
         -- Means: native script input exists but model weights are absent,
         -- so to_english_for_matching() falls back silently and classify()
         -- returns zero matches for a genuine scam message.
END FUNCTION
```

**Concrete Examples:**

- Input: `"आपका SBI KYC पेंडिंग है, आज खाता ब्लॉक हो जाएगा"`
  Expected: ≥1 typology match (fake_kyc), confidence ≥ 55
  Actual (unverified): 0 matches if indic-en model not downloaded

- Input: `"మీ విద్యుత్ కనెక్షన్ నేడు కత్తిరించబడుతుంది, వెంటనే చెల్లించండి"`
  Expected: ≥1 typology match (electricity_disconnection), confidence ≥ 55
  Actual (unverified): 0 matches if indic-en model not downloaded

- Input: `"Your electricity will be disconnected tonight"` (English)
  Expected: ≥1 typology match — this must still work AFTER the native-script fix (preservation)

---

### G5 — No-Fabrication Contract in format_scheme_layout() (C3 Re-Confirmation)

**The bug manifests when** `format_scheme_layout()` returns a generated, inferred, or
empty value for a field that has no seed data, rather than the exact specified fallback
string.

The current code reads:
```python
"eligibility": meta.get("eligibility") or "Not mentioned",
"location": meta.get("location") or "No location restriction -- apply online only",
"required_documents": meta.get("required_documents") or "Not mentioned",
"contact_info": meta.get("contact_info") or f"Visit official website: {meta.get('official_source', 'N/A')}",
```

ChromaDB metadata normalizes `None` to `""` (empty string) in `build_collection()`. The
`or` operator in Python evaluates `"" or fallback` as `fallback` — so the fallback logic
is correct as written. This must be confirmed by running it, not just reading it, because
the ChromaDB `None → ""` conversion is a runtime behavior that has never been exercised.

**Formal Specification:**

```
FUNCTION isBugCondition_G5(scheme_result, field_name)
  INPUT: scheme_result (dict returned by format_scheme_layout()),
         field_name (one of eligibility, location, required_documents, contact_info)
  OUTPUT: boolean

  seed_value = original_seed_data[field_name]
  RETURN seed_value IS None
         AND scheme_result[field_name] != EXPECTED_FALLBACK[field_name]
END FUNCTION

WHERE EXPECTED_FALLBACK = {
  "eligibility":          "Not mentioned",
  "location":             "No location restriction -- apply online only",
  "required_documents":   "Not mentioned",
  "contact_info":         "Visit official website: {official_source value}"
}
```

**Concrete Examples:**

- `PM-KISAN` seed: `location = null`, `contact_info = null`
  Expected `format_scheme_layout()` output:
  - `location` → `"No location restriction -- apply online only"`
  - `contact_info` → `"Visit official website: pmkisan.gov.in"`
- `PMAY` seed: `location = null`, `contact_info = null`
  Expected: same fallbacks, with `official_source = "pmaymis.gov.in"`

---

### G6 — local_pipeline_test.py Never Executed

**The bug manifests when** `local_pipeline_test.py` is run for the first time and fails
with an import error, a missing data file, a ChromaDB initialization error, or produces
no output — meaning the test harness itself is broken and provides no validation evidence.

**Formal Specification:**

```
FUNCTION isBugCondition_G6(execution_result)
  INPUT: execution_result (stdout, stderr, exit_code from running local_pipeline_test.py)
  OUTPUT: boolean

  RETURN execution_result.exit_code != 0
         OR execution_result.stdout_is_empty()
         OR any_sample_raises_unhandled_exception(execution_result)
         OR missing_native_script_test_cases()
         -- The test harness is written but never run; it may also be
         -- incomplete (no native Devanagari/Telugu samples)
END FUNCTION
```

**Concrete Examples:**

- Running `python local_pipeline_test.py` raises `ModuleNotFoundError: chromadb`
- The five existing English/Hinglish samples run but produce wrong classification results
  due to a threshold or normalization issue
- The test harness succeeds but has no Devanagari or Telugu test cases — the native-script
  path (G4) remains unexercised even after model download

## Expected Behavior

### Preservation Requirements

The verification mission must not change any behavior that is already correct. Fixes are
scoped strictly to closing the identified gaps.

**Unchanged Behaviors:**

- English-language scam text classification via `classify()` must continue to produce
  correct typology matches with confidence ≥ 55.
- Romanized Hinglish scam text (e.g., `"bijli katne wali hai"`) must continue to trigger
  the correct typology via panic-tag + fuzzy-match path without invoking any translation.
- `_detect_indic_script()` must return `None` for Latin-script input so `to_english_for_matching()`
  passes it through unchanged — no unnecessary translation call on English or romanized text.
- `url_agent.py` structural checks (IP URLs, shorteners, lookalike domains) must continue
  to work without any API keys configured.
- `format_scheme_layout()` must continue to return exact seed data values for fields that
  are NOT null in the seed JSON (e.g., `PM Ujjwala Yojana` has `location` and `contact_info`
  — those must not be replaced with fallbacks).
- Rate limiter must enforce the 3-requests/60-seconds window for all four endpoints
  without changes to `WINDOW_SECONDS` or `MAX_REQUESTS_PER_WINDOW`.
- `translate_text(text, "english")` must return `text` unchanged with no model call.
- The `validate_language()` guard in `api.py` must continue to return HTTP 400 for any
  `language` value not in `LANGUAGE_CODES`.
- `OcrUnavailableError` must continue to map to HTTP 503 (not 500) when Tesseract is absent.
- `AudioExtractionError` must continue to map to HTTP 503 (not 500) when ffmpeg is absent.

**Scope of Preservation:**

All inputs that do NOT trigger one of the six identified bug conditions should be
completely unaffected by this verification mission's fixes. This includes:
- Clean, non-scam messages that should return zero typology matches
- URL analysis when API keys are absent (must return `verdict: "unknown"`, never `"safe"`)
- Any endpoint returning HTTP 400/422 for malformed or empty inputs
- Scheme results for schemes where all four fields are populated in the seed JSON

## Hypothesized Root Causes

### G1 — Dependency Conflicts

1. **IndicTransToolkit git dependency**: The `@main` branch may have moved. If the
   `IndicProcessor` API changed (constructor signature, method names), `translate.py` will
   import successfully but raise `AttributeError` or `TypeError` at first call.
2. **torch + transformers version pin**: `torch==2.4.1` and `transformers==4.44.2` were
   released at compatible points, but pip's dependency resolver may pull in an incompatible
   transitive dependency (e.g., a `tokenizers` version mismatch) on Windows.
3. **sentencepiece on Windows**: `sentencepiece==0.2.0` requires a C++ build; if the wheel
   for the target Python version is absent from PyPI, pip will attempt a source build, which
   fails without Visual C++ build tools.
4. **chromadb + onnxruntime**: ChromaDB 0.5.5 pulls in `onnxruntime`; on Windows this is
   `onnxruntime` (not `onnxruntime-gpu`), and the version pin may conflict with
   `sentence-transformers==3.1.1`.

### G2 — System Dependencies (Windows-specific)

1. **Tesseract not in PATH**: On Windows, Tesseract installs to `C:\Program Files\Tesseract-OCR`
   by default and does NOT add itself to PATH — the user must do this manually.
2. **Language packs not installed**: The Windows Tesseract installer offers a language pack
   selector; `hin` and `tel` packs must be explicitly checked. The `.traineddata` files land
   in `C:\Program Files\Tesseract-OCR\tessdata\`.
3. **ocr.py error message is Linux-only**: The `OcrUnavailableError` message says
   `sudo apt-get install tesseract-ocr-hin tesseract-ocr-tel`. On Windows this is wrong; it
   must say `winget install UB-Mannheim.TesseractOCR` or point to the official installer.
4. **ffmpeg not in PATH on Windows**: ffmpeg has no official Windows package manager installer;
   users typically download a static build from ffmpeg.org or use `winget install ffmpeg`.

### G3 — URL Security Boundary

1. **VirusTotal submit path**: `_check_virustotal()` calls `requests.post(VT_URL_SUBMIT_ENDPOINT,
   data={"url": url})` — the URL is sent as form data to VirusTotal's own endpoint, not used
   as a network target. This is expected-safe but must be confirmed with exact line references.
2. **No indirect fetch via approved endpoint**: The Safe Browsing body sends the URL string
   inside a JSON payload to Google's endpoint. Google's servers evaluate it; our code never
   follows the URL. This is the approved pattern and must be documented explicitly.

### G4 — Native-Script Classification

1. **Model weights not downloaded**: The `_INDIC_EN_MODEL_NAME = "ai4bharat/indictrans2-indic-en-dist-200M"`
   checkpoint must be downloaded from Hugging Face (~400MB) on first use. On a clean machine
   with no prior `transformers` cache, `_load_indic_en_model()` will trigger a full download.
   If the machine is offline or the cache is absent, `to_english_for_matching()` silently
   falls back to the original text, producing zero matches.
2. **IndicProcessor API mismatch**: If the `IndicTransToolkit@main` API changed, the
   `processor.preprocess_batch()` or `processor.postprocess_batch()` call may fail silently
   (the `except Exception: return text` handler swallows it), again producing zero matches.
3. **Script detection threshold**: `_detect_indic_script()` requires `>= 4` native-script
   characters. A short message or one with heavy English loanwords may fall below the threshold.

### G5 — Scheme Fabrication (C3)

1. **ChromaDB None-to-empty-string conversion**: `build_collection()` converts `None` values
   to `""` before storing metadata. The `or` fallback in `format_scheme_layout()` correctly
   handles `""` as falsy. This chain has never been exercised end-to-end; the runtime path
   must be confirmed.
2. **contact_info fallback uses f-string**: The fallback `f"Visit official website: {meta.get('official_source', 'N/A')}"` will produce `"Visit official website: N/A"` if `official_source` is also absent — this is an acceptable fallback but must be confirmed against each seed record.

### G6 — Test Harness

1. **Import order / working directory**: `local_pipeline_test.py` imports from `scheme_check`
   which opens `data/schemes_seed.json` with a relative path. This only works if the script
   is run from the project root (`c:\...\satark_setu\`) — not from any subdirectory.
2. **ChromaDB persistence path**: `build_collection()` defaults to `./chroma_store`. On first
   run this directory is created; on subsequent runs it should be reused. If the working
   directory differs between runs, a second ChromaDB store may be created, wasting time.
3. **No native-script test cases**: The five existing samples are English or romanized Hinglish.
   The G4 gap (native-script classification) will remain untested unless Devanagari and Telugu
   samples are added.

## Correctness Properties

Property 1: G1 — Dependency Environment Is Fully Installable

_For any_ clean Python environment (Python 3.10+, network access available), running
`pip install -r requirements.txt` SHALL complete with exit code 0, and subsequently
every project module SHALL import without `ImportError`, `ModuleNotFoundError`, or
circular import errors.

**Validates: Requirements 1.1, 1.2, 1.3**

---

Property 2: G2 — System Dependencies Produce Correct HTTP Responses

_For any_ request to `/api/verify-image` when Tesseract is installed with `hin` and `tel`
packs, the system SHALL return a typology verdict. When Tesseract is absent or missing
language packs, the system SHALL return HTTP 503 with the `OcrUnavailableError` message
containing Windows-correct install instructions — never HTTP 500 with a raw traceback.
Analogously for `/api/verify-voice` with ffmpeg.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 6.2, 7.4, C4**

---

Property 3: G3 — URL Security Boundary Is Provably Clean

_For any_ URL string submitted to `url_agent.py`, the module SHALL make network connections
only to `SAFE_BROWSING_ENDPOINT` or `VT_URL_REPORT_ENDPOINT`/`VT_URL_SUBMIT_ENDPOINT`.
The submitted URL SHALL appear only as a value inside a request body or path-ID parameter
sent to one of those approved endpoints — never as a network target itself. This property
SHALL be confirmed with specific line-number citations from the source, not by assertion.

**Validates: Requirements 3.1, 3.2, 3.3, C1**

---

Property 4: G4 — Native-Script Scam Messages Are Correctly Classified

_For any_ input text where `_detect_indic_script()` returns a non-None language tag
(i.e., the text contains ≥ 4 Devanagari or Telugu characters and is a genuine scam message),
the fixed system SHALL return at least one typology match with confidence ≥ 55 — the same
classification that would be returned if the equivalent message were written in English.

_For any_ input text where `_detect_indic_script()` returns None (Latin-script, romanized
Hinglish, or mixed text with < 4 native-script characters), `to_english_for_matching()`
SHALL return the input unchanged with no model call, preserving existing behavior.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 9.5**

---

Property 5: G5 — Scheme Formatter Never Fabricates

_For any_ scheme retrieved from ChromaDB where a seed field (eligibility, location,
required_documents, or contact_info) was null in the source JSON, `format_scheme_layout()`
SHALL return exactly the specified fallback string for that field — not an empty string,
not a generated value, and not a partially-completed template.

_For any_ scheme where a seed field is NOT null, `format_scheme_layout()` SHALL return
the exact seed value unchanged.

**Validates: Requirements 8.2, 8.3, C3**

---

Property 6: G6 — Test Harness Executes Successfully and Covers Native-Script Input

_For any_ run of `local_pipeline_test.py` from the project root on a machine where
all dependencies are installed (Properties 1 and 2 satisfied), the script SHALL exit with
code 0, produce per-sample output for all samples including at least two native-script
(Devanagari and Telugu) samples, and the native-script samples SHALL produce typology
matches (not "No typology matched above threshold").

**Validates: Requirements 1.2, 5.1, 5.4, 12.3**

---

Property 7: C4 — All Failure Paths Degrade Gracefully

_For any_ request to any of the four API endpoints where a dependency is broken (Tesseract
absent, ffmpeg absent, IndicTrans2 model unavailable, ChromaDB uninitialized, API keys
absent), the system SHALL return an HTTP response with a 4xx or 5xx status code and a
human-readable `detail` message — never an unhandled exception reaching the ASGI layer as
HTTP 500 with a raw Python traceback.

_For any_ request with an unsupported `language` value, the system SHALL return HTTP 400.
_For any_ image request returning blank OCR output, the system SHALL return HTTP 422.
_For any_ client IP exceeding the rate limit, the system SHALL return HTTP 429.

**Validates: Requirements 4.3, 6.2, 6.3, 7.2, 7.4, 10.1, C4**

## Fix Implementation

### G1 — Dependency Install

**File**: `requirements.txt`

No code changes are expected. The fix is **execution + documentation**:

1. Run `pip install -r requirements.txt` on a clean virtual environment on the target Windows
   machine and record the exact output.
2. If `IndicTransToolkit` fails: pin to the latest working commit SHA instead of `@main`
   — change `git+https://...@main` to `git+https://...@{confirmed_sha}`.
3. If `sentencepiece` fails to build: ensure `pip >= 23` (which selects pre-built wheels
   preferentially) and that Python 3.10 or 3.11 is used (both have published wheels).
4. If `torch==2.4.1` is unavailable as a pre-built wheel for the Python/OS combination:
   substitute `torch==2.3.1` (next stable release with broad wheel coverage) and re-test.
5. Document the exact `pip install` command and output in the final verification report.

**No changes to application logic are needed for this gap.**

---

### G2 — System Dependencies (Windows)

**File**: `ocr.py` (error message fix only)

**Specific Change — Windows install instructions in error messages:**

Replace the Linux-specific `sudo apt-get install` instructions in both `OcrUnavailableError`
raise sites with Windows-correct equivalents:

```python
# TesseractNotFoundError branch — replace error message:
raise OcrUnavailableError(
    "OCR isn't available: the Tesseract binary isn't installed or isn't in PATH. "
    "Windows: download the installer from https://github.com/UB-Mannheim/tesseract/wiki "
    "and check the 'Additional language data (download)' option to include hin and tel packs. "
    "Add the install directory (e.g. C:\\Program Files\\Tesseract-OCR) to your PATH."
) from e

# TesseractError branch — replace error message:
raise OcrUnavailableError(
    "OCR failed, likely because the hin or tel language pack isn't installed. "
    "Windows: re-run the Tesseract installer and select Additional Language Data "
    f"to add Hindi (hin) and Telugu (tel) packs. (original error: {e})"
) from e
```

**File**: `voice_pipeline.py` (error message fix only)

```python
# FileNotFoundError branch — replace error message:
raise AudioExtractionError(
    "Voice/video processing isn't available: ffmpeg isn't installed or isn't in PATH. "
    "Windows: run 'winget install ffmpeg' in an elevated terminal, or download a "
    "static build from https://ffmpeg.org/download.html and add it to PATH."
) from e
```

**No logic changes — only error message strings.**

---

### G3 — URL Security Boundary Verification

No code changes are anticipated. The fix is **evidence gathering**:

1. Read `url_agent.py` and produce a line-by-line analysis of every `requests.*` call.
2. For each call, document: the function name, the line number, the network target, and
   whether the submitted URL string appears as the target or only as body data.
3. Confirm the four approved calls:
   - `requests.post(f"{SAFE_BROWSING_ENDPOINT}?key=...", json=body)` — safe, submitted URL
     is inside `body["threatInfo"]["threatEntries"][0]["url"]`
   - `requests.get(VT_URL_REPORT_ENDPOINT.format(url_id), ...)` — safe, `url_id` is the
     base64 hash of the URL, and the target is the VT API endpoint
   - `requests.post(VT_URL_SUBMIT_ENDPOINT, data={"url": url})` — safe, submitted URL is
     form data to VT's own endpoint
   - All `_structural_red_flags()` operations — no network calls, pure string analysis
4. Produce a signed evidence table in the final verification report.

---

### G4 — Native-Script Classification

**File**: `local_pipeline_test.py`

Add two native-script test samples to the `SAMPLES` list:

```python
(
    "Hindi Devanagari fake KYC (native script)",
    "प्रिय ग्राहक, आपका SBI KYC अपडेट नहीं हुआ है, आज खाता ब्लॉक हो जाएगा। "
    "तुरंत यहाँ क्लिक करें: https://sbi-kyc-secure.in/verify",
),
(
    "Telugu electricity disconnection (native script)",
    "మీ విద్యుత్ కనెక్షన్ నేడు రాత్రి కత్తిరించబడుతుంది. "
    "వెంటనే బిల్లు చెల్లించండి: https://tspdcl-pay.in/bill",
),
```

The `to_english_for_matching()` path is already wired in `api.py`'s `build_verdict()` and
in `local_pipeline_test.py` via `classify()` being called with the raw text. However,
`local_pipeline_test.py` currently calls `classify(raw_text)` directly without first calling
`to_english_for_matching()`. This is the gap: the test harness bypasses the translation step.

**File**: `local_pipeline_test.py` — Fix the pipeline call sequence:

```python
# Current (incorrect for native-script input):
classification = classify(raw_text)

# Fixed (mirrors api.py's build_verdict() exactly):
from translate import to_english_for_matching
matching_text = to_english_for_matching(raw_text)
classification = classify(matching_text)
```

This change also applies the same fix `api.py` already uses, making the test harness a
faithful replica of the production pipeline. No changes to `api.py` are needed.

---

### G5 — Scheme Formatter Verification

No code changes are anticipated. The fix is **runtime verification**:

1. Run `local_pipeline_test.py` (after G6 fixes) and inspect scheme output for PM-KISAN
   (null `location`, null `contact_info`) and PMAY (null `location`, null `contact_info`).
2. Confirm that `format_scheme_layout()` returns `"No location restriction -- apply online only"`
   and `"Visit official website: pmkisan.gov.in"` (not empty strings).
3. If the `None → ""` conversion in `build_collection()` is found to be broken (e.g., a
   future ChromaDB version changes behavior), the fallback must be moved inside
   `format_scheme_layout()` to strip None at the point of use — but this is not expected.

---

### G6 — Test Harness

**File**: `local_pipeline_test.py`

Changes required (all non-breaking to existing samples):
1. Add the `to_english_for_matching()` call before `classify()` (see G4 above).
2. Add two native-script samples to `SAMPLES` (see G4 above).
3. Add a comment at the top of `run()` documenting the required working directory:
   ```python
   # Must be run from the project root: python local_pipeline_test.py
   # (data/schemes_seed.json and ./chroma_store paths are relative to CWD)
   ```
4. Optionally: add a guard at the top of `run()` to fail fast with a clear message if
   `data/schemes_seed.json` is not found, rather than a cryptic `FileNotFoundError`.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach for each gap:

1. **Exploratory**: Run against the current (unverified/unfixed) state to surface the actual
   failure and confirm the root cause hypothesis.
2. **Fix + Preservation Checking**: Apply the minimal fix, re-run, and verify both that the
   bug condition no longer triggers and that all preservation requirements still hold.

All commands below are for Windows (cmd or PowerShell). The project root is assumed to be
`c:\Users\rohan\OneDrive\project\satark_setu`.

---

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each gap on the current unverified
codebase. Confirm or refute root cause hypotheses.

**G1 — Dependency Install (Exploratory):**
```
cd c:\Users\rohan\OneDrive\project\satark_setu
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt 2>&1 | tee install_log.txt
```
Expected counterexample if bug holds: ResolutionImpossible error, or IndicTransToolkit
clone failure, recorded in `install_log.txt`.

**G2 — System Dependencies (Exploratory):**
```
tesseract --list-langs
ffmpeg -version
```
Expected counterexample if bug holds: `tesseract` not recognized, or `hin`/`tel` absent
from lang list.

**G3 — URL Security Boundary (Exploratory — static analysis):**
```
findstr /n "requests\." url_agent.py
```
Manually inspect each match. Expected: all calls target `SAFE_BROWSING_ENDPOINT`,
`VT_URL_REPORT_ENDPOINT`, or `VT_URL_SUBMIT_ENDPOINT` — never a variable holding a
submitted URL as the first argument.

**G4 — Native-Script Classification (Exploratory):**
```python
# Run in Python REPL after activating venv:
from classify import classify
result = classify("आपका SBI KYC पेंडिंग है, आज खाता ब्लॉक हो जाएगा")
print(result["matches"])  # Expected counterexample: [] (empty, false negative)
```

**G5 — Scheme Fabrication (Exploratory):**
```python
from scheme_check import build_collection, format_scheme_layout
col = build_collection()
results = col.get(ids=["scheme_0"])  # PM-KISAN
meta = results["metadatas"][0]
print(repr(meta.get("location")))    # Expected: "" (empty string after None→"" conversion)
print(repr(meta.get("contact_info")))
layout = format_scheme_layout(meta)
print(layout["location"])            # Must be: "No location restriction -- apply online only"
print(layout["contact_info"])        # Must be: "Visit official website: pmkisan.gov.in"
```

**G6 — Test Harness (Exploratory):**
```
cd c:\Users\rohan\OneDrive\project\satark_setu
python local_pipeline_test.py
```
Expected counterexample if bug holds: ImportError, FileNotFoundError, or all five samples
complete but no native-script samples are included.

---

### Fix Checking

**Goal**: After applying each fix, verify that for all inputs where the bug condition held,
the fixed system now produces the expected behavior.

**Pseudocode (applies to all gaps):**
```
FOR ALL input WHERE isBugCondition_Gn(input) DO
  result := fixed_system(input)
  ASSERT expectedBehavior_Gn(result)
END FOR
```

**G1 Fix Check:**
- Re-run `pip install -r requirements.txt` in a fresh venv; confirm exit code 0.
- Run `python -c "import fastapi, uvicorn, pytesseract, cv2, chromadb, sentence_transformers,
  whisper, torch, transformers, sentencepiece; from IndicTransToolkit.processor import
  IndicProcessor; print('all imports OK')"`.

**G2 Fix Check:**
- With Tesseract installed + hin/tel packs: `python -c "from ocr import extract_text; print('OK')"`.
- With Tesseract absent (rename/unlink binary temporarily): call `extract_text(b"fake")` and
  assert that `OcrUnavailableError` is raised (not `TesseractNotFoundError` bubbling up).
- Verify error message contains "winget" or "UB-Mannheim" — not "apt-get".

**G3 Fix Check:**
- Produce the evidence table with line numbers. Assert zero lines where a submitted URL
  variable is used as a network target.

**G4 Fix Check:**
```python
from translate import to_english_for_matching
from classifier import classify

hindi_scam = "आपका SBI KYC पेंडिंग है, आज खाता ब्लॉक हो जाएगा"
translated = to_english_for_matching(hindi_scam)
print("Translated:", translated)   # Must not be the original Devanagari string
result = classify(translated)
print("Matches:", result["matches"])  # Must contain at least one match with confidence >= 55

telugu_scam = "మీ విద్యుత్ కనెక్షన్ నేడు రాత్రి కత్తిరించబడుతుంది, వెంటనే చెల్లించండి"
translated_te = to_english_for_matching(telugu_scam)
result_te = classify(translated_te)
print("Telugu matches:", result_te["matches"])  # Must contain at least one match
```

**G5 Fix Check:**
- Re-run the exploratory G5 script above after running `local_pipeline_test.py`; confirm
  fallback strings are exact.

**G6 Fix Check:**
- `python local_pipeline_test.py` exits 0, prints output for all 7 samples (5 original + 2
  native-script), native-script samples show ≥1 typology match.

---

### Preservation Checking

**Goal**: For all inputs where the bug condition does NOT hold, the fixed system must produce
the same result as the original system.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition_Gn(input) DO
  ASSERT fixed_system(input) = original_system(input)
END FOR
```

**Preservation Test Cases:**

1. **English scam classification is unchanged**: After G4 fix (adding `to_english_for_matching()`
   call to `local_pipeline_test.py`), re-run original five English/Hinglish samples and
   confirm identical match counts and typologies as before the fix.
   ```python
   from translate import to_english_for_matching, _detect_indic_script
   assert _detect_indic_script("Your SBI KYC is pending") is None  # Latin text: no model call
   ```

2. **URL "unknown" verdict when no API keys are set**: After any fix, confirm that submitting
   a URL with no `GOOGLE_SAFE_BROWSING_API_KEY` or `VIRUSTOTAL_API_KEY` set returns
   `{"verdict": "unknown"}` — not `"safe"`, not `"no_known_threat"`.
   ```python
   import os; os.environ.pop("GOOGLE_SAFE_BROWSING_API_KEY", None)
   os.environ.pop("VIRUSTOTAL_API_KEY", None)
   from url_agent import check_url
   result = check_url("https://example.com")
   assert result["verdict"] == "unknown"
   ```

3. **Scheme fields with real seed data are not replaced by fallbacks**: After G5 verification,
   assert that `PM Ujjwala Yojana` (which has non-null `location` and `contact_info` in seed)
   returns the exact seed values, not the fallback strings.
   ```python
   layout = format_scheme_layout({"location": "Available through local LPG distributors nationwide",
                                   "contact_info": "Local LPG distributor office", ...})
   assert layout["location"] == "Available through local LPG distributors nationwide"
   ```

4. **validate_language() still returns HTTP 400 for bad input**: After any api.py changes,
   confirm `POST /api/verify-text` with `{"text": "test", "language": "swahili"}` returns
   HTTP 400 (not 500).

5. **Rate limiter still enforces 3 requests / 60 seconds**: After any api.py or rate_limiter.py
   changes, send 4 requests from the same IP and assert the 4th returns HTTP 429.

---

### Unit Tests

- `test_url_agent.py`: Test `_structural_red_flags()` with IP URL, shortener, lookalike domain,
  and legitimate domain — all without network access.
- `test_normalize.py`: Test `normalize()` with zero-width chars, Cyrillic homoglyphs, and
  punctuation-evasion patterns.
- `test_classifier.py`: Test `classify()` with each of the six typology phrases and with a
  clean non-scam message.
- `test_scheme_check.py`: Test `format_scheme_layout()` with all-null metadata and with
  fully-populated metadata; assert exact fallback strings and exact seed values respectively.
- `test_rate_limiter.py`: Test `is_rate_limited()` with 3 then 4 requests from the same
  key within 60 seconds.
- `test_validate_language.py`: Test `validate_language()` with supported values (`"english"`,
  `"hindi"`, `"telugu"`) and with an unsupported value (`"french"`).

### Property-Based Tests

- **`test_pbt_url_security.py` — Property 3**: Generate random URL strings (using `hypothesis`
  or `pytest-randomly`). For each generated URL, call `check_url()` and assert that no
  direct network connection was made to the submitted URL. (Mock `requests` and assert
  no call received the raw URL as its first positional argument.)
- **`test_pbt_scheme_no_fabrication.py` — Property 5**: Generate random metadata dicts with
  randomly-nulled fields. Call `format_scheme_layout()` on each. Assert that any null or
  empty-string field maps to the exact expected fallback — never a generated or partial value.
- **`test_pbt_preservation_english.py` — Property 4 preservation clause**: Generate random
  Latin-script strings. Assert `_detect_indic_script()` returns None for all of them. Assert
  `to_english_for_matching()` returns input unchanged.

### Integration Tests

- **Full text pipeline with English scam**: Start the FastAPI server with `uvicorn api:app
  --port 8000`. POST `{"text": "your SBI KYC is pending update immediately", "language": "english"}`.
  Assert response contains `matches` with ≥1 entry. Assert `url_results` is present.
- **Full text pipeline with Devanagari scam**: POST `{"text": "आपका SBI KYC पेंडिंग है",
  "language": "hindi"}`. Assert ≥1 typology match. Assert response labels are in Hindi.
- **Image pipeline with missing Tesseract**: Temporarily rename tesseract binary; POST to
  `/api/verify-image`; assert HTTP 503 with `OcrUnavailableError` message.
- **Search endpoint with null-field scheme**: GET `/api/search?query=pm+kisan&language=english`.
  Assert response contains a result where `location` is `"No location restriction -- apply
  online only"` (the fallback for PM-KISAN's null location field).
- **Rate limiter integration**: Send 4 rapid POSTs to `/api/verify-text` from the same IP.
  Assert 4th response is HTTP 429.
- **Frontend loads**: Open `http://localhost:8000` in a browser (or with `requests.get()`).
  Assert HTTP 200 and that the response body contains `id="app"` or the main UI container.
