"""
General scam-pattern classifier, seeded from I4C-documented typologies.

This is the primary/general-purpose module -- it should catch the bulk
of scam volume (digital arrest, courier/customs, task-based job scams,
fake KYC, electricity disconnection, refund/QR scams), NOT just
government-scheme fraud. The MyScheme cross-check (scheme_check.py) is
a specialized second module layered on top of this, used only when a
message specifically claims to be about a government scheme or DBT
payment.

Uses fuzzy matching (edit distance), not exact string match, because
normalize.py can only catch known evasion tricks -- it will never be
complete, so the matcher itself needs tolerance for near-misses.
"""

from rapidfuzz import fuzz
from normalize import normalize

# Each typology: a name, a set of representative phrases (seed these
# from real I4C advisories / cybercrime portal samples before the
# hackathon -- these are illustrative starting points, not a finished
# dataset), and the panic-tag(s) from normalize.py that co-occur with it.
TYPOLOGIES = {
    "digital_arrest": {
        "label": "Digital arrest / fake law enforcement",
        "phrases": [
            "you are under digital arrest",
            "your aadhaar is linked to a crime",
            "cbi investigation against you",
            "do not disconnect this call or you will be arrested",
            "stay on video call until verification complete",
        ],
        "tags": ["ARREST"],
        "advice": "Real police never conduct arrests, investigations, or "
                  "'verification' over a phone or video call, and never "
                  "demand you stay on a call under threat.",
    },
    "courier_customs": {
        "label": "Courier / customs parcel scam",
        "phrases": [
            "illegal parcel found in your name",
            "your courier is held at customs",
            "package containing banned items",
            "pay customs duty to release your parcel",
        ],
        "tags": ["CUSTOMS"],
        "advice": "Customs and courier companies do not collect duty "
                  "payments over phone calls or UPI -- verify directly "
                  "on the courier company's official app or website.",
    },
    "fake_kyc": {
        "label": "Fake KYC update request",
        "phrases": [
            "your kyc is pending please update immediately",
            "your account will be blocked update kyc now",
            "click link to complete kyc verification",
            "share otp to complete kyc",
        ],
        "tags": ["KYC", "URGENT"],
        "advice": "Banks never ask for OTP, PIN, or a link-based 'KYC "
                  "update' by SMS or WhatsApp -- KYC updates happen at a "
                  "branch or the bank's official app only.",
    },
    "electricity_disconnection": {
        "label": "Fake electricity disconnection notice",
        "phrases": [
            "your electricity will be disconnected tonight",
            "pay your electricity bill immediately to avoid disconnection",
            "bijli katne wali hai abhi bill jama karein",
        ],
        "tags": ["ELECTRICITY", "URGENT"],
        "advice": "Electricity boards send disconnection notices through "
                  "official channels with advance notice, not same-day "
                  "WhatsApp/SMS threats demanding instant UPI payment.",
    },
    "refund_qr": {
        "label": "Fake refund / cashback QR scam",
        "phrases": [
            "scan this qr code to receive your refund",
            "enter your upi pin to receive cashback",
            "scan qr to claim your prize",
        ],
        "tags": ["REFUND", "PIN"],
        "advice": "You never need to scan a QR code or enter your UPI PIN "
                  "to RECEIVE money -- PIN entry only ever sends money out.",
    },
    "task_job_scam": {
        "label": "Task-based / part-time job scam",
        "phrases": [
            "like videos and earn daily income",
            "join our telegram channel for part time job",
            "complete simple tasks earn money from home",
            "pay registration fee to start earning",
        ],
        "tags": [],
        "advice": "Legitimate jobs do not ask you to pay a 'registration' "
                  "or 'activation' fee before you start earning.",
    },
}


def classify(raw_text: str) -> dict:
    normalized = normalize(raw_text)
    clean_text = normalized["clean_text"]
    panic_tags = set(normalized["panic_tags"])

    results = []
    for key, typ in TYPOLOGIES.items():
        best_score = 0
        for phrase in typ["phrases"]:
            score = fuzz.partial_ratio(clean_text, phrase)
            best_score = max(best_score, score)

        tag_overlap = len(panic_tags & set(typ["tags"]))
        # Panic-tag co-occurrence nudges confidence up -- catches cases
        # where OCR mangled the exact phrase but the vocabulary signal
        # is still there.
        adjusted_score = best_score + (tag_overlap * 8)

        if adjusted_score >= 60:  # tune this threshold against real samples
            results.append({
                "typology": key,
                "label": typ["label"],
                "confidence": min(adjusted_score, 100),
                "advice": typ["advice"],
            })

    results.sort(key=lambda r: r["confidence"], reverse=True)
    return {
        "clean_text": clean_text,
        "panic_tags": sorted(panic_tags),
        "matches": results,
    }
