"""
OCR extraction. Runs server-side (this is a bot, not a client app --
there is no on-device ML Kit to lean on here).

Multi-language support matters because scam messages mix scripts:
pure Hindi/Telugu/Tamil, pure English, or Hinglish (Hindi written in
Roman script). Tesseract's 'lang' string is a '+'-joined list.
Extend LANGS if you add more target-state coverage.
"""

import os
import pytesseract
from preprocess import preprocess_for_ocr

# eng = English, hin = Hindi (Devanagari), tel = Telugu.
# Add more per your target states, e.g. "+tam" for Tamil, "+ben" for Bengali.
# Each extra language model adds latency, so keep this to your actual
# target geography rather than loading all 22 official languages.
LANGS = "eng+hin+tel"

# Point to standard Windows install path if present
DEFAULT_TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(DEFAULT_TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT_CMD

# Use local tessdata directory if present to load correct Hindi/Telugu models
local_tessdata = os.path.join(os.path.dirname(__file__), "tessdata")
if os.path.exists(local_tessdata):
    os.environ["TESSDATA_PREFIX"] = local_tessdata


class OcrUnavailableError(RuntimeError):
    """
    Raised when the Tesseract binary or a required language pack isn't
    installed. Distinct from "OCR ran but found no text" -- the caller
    should surface this as a clear service-configuration message (503)
    rather than the generic "couldn't read text" (422) or, worse, an
    unhandled 500 with a raw Tesseract stack trace.
    """


def extract_text(image_bytes: bytes) -> str:
    processed = preprocess_for_ocr(image_bytes)
    config = "--oem 3 --psm 6"

    try:
        text = pytesseract.image_to_string(processed, lang=LANGS, config=config)
    except pytesseract.TesseractNotFoundError as e:
        raise OcrUnavailableError(
            "OCR isn't available: the Tesseract binary isn't installed or isn't in PATH. "
            "Windows: download the installer from https://github.com/UB-Mannheim/tesseract/wiki "
            "and check the 'Additional language data (download)' option to include hin and tel packs. "
            "Add the install directory (e.g. C:\\Program Files\\Tesseract-OCR) to your PATH."
        ) from e
    except pytesseract.TesseractError as e:
        # Covers the "missing language pack" case, e.g. Tesseract is
        # installed but hin.traineddata / tel.traineddata are absent --
        # this raises a TesseractError mentioning the missing data file,
        # not TesseractNotFoundError, so it needs its own branch.
        raise OcrUnavailableError(
            "OCR failed, likely because the hin or tel language pack isn't installed. "
            "Windows: re-run the Tesseract installer and select Additional Language Data "
            f"to add Hindi (hin) and Telugu (tel) packs. (original error: {e})"
        ) from e
    return text.strip()
