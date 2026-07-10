# Satark Setu — Web App

Standalone web app (no Telegram/chat platform dependency) — one FastAPI
process serves both the API and the frontend, so the entire demo runs
from your laptop with a single command.

## Run it

1. System dependencies:
   ```
   sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-tel ffmpeg
   ```

2. Python dependencies:
   ```
   pip install -r requirements.txt --break-system-packages
   ```

3. Copy `.env.example` to `.env` and fill in:
   - **Google Safe Browsing API key** (free tier, Google Cloud Console -> enable "Safe Browsing API")
   - **VirusTotal API key** (free tier, virustotal.com account settings)

   Both are optional for the demo — without them, the URL agent still
   runs its structural checks (lookalike domains, shorteners, raw IPs)
   and honestly reports "unverified" instead of a false all-clear.

4. Run:
   ```
   python api.py
   ```

5. Open **http://localhost:8000** in your browser. That's the whole app —
   frontend and backend on one port, nothing else to start.

## What's in the interface

- **Paste text / Upload screenshot / Voice-video note** — three input
  modes into the same verification pipeline (OCR / Whisper transcription
  feed into the same classifier either way).
- **Verdict card** — scam-typology match with confidence, URL safety
  findings (color-coded: red = flagged dangerous, amber = structurally
  suspicious, teal = no known threat, grey = unverified), and a stamp
  animation on result.
- **Scheme reference card** — strict four-field layout (Eligibility,
  Location, Required Documents, Contact Info) whenever a message or
  search matches a known government scheme.
- **Scheme search** — independent of the verification flow, search by
  scheme name or situation.
- **Language switcher** (EN / हिं / తె) — reflects in both the interface
  chrome and the verdict/scheme content itself.

## Architecture

```
frontend/index.html  --calls-->  api.py (FastAPI)
                                     |
                    +----------------+----------------+
                    |                |                 |
              ocr.py + preprocess.py |          voice_pipeline.py
                    |                |                 |
              normalize.py --> classifier.py <---------+
                    |                |
              url_agent.py     scheme_check.py
              (query-only,     (local ChromaDB,
               never fetches    no live gov API
               the URL itself)  dependency)
                    |                |
                    +-------+--------+
                            |
                      translate.py
                    (EN canonical -> HI/TE
                     at display time)
```

## Critical design constraint: the URL agent never executes anything

`url_agent.py` **only sends URL strings to third-party threat-intelligence
APIs** (Google Safe Browsing, VirusTotal) and runs execution-free string
analysis. It never fetches, renders, or opens a submitted URL from this
codebase. Preserve this boundary if you extend the module.

## What's deliberately NOT here yet

- **Live MyScheme/NDAP API integration** — seeded local DB
  (`data/schemes_seed.json`) is the right call for a demo.
- **Full I4C typology phrase library** — `classifier.py` ships with six
  typologies as working examples; expand with real advisory phrasing
  before judging.
- **Chakshu/DIP auto-reporting** — proposed next step, not yet built.
- **Persistent/shared rate limiting** — `rate_limiter.py` is in-memory,
  fine for a single-process demo, won't survive a restart.

## Demo script suggestion

1. Paste a fake "KYC pending, click [suspicious link]" message → verdict
   card shows the typology match AND the URL flag together.
2. Upload a screenshot of a fake "PM-KISAN installment pending" message →
   OCR extracts text, scheme card shows the real process.
3. Upload a short voice note describing a scam call → same pipeline runs
   on the transcript.
4. Use the scheme search bar directly → shows the four-field layout
   independent of verification.
5. Switch to Hindi or Telugu mid-demo → repeat step 1, show translated
   output.
