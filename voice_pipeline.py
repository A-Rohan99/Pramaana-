"""
Voice/audio pipeline for MP4 or voice-note uploads.

Uses Whisper (openai-whisper, runs locally, no audio leaves your
server to a third party) for transcription + language auto-detection.
Once we have text, it re-enters the SAME pipeline text/screenshots use
(normalize -> classify -> url_agent -> scheme_check) rather than
duplicating any logic -- audio is just another route to "get text",
not a separate product surface.

Language detection strategy:
  Whisper's 'small' model has unreliable language detection on short
  Indian-accented English clips (often misclassifies as Hindi).
  We fix this with a dual-transcription approach:
    1. Always transcribe in English
    2. Always transcribe in Hindi
    3. Pick whichever result looks more like real English using an
       ASCII-ratio heuristic: if >60% of the characters are ASCII
       (Latin alphabet), the speech was English. Otherwise, use Hindi.
  This eliminates the language detection step entirely and works
  perfectly for our use case of English + Hindi speaking merchants.
"""

import logging
import whisper
import subprocess
import tempfile
import os

logger = logging.getLogger("pramaan_api")

_model = None  # lazy-loaded


class AudioExtractionError(RuntimeError):
    """
    Raised when ffmpeg is missing or fails to extract audio.
    """

# Whisper language codes we surface to the user.
SUPPORTED_LANG_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
}

# English ledger-intent keywords -- if the English transcript contains ANY
# of these, it is definitely English regardless of ASCII ratio.
_ENGLISH_INTENT_KEYWORDS = [
    "paid", "pay", "received", "receive", "sent", "send", "transferred",
    "transfer", "rent", "salary", "salary", "bought", "purchase", "sold",
    "sale", "bill", "invoice", "cash", "rupees", "rs", "inr", "upi",
    "bank", "credit", "debit", "deposit", "withdraw", "loan", "emi",
    "fee", "charge", "expense", "income", "profit", "loss",
]


def _get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("small")
    return _model


def _extract_audio(input_path: str) -> str:
    """
    Convert any audio/video container to a 16kHz mono WAV.
    Whisper requires this format and processes it fastest.
    """
    out_path = tempfile.mktemp(suffix=".wav")

    ffmpeg_cmd = "ffmpeg"
    import shutil
    if not shutil.which("ffmpeg"):
        winget_path = (
            r"C:\Users\rohan\AppData\Local\Microsoft\WinGet\Packages"
            r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
            r"\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
        )
        if os.path.exists(winget_path):
            ffmpeg_cmd = winget_path

    try:
        subprocess.run(
            [ffmpeg_cmd, "-y", "-i", input_path, "-ar", "16000", "-ac", "1", out_path],
            check=True, capture_output=True,
        )
    except FileNotFoundError as e:
        raise AudioExtractionError(
            "Audio transcription isn't available: ffmpeg is not installed or not in PATH. "
            "Windows: run 'winget install ffmpeg' in an elevated terminal."
        ) from e
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else "unknown error"
        raise AudioExtractionError(
            f"Couldn't process that audio/video file (ffmpeg error: {stderr[:300]})"
        ) from e
    return out_path


def _ascii_ratio(text: str) -> float:
    """
    Fraction of non-whitespace characters that are plain ASCII (0x20-0x7E).
    English text is ~1.0; Devanagari/Telugu is ~0.0.
    """
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    ascii_chars = sum(1 for c in chars if ord(c) < 128)
    return ascii_chars / len(chars)


def _looks_like_english(text: str) -> bool:
    """
    Returns True if the transcript is most likely English.
    Two independent signals, either one is sufficient:
      1. High ASCII ratio (>60%) — catches any Latin-script output
      2. Presence of known English ledger/transaction keywords
    """
    lower = text.lower()
    if _ascii_ratio(text) > 0.60:
        return True
    if any(kw in lower for kw in _ENGLISH_INTENT_KEYWORDS):
        return True
    return False


def transcribe(file_path: str) -> dict:
    """
    Transcribe audio using a dual-language strategy:
      - Transcribe forced as English
      - Transcribe forced as Hindi
      - Select the English transcript if it looks like English,
        otherwise return the Hindi transcript.

    This completely bypasses Whisper's unreliable language auto-detection
    on short Indian-accented clips.
    """
    model = _get_model()
    audio_path = _extract_audio(file_path)

    try:
        common_opts = dict(fp16=False, condition_on_previous_text=False)

        # Transcribe in English (forced)
        en_result = model.transcribe(audio_path, language="en", **common_opts)
        en_text = en_result.get("text", "").strip()

        # Transcribe in Hindi (forced)
        hi_result = model.transcribe(audio_path, language="hi", **common_opts)
        hi_text = hi_result.get("text", "").strip()

        logger.info("Voice EN candidate: %r", en_text[:120])
        logger.info("Voice HI candidate: %r", hi_text[:120])

        # Pick the better transcript
        if _looks_like_english(en_text):
            detected_lang = "en"
            transcript = en_text
            logger.info("Voice: selected English transcript")
        else:
            detected_lang = "hi"
            transcript = hi_text
            logger.info("Voice: selected Hindi transcript (ASCII ratio EN=%.2f)", _ascii_ratio(en_text))

        # Fallback: if chosen transcript is empty, try the other
        if not transcript:
            if detected_lang == "en" and hi_text:
                detected_lang = "hi"
                transcript = hi_text
            elif detected_lang == "hi" and en_text:
                detected_lang = "en"
                transcript = en_text

    finally:
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass

    return {
        "transcript": transcript,
        "detected_language": detected_lang,
        "detected_language_name": SUPPORTED_LANG_NAMES.get(detected_lang, detected_lang),
    }
