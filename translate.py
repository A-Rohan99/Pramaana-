"""
Output translation layer.

Design choice: keep ONE canonical copy of all scam-advice text and
scheme data in English (in classifier.py / schemes_seed.json), and
translate only at display time, on the final formatted output. This
avoids maintaining three parallel, driftable copies of the same source
data -- a single edit to a typology's advice text or a scheme's
eligibility criteria stays correct in all three languages automatically.

Runs entirely locally via AI4Bharat's IndicTrans2 (MIT licensed,
https://github.com/AI4Bharat/IndicTrans2) -- no API key, no per-call
cost, and no dependency on a third-party translation service's uptime
or terms of service. Model weights download once from Hugging Face on
first run (~500MB for the distilled 200M checkpoint used here), then
every call runs fully offline.

Uses the distilled en-indic 200M checkpoint rather than the full 1.1B
model: it runs at usable latency on CPU (no GPU required), which
matters for a hackathon demo box or a low-cost server -- the 1.1B
model is meaningfully more accurate but expects a GPU for interactive
latency. Swap _MODEL_NAME below to "ai4bharat/indictrans2-en-indic-1B"
if GPU is available and higher translation quality is worth the cost.
"""

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from IndicTransToolkit.processor import IndicProcessor

# IndicTrans2 language tags (FLORES-200 style), not ISO 639-1 -- the
# library needs script information (e.g. "Deva" for Devanagari), not
# just the language name.
LANGUAGE_CODES = {
    "english": "eng_Latn",
    "hindi": "hin_Deva",
    "telugu": "tel_Telu",
}

_MODEL_NAME = "ai4bharat/indictrans2-en-indic-dist-200M"
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

_tokenizer = None
_model = None
_processor = None


def _load_model():
    """
    Lazy-loaded, module-level singleton. The model is ~200M
    parameters -- reloading it on every request would add several
    seconds of latency to every single translated response. Loaded
    once on first use and reused for the process's lifetime.
    """
    global _tokenizer, _model, _processor
    if _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(_MODEL_NAME, trust_remote_code=True)
        _model = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_NAME, trust_remote_code=True).to(_DEVICE)
        _model.eval()
        _processor = IndicProcessor(inference=True)
    return _tokenizer, _model, _processor


def translate_text(text: str, target_language: str) -> str:
    target_language = target_language.lower()
    if target_language == "english":
        return text  # canonical language, no translation needed

    tgt_code = LANGUAGE_CODES.get(target_language)
    if not tgt_code:
        raise ValueError(f"Unsupported language: {target_language}. Choose from {list(LANGUAGE_CODES)}")

    try:
        tokenizer, model, processor = _load_model()
        batch = processor.preprocess_batch([text], src_lang="eng_Latn", tgt_lang=tgt_code)
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True).to(_DEVICE)
        with torch.no_grad():
            generated = model.generate(**inputs, max_length=256, num_beams=5)
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        return processor.postprocess_batch(decoded, lang=tgt_code)[0]
    except Exception:
        # Model not yet downloaded, out of memory, first-run cold
        # start, or any inference failure shouldn't break the whole
        # response -- fall back to English rather than showing an
        # error to the user.
        return text + "\n\n[Translation unavailable right now -- showing English]"


def translate_verdict_dict(verdict: dict, target_language: str) -> dict:
    """
    Translates only the user-facing string fields of a verdict/scheme
    result dict, leaving structural fields (confidence scores, urls,
    typology keys) untouched.
    """
    translatable_keys = [
        "label", "advice", "matched_scheme", "real_process",
        "eligibility", "location", "required_documents", "contact_info",
        "message",
    ]
    translated = dict(verdict)
    for key in translatable_keys:
        if key in translated and isinstance(translated[key], str):
            translated[key] = translate_text(translated[key], target_language)
    return translated


# ---------------------------------------------------------------------------
# Input-side translation: native-script Indic text -> English, so it can
# reach classify()/scheme_check(), whose patterns are English/romanized-
# Hinglish only. Without this, a scam message written in actual Devanagari
# or Telugu script -- not romanized Hinglish -- scores close to zero
# against every typology and produces a false "no match" verdict. This
# affects all three input paths: pasted text, OCR'd screenshots (Tesseract
# already extracts Devanagari/Telugu correctly), and voice transcripts
# (Whisper transcribes in the spoken language's native script by default).
# ---------------------------------------------------------------------------

_INDIC_EN_MODEL_NAME = "ai4bharat/indictrans2-indic-en-dist-200M"
_indic_en_tokenizer = None
_indic_en_model = None
_indic_en_processor = None

# Unicode block ranges for the scripts this project supports (see
# voice_pipeline.py's SUPPORTED_LANG_NAMES). Deliberately simple code-point
# checks, not a trained language-ID model -- this only needs to answer
# "should I bother translating this", not identify a precise dialect.
_SCRIPT_RANGES = {
    "hin_Deva": (0x0900, 0x097F),  # Devanagari (Hindi)
    "tel_Telu": (0x0C00, 0x0C7F),  # Telugu
}


def _detect_indic_script(text: str) -> str | None:
    """
    Returns the FLORES-style source-language tag if the text contains
    enough characters from a known Indic script to be worth a model
    call, else None (meaning: already Latin-script/English/Hinglish,
    pass through untouched -- classifier.py's fuzzy matching already
    tolerates romanized Hinglish natively, so translating it too would
    only add latency and translation risk for no benefit).
    """
    counts = {tag: 0 for tag in _SCRIPT_RANGES}
    for ch in text:
        cp = ord(ch)
        for tag, (lo, hi) in _SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                counts[tag] += 1
    best_tag, best_count = max(counts.items(), key=lambda kv: kv[1])
    # Require a handful of script characters, not just one stray one
    # (e.g. a name or a symbol), so an otherwise-English message
    # doesn't trigger an unnecessary model call.
    return best_tag if best_count >= 4 else None


def _load_indic_en_model():
    global _indic_en_tokenizer, _indic_en_model, _indic_en_processor
    if _indic_en_model is None:
        _indic_en_tokenizer = AutoTokenizer.from_pretrained(_INDIC_EN_MODEL_NAME, trust_remote_code=True)
        _indic_en_model = AutoModelForSeq2SeqLM.from_pretrained(_INDIC_EN_MODEL_NAME, trust_remote_code=True).to(_DEVICE)
        _indic_en_model.eval()
        _indic_en_processor = IndicProcessor(inference=True)
    return _indic_en_tokenizer, _indic_en_model, _indic_en_processor


def to_english_for_matching(text: str) -> str:
    """
    Translates native-script Indic text to English for classification
    purposes only.

    IMPORTANT: only ever use this output for classify()/scheme_check().
    Never use it for url_agent.extract_urls() -- URLs must stay
    byte-for-byte as submitted; a translation model has no reason to
    preserve them verbatim and may mangle or drop them. Call
    extract_urls() on the original, untranslated raw_text.
    """
    src_lang = _detect_indic_script(text)
    if src_lang is None:
        return text

    try:
        tokenizer, model, processor = _load_indic_en_model()
        batch = processor.preprocess_batch([text], src_lang=src_lang, tgt_lang="eng_Latn")
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True).to(_DEVICE)
        with torch.no_grad():
            generated = model.generate(**inputs, max_length=256, num_beams=5)
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
        return processor.postprocess_batch(decoded, lang="eng_Latn")[0]
    except Exception:
        # If translation fails, fall back to the original text rather
        # than raising -- classify() will simply find no match, the
        # same silent-miss behavior as today, not a broken response.
        # A failed scam check must never surface as a 500.
        return text
