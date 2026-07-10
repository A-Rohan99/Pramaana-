"""
Normalize raw (OCR'd or pasted) text before pattern matching.

Four jobs:
  1. Strip characters scammers use to break exact-string filters
     (zero-width spaces, lookalike Unicode homoglyphs, stray punctuation
     wedged into brand names like "S.B.1" for "SBI").
  2. Collapse common Hinglish/cross-lingual panic vocabulary to a single
     canonical tag, so "bijli", "bill", "electricity" all resolve to
     the same signal instead of three separate weak matches.
  3. Tag transaction vocabulary (credited, debited, received, paid) so
     the pipeline can detect payment messages for ledger extraction.
  4. Lowercase + collapse whitespace for consistent downstream fuzzy
     matching (see classifier.py, which uses edit-distance, not exact
     match, precisely because step 1 will never be 100% complete).
"""

import re
import unicodedata

# Zero-width and invisible-format characters scammers insert to break
# keyword filters.
ZERO_WIDTH_CHARS = [
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\ufeff",  # BOM / zero-width no-break space
    "\u00ad",  # soft hyphen
]

# Common Cyrillic/Greek lookalikes mapped to their Latin equivalents.
# Extended to cover UPI handle spoofing (e.g. 'sЬi@upi' where 'Ь' is Cyrillic).
HOMOGLYPH_MAP = {
    "а": "a", "е": "e", "і": "i", "о": "o", "р": "p", "с": "c", "у": "y",
    "х": "x", "Ь": "b", "ѕ": "s", "ї": "i",                              # Cyrillic
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I",
    "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T",
    "Υ": "Y", "Χ": "X",                                                   # Greek
}

# High-frequency cross-lingual panic vocabulary -> canonical tag.
# Kept intentionally small and specific; expand from real scam samples
# rather than guessing broadly, or you'll get false positives on
# ordinary conversation.
HINGLISH_TAGS = {
    # Fraud/scam signals
    "electricity": "ELECTRICITY", "bijli": "ELECTRICITY", "bijlee": "ELECTRICITY", "bjl": "ELECTRICITY",
    "kyc": "KYC", "kewaisi": "KYC",
    "customs": "CUSTOMS", "parcel": "CUSTOMS", "courier": "CUSTOMS",
    "arrest": "ARREST", "police": "ARREST", "digital arrest": "ARREST",
    "refund": "REFUND", "cashback": "REFUND", "vaapas": "REFUND",
    "otp": "OTP", "pin": "PIN", "upi pin": "PIN",
    "turant": "URGENT", "abhi": "URGENT", "immediately": "URGENT", "jaldi": "URGENT",
    "kata jayega": "URGENT", "block": "URGENT", "suspend": "URGENT",
    # Transaction / bookkeeping signals (for ledger extraction)
    "credited": "CREDIT", "credit": "CREDIT", "received": "CREDIT",
    "mila": "CREDIT", "aaya": "CREDIT", "jama": "CREDIT",
    "debited": "DEBIT", "debit": "DEBIT", "sent": "DEBIT",
    "paid": "DEBIT", "transferred": "DEBIT", "bheja": "DEBIT",
    "upi": "TRANSACTION", "neft": "TRANSACTION", "imps": "TRANSACTION",
    "transaction": "TRANSACTION", "txn": "TRANSACTION", "payment": "TRANSACTION",
}


def strip_invisible_and_homoglyphs(text: str) -> str:
    for ch in ZERO_WIDTH_CHARS:
        text = text.replace(ch, "")
    text = "".join(HOMOGLYPH_MAP.get(ch, ch) for ch in text)
    # NFKC normalization folds a lot of remaining visual-lookalike
    # Unicode variants (fullwidth characters, etc.) into their ASCII form.
    text = unicodedata.normalize("NFKC", text)
    return text


def collapse_punctuation_evasion(text: str) -> str:
    """
    Turns 'S.B.1', 'S-B-I', 'S B I' into 'sbi' so fuzzy matching against
    known brand/institution names still fires. This is intentionally
    aggressive -- it runs only inside short token windows, not across
    the whole message, to avoid mangling real sentences.
    """
    def collapse_token(match: re.Match) -> str:
        return re.sub(r"[.\-\s]", "", match.group(0))

    # Matches short runs of single letters/digits separated by dots,
    # dashes, or spaces -- e.g. "S.B.1", "K Y C", "P-M-K-I-S-A-N".
    text = re.sub(r"\b(?:[A-Za-z0-9][.\-\s]){2,}[A-Za-z0-9]\b", collapse_token, text)
    return text


def tag_panic_vocabulary(text_lower: str) -> list[str]:
    tags_found = []
    for phrase, tag in HINGLISH_TAGS.items():
        if phrase in text_lower:
            tags_found.append(tag)
    return sorted(set(tags_found))


def normalize(raw_text: str) -> dict:
    text = strip_invisible_and_homoglyphs(raw_text)
    text = collapse_punctuation_evasion(text)
    text_lower = re.sub(r"\s+", " ", text).strip().lower()

    return {
        "clean_text": text_lower,
        "panic_tags": tag_panic_vocabulary(text_lower),
    }
