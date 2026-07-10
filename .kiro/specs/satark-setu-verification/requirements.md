## Introduction

Satark Setu is a FastAPI-based web application that helps Indian citizens verify suspicious messages (SMS, WhatsApp screenshots, voice notes) against known scam patterns and real government scheme data, in English, Hindi, and Telugu.

The codebase has been through one prior audit pass by an AI system working in a network-isolated sandbox. That pass could read every line of code and run pure-Python logic, but **could not install pip packages requiring network access, could not download model weights, and could not run the application end-to-end.** This verification mission closes the gap between "code reads correctly" and "system runs correctly."

### Non-Negotiable Constraints

These constraints must hold at all times and must be independently re-confirmed — not assumed from the prior audit.

**C1 — URL Security Boundary**: `url_agent.py` must never fetch, render, download, or execute a submitted URL from this application's own infrastructure. Permitted operations only: send the URL string to Google Safe Browsing API, send it to VirusTotal API (they sandbox on their own systems), or run string/regex structural analysis locally. Any code path opening a direct network connection to a submitted URL must be flagged immediately — never silently patched. This prohibition applies even when making calls to approved endpoints: using an approved endpoint does not permit targeting the submitted URL itself.

**C2 — No Paid API Keys**: The system must run on free-tier or zero-cost services only. Google Safe Browsing and VirusTotal use free-account keys. Translation runs fully locally via IndicTrans2 — no cloud translation API, no key, no per-call cost.

**C3 — Scheme Formatter Must Never Fabricate**: `scheme_check.py`'s `format_scheme_layout()` must fall back to exact specified default strings when seed data has no value: missing eligibility → "Not mentioned"; missing location → "No location restriction -- apply online only"; missing required_documents → "Not mentioned"; missing contact_info → "Visit official website: {official_source}".

**C4 — Graceful Degradation on All Failure Paths**: Every failure (missing Tesseract binary/language packs, missing ffmpeg, model download failure, unsupported language value, missing API keys) must produce a clear 4xx/5xx HTTP response with a real message — never an unhandled exception reaching the user as a raw stack trace. Operations that do not depend on a broken dependency (e.g., OCR-only flows when ffmpeg is absent) must continue to function normally.

### Known Pre-Existing Limitations (Acceptable for Demo)

- In-memory rate limiter does not survive a process restart (Redis would be the production replacement)
- Local ChromaDB store is not shared across multiple server processes
- Whisper "small" model — accuracy trade-off for demo speed
- Classifier has six typologies with illustrative phrases (expand with real I4C advisory phrasing before production)
- No live MyScheme/NDAP API integration — seed JSON is the data source
- Wide-open CORS (`allow_origins=["*"]`) must be tightened before real deployment

## Requirements

### Requirement 1

**User Story:** As a verification engineer, I want to confirm the full Python dependency environment installs and runs without conflicts, so that the application can actually start.

#### Acceptance Criteria

1. When `pip install -r requirements.txt` is executed, it must complete without errors, including the `IndicTransToolkit` git dependency; this requirement fails if pip install itself fails even if dependencies happen to be available system-wide.
2. When every project module is imported, each import must resolve without ImportError or circular import error.
3. When any module references a function or variable from another module, that function or variable must exist in the target module.

### Requirement 2

**User Story:** As a verification engineer, I want to confirm all required system dependencies are present and functional, so that OCR and audio processing work.

#### Acceptance Criteria

1. When `tesseract --list-langs` is run, the output must include both `hin` and `tel`.
2. When `ffmpeg -version` is run, it must exit with code 0.
3. When the Tesseract binary is invoked, it must be accessible in PATH.
4. When ffmpeg is broken but Tesseract works, OCR-only operations (image verification) must still proceed normally — only voice/audio operations should be unavailable.

### Requirement 3

**User Story:** As a verification engineer, I want to independently re-confirm the URL security boundary, so that I can certify no submitted URL is ever fetched or executed by this application's own code.

#### Acceptance Criteria

1. When `url_agent.py` is read line by line, there must be no `requests.get()`, `requests.post()`, `urllib.request.urlopen()`, `subprocess`, or equivalent call that uses a submitted URL as the network target.
2. When `url_agent.py` makes network calls, those calls must target only the Google Safe Browsing endpoint or the VirusTotal endpoint — the submitted URL itself must never be used as a network target, even indirectly via an approved endpoint.
3. When the security boundary is confirmed, evidence must be documented with specific line references, not just assertion.

### Requirement 4

**User Story:** As a user submitting a suspicious text message, I want to receive a verdict identifying the scam type and flagging dangerous URLs, so that I can decide whether to act on the message.

#### Acceptance Criteria

1. When a POST is made to `/api/verify-text` with an English-language scam message, the response must contain at least one typology match above the confidence threshold.
2. When a POST is made to `/api/verify-text` with a clean, non-scam message, the response must contain zero typology matches.
3. When a POST is made to `/api/verify-text` with an unsupported `language` value, the response must be HTTP 400, not HTTP 500.
4. When a scam message contains a suspicious URL, the response must include URL analysis results alongside the typology verdict.
5. When no API keys are set, URL analysis must return verdict `"unknown"` — never `"safe"` or `"no_known_threat"`.

### Requirement 5

**User Story:** As a Hindi-speaking user submitting a scam message written in native Devanagari script, I want the system to correctly classify the scam, so that I am not given a false "no match" result just because my message isn't in English.

#### Acceptance Criteria

1. When a POST is made to `/api/verify-text` with a native Devanagari-script scam message, the response must contain at least one typology match above threshold — not zero matches.
2. When `to_english_for_matching()` translates Devanagari input to English, the output must preserve the scam's meaning well enough that a human reviewer agrees the classification is correct.
3. When the translated English text is passed to the classifier, it must score a real typology match confirmed by an actual confidence score above threshold — not just by the function returning non-empty output.
4. When `to_english_for_matching()` translates Telugu-script input to English, the same meaning-preservation and classification requirements apply.
5. When any input undergoes translation and the translation preserves meaning, the classifier must produce a real match — this is not limited to Devanagari script only.

### Requirement 6

**User Story:** As a user uploading a screenshot of a suspicious WhatsApp message, I want the system to OCR the image and return a verdict, so that I don't have to manually retype the message.

#### Acceptance Criteria

1. When a POST is made to `/api/verify-image` with a screenshot image containing a scam message and an image file is uploaded, the response must contain a typology match.
2. When Tesseract is missing and a POST is made to `/api/verify-image`, the response must be HTTP 503 with the `OcrUnavailableError` message — not a stack trace.
3. When an unreadable or blank image is uploaded, the response must be HTTP 422 with a clear user-facing message.

### Requirement 7

**User Story:** As a user uploading a voice recording of a scam call, I want the system to transcribe and classify the call, so that I can verify it without typing anything.

#### Acceptance Criteria

1. When a POST is made to `/api/verify-voice` with a valid audio file, the response must include a transcript and a typology verdict.
2. When audio processing partially fails (e.g., transcription succeeds but classification produces no match), the system must return partial results rather than failing completely.
3. When the response is returned, it must include both `transcript` and `detected_language` fields.
4. When ffmpeg is missing and a POST is made to `/api/verify-voice`, the response must be HTTP 503 with the `AudioExtractionError` message — not a stack trace.

### Requirement 8

**User Story:** As a user searching for a government scheme, I want to find accurate eligibility and contact information, so that I can verify a claim without risk of receiving fabricated details.

#### Acceptance Criteria

1. When a GET is made to `/api/search` with a scheme-related query, the response must contain at least one relevant scheme from the seed data.
2. When scheme results are returned, each result must contain all four required fields: `eligibility`, `location`, `required_documents`, `contact_info`.
3. When a field has null seed data, the response must use the exact default fallback strings — never a generated, inferred, or hallucinated value.
4. When an empty or whitespace-only query string is received, the response must be HTTP 400.

### Requirement 9

**User Story:** As a user, I want the translation layer to produce coherent Hindi and Telugu output, so that non-English speakers receive accurate, readable verdicts.

#### Acceptance Criteria

1. When `translate_text()` is called with English input and `target_language="hindi"`, the output must be coherent Hindi text that preserves the original meaning, confirmed by human review — not just non-emptiness.
2. When `translate_text()` is called with English input and `target_language="telugu"`, the output must be coherent Telugu text by the same standard.
3. When `translate_text()` is called with `target_language="english"`, the input must be returned unchanged with no model call.
4. When translation actually fails (model not available, OOM, or inference error), the system must fall back to English display — it must not return an error or empty string. This fallback must not trigger when translation succeeds and produces coherent output.
5. When the IndicTrans2 models are used, both the `en-indic` and `indic-en` directions must have actually downloaded, loaded, and run inference — not merely installed.

### Requirement 10

**User Story:** As a user, I want the rate limiter to actually enforce request limits, so that the service is protected from abuse during the demo.

#### Acceptance Criteria

1. When the same client IP submits more than `MAX_REQUESTS_PER_WINDOW` requests within `WINDOW_SECONDS`, the response must be HTTP 429.
2. When any of the four API endpoints (`/api/verify-text`, `/api/verify-image`, `/api/verify-voice`, `/api/search`) receives a request, the rate limiter must apply to that endpoint.

### Requirement 11

**User Story:** As a demo presenter, I want the frontend to load and complete full user flows in a real browser, so that the application can be demonstrated without relying solely on API calls.

#### Acceptance Criteria

1. When the frontend is opened at `http://localhost:8000`, it must load without JavaScript errors.
2. When a user pastes a scam message and submits via the "Paste text" tab, the UI must display a verdict card with a typology match and stamp animation.
3. When a user uploads an image via the "Upload screenshot" tab, the UI must display an OCR-based verdict card.
4. When a user enters a query in the scheme search bar, the UI must display a scheme card with all four fields.
5. When the language switcher is toggled (EN / हिं / తె), both the UI chrome and the returned verdict/scheme content must update to reflect the selected language.
6. When an API error occurs, the frontend must display a user-facing error message — not a blank or broken state. This must function even when JavaScript errors are also present in the page.

### Requirement 12

**User Story:** As a maintainer, I want a final verification report and exact run commands, so that I can reproduce the verified state and continue development from a known-good baseline.

#### Acceptance Criteria

1. When the verification mission is complete, a final report must be produced that documents all gaps found with evidence (command output or test result) for each — not just assertion.
2. When the verification mission is complete, the final report must document all fixes applied with: what was wrong, how it was found, and what changed.
3. When the verification mission is complete, the final report must provide exact commands to start the application and run the test harness from scratch.
4. When the verification mission is complete, the final report must list remaining known limitations and explain why each is acceptable for demo.
5. When the final report is delivered, all four sections (gaps, fixes, run commands, known limitations) must be present together as a complete package — partial documentation is not acceptable.
