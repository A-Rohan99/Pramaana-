# Implementation Plan

<!-- ============================================================
     PHASE 0 — ENVIRONMENT SETUP
     Must complete before any code is run or tested.
     ============================================================ -->

- [x] 0. Set up the Python environment and confirm system dependencies

  - [x] 0.1 Create and activate a virtual environment
    - Run `python -m venv .venv` from the project root `c:\Users\rohan\OneDrive\project\satark_setu`
    - Activate with `.venv\Scripts\activate`
    - _Requirements: 1.1_

  - [x] 0.2 Install Python dependencies
    - Run `pip install -r requirements.txt 2>&1 | tee install_log.txt`
    - Confirm exit code 0 and no ResolutionImpossible errors
    - If `IndicTransToolkit@main` fails, pin to the latest working commit SHA: change `git+https://...@main` to `git+https://...@{confirmed_sha}` in requirements.txt
    - If `sentencepiece` source-build fails, ensure `pip >= 23` is used (`pip install --upgrade pip`) and Python 3.10/3.11
    - If `torch==2.4.1` wheel is unavailable, substitute `torch==2.3.1` and re-test
    - Save `install_log.txt` as evidence
    - _Requirements: 1.1_

  - [x] 0.3 Verify all project modules import cleanly
    - Run: `python -c "import fastapi, uvicorn, pytesseract, cv2, chromadb, sentence_transformers, whisper, torch, transformers, sentencepiece; from IndicTransToolkit.processor import IndicProcessor; print('all imports OK')"`
    - Confirm no `ImportError`, `ModuleNotFoundError`, or circular import errors
    - _Requirements: 1.2, 1.3_

  - [x] 0.4 Verify Tesseract is installed with hin and tel language packs
    - Run `tesseract --list-langs`
    - Confirm output includes both `hin` and `tel`
    - Confirm `tesseract` binary is in PATH (command resolves)
    - _Requirements: 2.1, 2.3_

  - [x] 0.5 Verify ffmpeg is installed
    - Run `ffmpeg -version`
    - Confirm exit code 0
    - _Requirements: 2.2_


<!-- ============================================================
     PHASE 1 — BUG CONDITION EXPLORATION TESTS
     Written BEFORE any fixes. Run on the UNFIXED codebase.
     Tests are expected to FAIL where gaps exist.
     ============================================================ -->

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - G2/G4/G6 Pipeline Gaps
  - **CRITICAL**: Write and run these tests BEFORE applying any code fixes
  - **GOAL**: Surface counterexamples that confirm each gap exists on the current codebase
  - **EXPECTED OUTCOME**: Some tests FAIL — this is correct and proves the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**

  - **Scoped PBT Approach — G2 (Error Message)**: Scope to the concrete failing case: call `OcrUnavailableError` message string and assert it does NOT contain "apt-get"
  - **Scoped PBT Approach — G4 (Native-Script False Negative)**: Scope to Devanagari KYC and Telugu electricity disconnection inputs; assert `classify(raw_text)` (WITHOUT `to_english_for_matching()`) returns 0 matches
  - **Scoped PBT Approach — G6 (Test Harness)**: Run `local_pipeline_test.py` as-is and observe whether it exits cleanly and includes native-script samples

  - Create `test_unit.py` in the project root with the following exploration checks:
    - Import `ocr` and capture the `OcrUnavailableError` message strings — assert each contains "apt-get" (expected to PASS on unfixed code, confirming the bad message exists)
    - Import `classify` from `classifier`; call `classify("आपका SBI KYC पेंडिंग है, आज खाता ब्लॉक हो जाएगा")` WITHOUT translation; assert `matches == []` — expected to PASS (confirms false-negative bug exists)
    - Import `classify` from `classifier`; call `classify("మీ విద్యుత్ కనెక్షన్ నేడు రాత్రి కత్తిరించబడుతుంది")` WITHOUT translation; assert `matches == []` — expected to PASS (confirms false-negative bug exists)
    - Run `python local_pipeline_test.py` (subprocess); confirm it has no native-script samples in output (expected on unfixed code)
  - Document all counterexamples found before moving to Phase 2
  - Mark task complete when exploration tests are written, run, and counterexamples are documented
  - _Requirements: 2.4, 5.1, 5.4, 6.2, 7.4_


- [x] 2. Write preservation property tests (BEFORE implementing fixes)
  - **Property 2: Preservation** - Latin-Script Pass-Through and Existing Behaviors
  - **IMPORTANT**: Follow observation-first methodology — observe unfixed behavior on non-buggy inputs first
  - **EXPECTED OUTCOME**: All preservation tests PASS on unfixed code (confirms baseline to protect)

  - Observe: `_detect_indic_script("Your SBI KYC is pending")` returns `None` on unfixed code
  - Observe: `to_english_for_matching("bijli katne wali hai")` returns input unchanged on unfixed code
  - Observe: `classify("your electricity will be disconnected tonight")` returns ≥1 match on unfixed code
  - Observe: `format_scheme_layout({"eligibility": "All BPL families", "location": "Rural India", "required_documents": "Aadhaar", "contact_info": "1800-XXX"})` returns exact seed values (not fallbacks) on unfixed code
  - Observe: `is_rate_limited("192.168.1.1", "/api/verify-text")` returns False for first 3 calls, True for 4th on unfixed code

  - Write property-based tests in `test_pbt.py` capturing these observed behaviors:
    - **Property 2a**: For all Latin-script strings (hypothesis `text("ascii")` strategy), `_detect_indic_script(s)` returns `None` — no model call triggered
    - **Property 2b**: For all Latin-script strings, `to_english_for_matching(s)` returns `s` unchanged
    - **Property 2c**: For randomly-nulled metadata dicts (hypothesis `dictionaries` strategy), `format_scheme_layout()` returns exact fallback strings for null/empty fields and exact seed values for non-null fields — never empty, never fabricated
    - **Property 2d**: For random URL strings (hypothesis `from_regex` strategy), `check_url()` (with mocked `requests`) never calls `requests.get/post` with the raw URL string as the first positional arg
  - Run `pytest test_pbt.py` on unfixed code; confirm all preservation tests PASS
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 5.2, 5.5, 8.3, 10.1_


<!-- ============================================================
     PHASE 2 — CODE FIXES (G2 and G4/G6)
     Minimal, scoped changes only — nothing beyond the identified gaps.
     ============================================================ -->

- [x] 3. Apply code fixes for G2, G4, and G6

  - [x] 3.1 Fix ocr.py — replace Linux-only error messages with Windows-correct instructions
    - In the `TesseractNotFoundError` branch, replace the error message with:
      `"OCR isn't available: the Tesseract binary isn't installed or isn't in PATH. Windows: download the installer from https://github.com/UB-Mannheim/tesseract/wiki and check the 'Additional language data (download)' option to include hin and tel packs. Add the install directory (e.g. C:\\Program Files\\Tesseract-OCR) to your PATH."`
    - In the `TesseractError` branch (language pack missing), replace with:
      `"OCR failed, likely because the hin or tel language pack isn't installed. Windows: re-run the Tesseract installer and select Additional Language Data to add Hindi (hin) and Telugu (tel) packs. (original error: {e})"`
    - No logic changes — error message strings only
    - _Bug_Condition: isBugCondition_G2 — ocr.py error messages contain Linux-only "sudo apt-get install" instructions_
    - _Expected_Behavior: OcrUnavailableError message contains "UB-Mannheim" or "winget" and no "apt-get"_
    - _Preservation: OcrUnavailableError still maps to HTTP 503 (not 500) in api.py; no logic changes_
    - _Requirements: 2.4, 6.2, C4_

  - [x] 3.2 Fix voice_pipeline.py — replace Linux-only ffmpeg error message with Windows-correct instructions
    - In the `FileNotFoundError` branch, replace the error message with:
      `"Voice/video processing isn't available: ffmpeg isn't installed or isn't in PATH. Windows: run 'winget install ffmpeg' in an elevated terminal, or download a static build from https://ffmpeg.org/download.html and add it to PATH."`
    - No logic changes — error message string only
    - _Bug_Condition: isBugCondition_G2 — voice_pipeline.py error message contains Linux-only instructions_
    - _Expected_Behavior: AudioExtractionError message contains "winget" and no "apt-get"_
    - _Preservation: AudioExtractionError still maps to HTTP 503 (not 500) in api.py_
    - _Requirements: 2.4, 7.4, C4_

  - [x] 3.3 Fix local_pipeline_test.py — add to_english_for_matching() call before classify()
    - Add `from translate import to_english_for_matching` at the top of the file
    - Change the pipeline call from `classification = classify(raw_text)` to:
      ```python
      matching_text = to_english_for_matching(raw_text)
      classification = classify(matching_text)
      ```
    - This mirrors the production pipeline in `api.py`'s `build_verdict()` exactly
    - _Bug_Condition: isBugCondition_G4/G6 — local_pipeline_test.py calls classify() directly on raw native-script text, bypassing to_english_for_matching()_
    - _Expected_Behavior: Native-script samples produce ≥1 typology match with confidence ≥ 55_
    - _Preservation: Existing 5 English/Hinglish samples produce identical match counts and typologies as before (Latin text passes through to_english_for_matching() unchanged)_
    - _Requirements: 5.1, 5.3, 5.4, 5.5_

  - [x] 3.4 Fix local_pipeline_test.py — add two native-script test samples
    - Add to the SAMPLES list:
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
    - _Bug_Condition: isBugCondition_G6 — test harness has no native-script samples, G4 path never exercised_
    - _Expected_Behavior: Script outputs per-sample results for all 7 samples; native-script samples show ≥1 typology match_
    - _Preservation: Original 5 samples unaffected_
    - _Requirements: 5.1, 5.4, 12.3_

  - [x] 3.5 Fix local_pipeline_test.py — add working-directory comment and fast-fail guard
    - Add at top of `run()`:
      ```python
      # Must be run from the project root: python local_pipeline_test.py
      # (data/schemes_seed.json and ./chroma_store paths are relative to CWD)
      ```
    - Optionally add a guard: if `not os.path.exists("data/schemes_seed.json"): sys.exit("ERROR: Run from project root")`
    - _Requirements: 12.3_


<!-- ============================================================
     PHASE 3 — UNIT AND PROPERTY-BASED TESTS
     Run after code fixes, before server-based integration tests.
     ============================================================ -->

- [x] 4. Create and run unit tests (test_unit.py)

  - [x] 4.1 Write unit tests for url_agent structural checks
    - Test `_structural_red_flags()` with an IP-format URL (e.g. `http://192.168.1.1/login`) — assert flag returned
    - Test with a known URL shortener (e.g. `http://bit.ly/abc`) — assert flag returned
    - Test with a lookalike domain (e.g. `http://sbi-kyc-secure.in`) — assert flag returned
    - Test with a legitimate domain (e.g. `https://sbi.co.in`) — assert no flag for structural reasons
    - All tests run without any network access (no API keys set)
    - _Requirements: 3.1, 3.2_

  - [x] 4.2 Write unit tests for normalize()
    - Test with zero-width characters (U+200B, U+FEFF) — assert stripped from output
    - Test with Cyrillic homoglyphs (e.g. Cyrillic 'а' in place of Latin 'a') — assert normalized
    - Test with punctuation-evasion patterns (e.g. dots between letters) — assert handled
    - _Requirements: 1.2_

  - [x] 4.3 Write unit tests for classify()
    - Test each of the six typology trigger phrases — assert ≥1 match with confidence ≥ 55 for each
    - Test with a clean, non-scam message (e.g. "Please call me back when you are free") — assert 0 matches
    - _Requirements: 4.1, 4.2_

  - [x] 4.4 Write unit tests for scheme_check no-fabrication (format_scheme_layout)
    - Test with all-null metadata dict — assert every field returns the exact specified fallback string:
      - `eligibility` → `"Not mentioned"`
      - `location` → `"No location restriction -- apply online only"`
      - `required_documents` → `"Not mentioned"`
      - `contact_info` → `"Visit official website: {official_source value}"`
    - Test with fully-populated metadata — assert every field returns the exact seed value (not a fallback)
    - _Bug_Condition: isBugCondition_G5 — null seed field produces wrong output instead of exact fallback_
    - _Expected_Behavior: format_scheme_layout() returns exact EXPECTED_FALLBACK strings for null fields_
    - _Preservation: Non-null fields return exact seed values unchanged_
    - _Requirements: 8.2, 8.3, C3_

  - [x] 4.5 Write unit tests for rate_limiter
    - Send 3 requests from the same key within 60 seconds — assert all return False (not rate-limited)
    - Send a 4th request — assert returns True (rate-limited, HTTP 429 trigger)
    - _Requirements: 10.1_

  - [x] 4.6 Write unit tests for validate_language()
    - Test with `"english"`, `"hindi"`, `"telugu"` — assert each is accepted (no HTTP 400)
    - Test with `"french"`, `"swahili"`, `""` — assert each raises HTTP 400
    - _Requirements: 4.3_

  - [x] 4.7 Run all unit tests and confirm they pass
    - Run `pytest test_unit.py -v` from the project root
    - All tests must pass; fix any failures before proceeding
    - _Requirements: 1.2, 3.1, 4.3, 8.3, 10.1_


- [x] 5. Create and run property-based tests (test_pbt.py)

  - [x] 5.1 Write PBT for URL security boundary (Property 3 — C1 re-confirmation)
    - **Property 1: Bug Condition** - URL Security Boundary Violation
    - Use `hypothesis` with `from_regex(r'https?://[a-zA-Z0-9./?=&_-]+')`  strategy to generate random URL strings
    - For each generated URL, mock `requests` and call `check_url(url)`
    - Assert that `requests.get` and `requests.post` are NEVER called with the raw `url` as the first positional argument
    - Assert all `requests.*` calls target only `SAFE_BROWSING_ENDPOINT`, `VT_URL_REPORT_ENDPOINT`, or `VT_URL_SUBMIT_ENDPOINT`
    - Use `unittest.mock.patch("requests.get")` and `unittest.mock.patch("requests.post")`
    - Run on unfixed code — expected to PASS (confirms boundary is clean) or FAIL (confirms violation if found)
    - Document any counterexample found
    - _Requirements: 3.1, 3.2, 3.3, C1_

  - [x] 5.2 Write PBT for scheme no-fabrication (Property 5 — C3 re-confirmation)
    - **Property 2: Preservation** - Scheme Formatter Never Fabricates
    - Use `hypothesis` `fixed_dictionaries` strategy to generate metadata dicts with randomly-nulled fields
    - For each generated dict, call `format_scheme_layout(meta)` and assert:
      - If `meta["eligibility"]` is `None` or `""`, output `eligibility` == `"Not mentioned"`
      - If `meta["location"]` is `None` or `""`, output `location` == `"No location restriction -- apply online only"`
      - If `meta["required_documents"]` is `None` or `""`, output `required_documents` == `"Not mentioned"`
      - If `meta["contact_info"]` is `None` or `""`, output `contact_info` starts with `"Visit official website:"`
      - If any field is non-null and non-empty, the output must equal the exact seed value
    - Run on unfixed code — expected to PASS (confirms no fabrication) or FAIL (confirms fabrication bug)
    - _Requirements: 8.2, 8.3, C3_

  - [x] 5.3 Write PBT for Latin-script preservation (Property 4 preservation clause)
    - Use `hypothesis` `text(alphabet=characters(whitelist_categories=('Lu','Ll','Nd','Zs','Po')))` strategy
    - For each generated Latin-script string, assert `_detect_indic_script(s)` returns `None`
    - For each generated Latin-script string, assert `to_english_for_matching(s)` returns `s` unchanged (no model call)
    - Run on unfixed code — expected to PASS (confirms preservation baseline)
    - _Requirements: 5.2, 5.5_

  - [x] 5.4 Run all property-based tests and confirm they pass
    - Run `pytest test_pbt.py -v` from the project root
    - All tests must pass on unfixed code (they confirm existing correct behaviors)
    - Document any counterexample found — if any PBT fails on unfixed code, it reveals a preservation violation
    - _Requirements: 3.1, 8.3, 5.5_


<!-- ============================================================
     PHASE 4 — VERIFY BUG CONDITION EXPLORATION TEST NOW PASSES
     Re-run the same tests from Phase 1 on the FIXED codebase.
     ============================================================ -->

- [x] 6. Verify bug condition exploration test now passes (after fixes)

  - [x] 6.1 Verify G2 fix — error messages no longer contain Linux-only instructions
    - **Property 1: Expected Behavior** - Windows-Correct Error Messages in ocr.py and voice_pipeline.py
    - **IMPORTANT**: Re-run the SAME exploration assertions from task 1 — do NOT write new tests
    - Re-run the assertion that `OcrUnavailableError` message does NOT contain "apt-get"
    - Assert the message DOES contain "UB-Mannheim" or the Windows installer URL
    - Re-run the assertion that `AudioExtractionError` message does NOT contain "apt-get"
    - Assert the message DOES contain "winget" or "ffmpeg.org"
    - **EXPECTED OUTCOME**: These assertions now PASS (confirms G2 fix is effective)
    - _Requirements: 2.4, 6.2, 7.4, C4_

  - [x] 6.2 Verify G4 fix — native-script scam messages now produce typology matches
    - **Property 1: Expected Behavior** - Native-Script Classification Via to_english_for_matching()
    - **IMPORTANT**: Re-run the SAME counterexample inputs from task 1 exploration — do NOT write new tests
    - Run in Python REPL (venv active, IndicTrans2 model downloaded):
      ```
      from translate import to_english_for_matching
      from classifier import classify
      hindi_scam = "आपका SBI KYC पेंडिंग है, आज खाता ब्लॉक हो जाएगा"
      translated = to_english_for_matching(hindi_scam)
      result = classify(translated)
      ```
    - Assert `translated` is NOT the original Devanagari string (model actually ran)
    - Assert `result["matches"]` contains ≥1 entry with confidence ≥ 55
    - Repeat with Telugu input: `"మీ విద్యుత్ కనెక్షన్ నేడు రాత్రి కత్తిరించబడుతుంది, వెంటనే చెల్లించండి"`
    - Assert ≥1 match with confidence ≥ 55
    - **EXPECTED OUTCOME**: Both assertions PASS (confirms G4 fix is effective)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 6.3 Verify G6 fix — local_pipeline_test.py exits 0 with all 7 samples and native-script matches
    - **Property 1: Expected Behavior** - Test Harness Executes Successfully with Native-Script Coverage
    - **IMPORTANT**: Re-run the SAME script as explored in task 1 — the fixed version
    - Run `python local_pipeline_test.py` from `c:\Users\rohan\OneDrive\project\satark_setu`
    - Assert exit code 0
    - Assert output contains per-sample results for all 7 samples (5 original + 2 native-script)
    - Assert the Hindi Devanagari sample shows ≥1 typology match (not "No typology matched above threshold")
    - Assert the Telugu sample shows ≥1 typology match
    - Save full output as evidence for the final report
    - **EXPECTED OUTCOME**: Script exits 0, all 7 samples processed, native-script samples matched
    - _Requirements: 1.2, 5.1, 5.4, 12.3_

  - [x] 6.4 Verify G5 — scheme formatter fallback strings are exact (runtime confirmation)
    - Run the G5 exploratory script on the live ChromaDB (after local_pipeline_test.py has run at least once):
      ```
      from scheme_check import build_collection, format_scheme_layout
      col = build_collection()
      results = col.get(ids=["scheme_0"])
      meta = results["metadatas"][0]
      layout = format_scheme_layout(meta)
      ```
    - Assert `layout["location"]` == `"No location restriction -- apply online only"` (PM-KISAN null location)
    - Assert `layout["contact_info"]` starts with `"Visit official website: pmkisan.gov.in"`
    - Repeat for PMAY (null location and contact_info)
    - Assert `PM Ujjwala Yojana` fields with non-null seed values return exact seed values, not fallbacks
    - _Requirements: 8.2, 8.3, C3_


<!-- ============================================================
     PHASE 5 — VERIFY PRESERVATION TESTS STILL PASS
     Re-run Phase 2 tests on the FIXED codebase.
     ============================================================ -->

- [x] 7. Verify preservation tests still pass after all fixes

  - [x] 7.1 Re-run PBT preservation suite on fixed codebase
    - **Property 2: Preservation** - Latin-Script Pass-Through and Existing Behaviors Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run `pytest test_pbt.py -v` on the fixed codebase
    - All property-based tests must still pass (confirms no regressions)
    - Specifically confirm:
      - `_detect_indic_script("Your SBI KYC is pending")` still returns `None`
      - `to_english_for_matching("bijli katne wali hai")` still returns input unchanged (romanized Hinglish: no model call)
      - `classify("your electricity will be disconnected tonight")` still returns ≥1 match (English path unchanged)
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions from G4 fix)
    - _Requirements: 5.2, 5.5_

  - [x] 7.2 Verify URL "unknown" verdict when no API keys are set (preservation)
    - With `GOOGLE_SAFE_BROWSING_API_KEY` and `VIRUSTOTAL_API_KEY` unset (or `.env` not loaded):
      ```python
      import os
      os.environ.pop("GOOGLE_SAFE_BROWSING_API_KEY", None)
      os.environ.pop("VIRUSTOTAL_API_KEY", None)
      from url_agent import check_url
      result = check_url("https://example.com")
      assert result["verdict"] == "unknown"
      ```
    - Assert result is `"unknown"` — never `"safe"` or `"no_known_threat"`
    - _Requirements: 4.5_

  - [x] 7.3 Verify G3 security boundary with line-number evidence table (static analysis)
    - Run `findstr /n "requests\." url_agent.py` from the project root
    - For each match, record: function name, line number, network target variable, and classification
    - Produce a signed evidence table with columns: Line | Function | Call | Target | Safe?
    - Confirm all calls target only `SAFE_BROWSING_ENDPOINT`, `VT_URL_REPORT_ENDPOINT`, or `VT_URL_SUBMIT_ENDPOINT`
    - Confirm zero lines where a submitted URL variable is the first positional argument to any `requests.*` call
    - The submitted URL must appear only as a value inside a request body (`json=body`) or form data (`data={"url": url}`) — never as the network target
    - _Requirements: 3.1, 3.2, 3.3, C1_

  - [x] 7.4 Verify validate_language() still returns HTTP 400 for unsupported language (preservation)
    - Run `pytest test_unit.py::test_validate_language -v` to re-confirm
    - Assert `POST /api/verify-text` with `language="french"` returns HTTP 400 (not HTTP 500)
    - _Requirements: 4.3_

  - [x] 7.5 Verify rate limiter still fires at the 4th request (preservation)
    - Run `pytest test_unit.py::test_rate_limiter -v` to re-confirm
    - Assert 4th request from same IP returns HTTP 429
    - _Requirements: 10.1, 10.2_


<!-- ============================================================
     PHASE 6 — SERVER-BASED INTEGRATION TESTS
     Server must be running before these tasks begin.
     Start the server manually: uvicorn api:app --reload --port 8000
     ============================================================ -->

- [x] 8. Run server-based integration and endpoint tests
  - **PREREQUISITE**: Start the FastAPI server manually before this phase:
    `uvicorn api:app --reload --port 8000` from `c:\Users\rohan\OneDrive\project\satark_setu`

  - [x] 8.1 Verify English text verification endpoint
    - `curl -s -X POST http://localhost:8000/api/verify-text -H "Content-Type: application/json" -d "{\"text\": \"Your SBI KYC is pending, update immediately or account will be blocked\", \"language\": \"english\"}"`
    - Assert response contains `matches` with ≥1 typology entry
    - Assert response contains `url_results` field
    - _Requirements: 4.1, 4.4_

  - [x] 8.2 Verify clean (non-scam) message returns zero matches
    - `curl -s -X POST http://localhost:8000/api/verify-text -H "Content-Type: application/json" -d "{\"text\": \"Please call me back when you are free\", \"language\": \"english\"}"`
    - Assert response contains `matches` with 0 entries
    - _Requirements: 4.2_

  - [x] 8.3 Verify Devanagari scam message is classified via API
    - POST `{"text": "आपका SBI KYC पेंडिंग है, आज खाता ब्लॉक हो जाएगा", "language": "hindi"}`
    - Assert ≥1 typology match in response
    - Assert response labels/content are in Hindi
    - _Requirements: 5.1, 5.3_

  - [x] 8.4 Verify unsupported language param returns HTTP 400 (not HTTP 500)
    - `curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/verify-text -H "Content-Type: application/json" -d "{\"text\": \"test\", \"language\": \"french\"}"`
    - Assert HTTP status code is 400
    - _Requirements: 4.3_

  - [x] 8.5 Verify rate limiter fires at 4th request via real server
    - Send 4 rapid POST requests to `/api/verify-text` from the same IP (use a loop in cmd or PowerShell)
    - Assert the 4th response has HTTP status 429
    - Example (PowerShell):
      ```powershell
      1..4 | ForEach-Object { Invoke-WebRequest -Uri http://localhost:8000/api/verify-text -Method POST -ContentType 'application/json' -Body '{"text":"test","language":"english"}' -ErrorAction SilentlyContinue | Select-Object StatusCode }
      ```
    - _Requirements: 10.1, 10.2_

  - [x] 8.6 Verify scheme search endpoint with null-field scheme
    - `curl -s "http://localhost:8000/api/search?query=pm+kisan&language=english"`
    - Assert response contains a result where `location` == `"No location restriction -- apply online only"`
    - Assert all four fields (`eligibility`, `location`, `required_documents`, `contact_info`) are present
    - _Requirements: 8.1, 8.2, 8.3_

  - [x] 8.7 Verify empty search query returns HTTP 400
    - `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/search?query=&language=english"`
    - Assert HTTP status code is 400
    - _Requirements: 8.4_

  - [x] 8.8 Verify no-API-keys URL check returns "unknown" not "safe" (server-level)
    - With API keys unset in `.env`, restart server and POST a URL-containing message
    - Assert `url_results` in response contains `verdict: "unknown"` — never `"safe"` or `"no_known_threat"`
    - _Requirements: 4.5_

  - [x] 8.9 Verify frontend loads at http://localhost:8000
    - `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000`
    - Assert HTTP 200
    - Open in a real browser; assert no JavaScript errors in the console on initial load
    - _Requirements: 11.1_


<!-- ============================================================
     PHASE 7 — FINAL CHECKPOINT AND VERIFICATION REPORT
     ============================================================ -->

- [x] 9. Checkpoint — Ensure all tests pass and produce final verification report

  - [x] 9.1 Run the complete test suite one final time
    - Run `pytest test_unit.py test_pbt.py -v` from the project root
    - All tests must pass; resolve any failures before proceeding
    - If failures remain, ask the user before proceeding
    - _Requirements: 1.2, 3.1, 4.3, 5.5, 8.3, 10.1_

  - [x] 9.2 Run local_pipeline_test.py and capture final output
    - Run `python local_pipeline_test.py > pipeline_output.txt 2>&1`
    - Confirm exit code 0
    - Confirm all 7 samples appear in output
    - Confirm Hindi and Telugu samples show typology matches
    - Save `pipeline_output.txt` as evidence
    - _Requirements: 1.2, 5.1, 5.4, 12.3_

  - [x] 9.3 Confirm IndicTrans2 models actually ran inference (not just installed)
    - During the G4 fix check (task 6.2), confirm that `to_english_for_matching()` returned translated (non-Devanagari) text — not the original input
    - This proves both `en-indic` and `indic-en` directions downloaded, loaded, and ran
    - _Requirements: 9.5_

  - [x] 9.4 Produce final verification report
    - Document all gaps found with evidence (command output or test result) — not just assertion:
      - G1: attach `install_log.txt` or confirm clean install
      - G2: show before/after error message strings with line references
      - G3: attach the signed line-number evidence table from task 7.3
      - G4: show `to_english_for_matching()` output and classify result for both native-script samples
      - G5: show `format_scheme_layout()` output for PM-KISAN and PMAY null fields
      - G6: attach `pipeline_output.txt`
    - Document all fixes applied: what was wrong, how it was found, what changed (file + line number)
    - Provide exact commands to start the application and run the test harness from scratch on Windows
    - List remaining known limitations and explain why each is acceptable for demo:
      - In-memory rate limiter does not survive process restart
      - Local ChromaDB not shared across multiple server processes
      - Whisper "small" model — accuracy vs. speed trade-off
      - Classifier uses six typologies with illustrative phrases (not real I4C advisory phrasing)
      - No live MyScheme/NDAP API — seed JSON is the data source
      - Wide-open CORS — must be tightened before real deployment
    - All four sections (gaps, fixes, run commands, known limitations) must be present together
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
