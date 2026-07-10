"""
Standalone local test harness for Satark Setu.

Does NOT start the FastAPI server and does NOT need any API keys.
Exercises normalize -> classify -> url_agent -> scheme_check directly
against realistic sample inputs so you can sanity-check behavior before
wiring up Telegram/browser/API keys.

Run from the project root (same directory as this file):
    cd c:\\Users\\rohan\\OneDrive\\project\\satark_setu
    python local_pipeline_test.py
"""

from normalize import normalize
from classifier import classify
from url_agent import extract_urls, check_url
from scheme_check import build_collection, check_scheme_claim
from translate import to_english_for_matching

SAMPLES = [
    (
        "Fake KYC SMS",
        "Dear customer your SBI KYC is pending, account will be BLOCKED today. "
        "Update immediately: https://sbi-verify.secure-kyc-update.co.in/login",
    ),
    (
        "Fake PM-KISAN message",
        "PM Kisan 15th installment ka kist pending hai, turant apna Aadhaar "
        "verify karein warna payment cancel ho jayega: http://bit.ly/pmkisan15",
    ),
    (
        "Clean, non-scam message",
        "Hey, are we still meeting for lunch at 1pm tomorrow near the office?",
    ),
    (
        "Lookalike phishing URL only",
        "Your parcel is held at customs, pay duty here to release: "
        "https://indiapost.gov.in.duty-clearance.info/pay",
    ),
    (
        "Digital arrest scam call description",
        "Caller said do not disconnect this video call, you are under digital "
        "arrest, CBI investigation against you, aadhaar linked to a crime.",
    ),
    (
        "Hindi Devanagari KYC scam",
        "आपका SBI KYC पेंडिंग है, आज खाता ब्लॉक हो जाएगा। तुरंत यहाँ क्लिक करें: https://sbi-kyc-secure.in/verify",
    ),
    (
        "Telugu electricity disconnection scam",
        "మీ విద్యుత్ కనెక్షన్ నేడు రాత్రి కత్తిరించబడుతుంది। దయచేసి ఇప్పుడే చెల్లించండి: http://tsecil-pay.in",
    ),
    (
        "Hindi PM-KISAN native script",
        "प्रिय किसान, आपकी PM Kisan की 15वीं किस्त रुकी हुई है। अभी Aadhaar सत्यापित करें: http://bit.ly/pmkisan-hin",
    ),
]


def run():
    # Fast-fail if not run from the project root — data/schemes_seed.json won't be found otherwise.
    import pathlib, sys as _sys

    # Ensure stdout can handle Unicode (Devanagari, Telugu) on Windows terminals
    # that default to cp1252 — without this, printing native-script Input: lines
    # raises UnicodeEncodeError when the console codec can't encode the characters.
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(_sys.stderr, "reconfigure"):
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    _data_file = pathlib.Path("data/schemes_seed.json")
    if not _data_file.exists():
        print(
            "ERROR: data/schemes_seed.json not found.\n"
            "Run this script from the project root directory:\n"
            "  cd c:\\Users\\rohan\\OneDrive\\project\\satark_setu\n"
            "  python local_pipeline_test.py",
            file=_sys.stderr,
        )
        _sys.exit(1)

    print("Building scheme collection (first run seeds ChromaDB from data/schemes_seed.json)...")
    collection = build_collection()
    print("Ready.\n" + "=" * 70)

    for title, raw_text in SAMPLES:
        print(f"\n### {title}")
        print(f"Input: {raw_text}\n")

        normalized = normalize(raw_text)
        print(f"-- normalize.py --")
        print(f"clean_text : {normalized['clean_text']}")
        print(f"panic_tags : {normalized['panic_tags']}")

        text_for_matching = to_english_for_matching(raw_text)
        classification = classify(text_for_matching)
        print(f"\n-- classifier.py --")
        if classification["matches"]:
            for m in classification["matches"]:
                print(f"  [{m['confidence']:>3}%] {m['label']}")
                print(f"          advice: {m['advice']}")
        else:
            print("  No typology matched above threshold.")

        urls = extract_urls(raw_text)
        print(f"\n-- url_agent.py --")
        if urls:
            for u in urls:
                result = check_url(u)
                print(f"  {u}")
                print(f"    verdict: {result['verdict']}")
                if result["structural_flags"]:
                    for f in result["structural_flags"]:
                        print(f"    - {f}")
                print(f"    (safe_browsing_checked={result['safe_browsing_checked']}, "
                      f"virustotal_checked={result['virustotal_checked']})")
        else:
            print("  No URLs found in message.")

        print(f"\n-- scheme_check.py --")
        scheme_result = check_scheme_claim(normalized["clean_text"], collection)
        if scheme_result:
            print(f"  Matched scheme: {scheme_result['scheme_name']}")
            print(f"    Eligibility        : {scheme_result['eligibility']}")
            print(f"    Location           : {scheme_result['location']}")
            print(f"    Required Documents : {scheme_result['required_documents']}")
            print(f"    Contact Info       : {scheme_result['contact_info']}")
            print(f"    Real process       : {scheme_result['real_process']}")
        else:
            print("  No scheme match (expected -- this message doesn't reference a known scheme).")

        print("=" * 70)


if __name__ == "__main__":
    run()
