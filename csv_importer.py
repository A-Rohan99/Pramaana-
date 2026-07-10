"""
Pramaan — CSV Transaction Importer.

Parses exported transaction CSVs from PhonePe, Google Pay, and Paytm
into a unified transaction format that the pipeline can process.

Each app exports slightly different column names and amount formats.
This module auto-detects the app from the header row, normalises the
data, and returns a list of dicts ready for pipeline.process_message().
"""

from __future__ import annotations

import csv
import io
import re
import datetime
import logging
from typing import Literal

logger = logging.getLogger(__name__)

# ── Supported app formats ─────────────────────────────────────────────────────

AppName = Literal["phonepe", "gpay", "paytm", "auto"]

# Signature header strings for each app (first row detection)
_SIGNATURES: dict[str, list[str]] = {
    "phonepe": ["transaction id", "debit", "credit"],
    "gpay":    ["transaction id", "description", "amount (inr)"],
    "paytm":   ["txn id", "remarks", "net amount"],
}


def detect_app(headers: list[str]) -> AppName:
    """Detect which UPI app produced the CSV from its column headers."""
    normalised = [h.strip().lower() for h in headers]
    for app, sigs in _SIGNATURES.items():
        if all(s in normalised for s in sigs):
            return app  # type: ignore[return-value]
    return "auto"


# ── Amount helpers ────────────────────────────────────────────────────────────

def _parse_amount(raw: str) -> float | None:
    """Strip currency symbols and commas; return float or None."""
    cleaned = re.sub(r"[^\d.]", "", raw.replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_date(raw: str) -> str | None:
    """Try several common date formats and return ISO date string."""
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d",
                "%d %b %Y", "%b %d, %Y"):
        try:
            return datetime.datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return raw.strip() or None


# ── Per-app parsers ───────────────────────────────────────────────────────────

def _parse_phonepe(row: dict) -> dict | None:
    """
    PhonePe CSV columns (as of 2024 export):
        Date, Particulars, Debit, Credit, Bank Reference Number
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    debit  = _parse_amount(keys.get("debit", "") or "")
    credit = _parse_amount(keys.get("credit", "") or "")
    if not debit and not credit:
        return None

    direction = "outflow" if (debit or 0) > 0 else "inflow"
    amount    = debit or credit

    # Extract counterparty from description
    desc = keys.get("particulars") or keys.get("description") or ""
    counterparty = _extract_counterparty(desc)

    return {
        "raw_text":         f"PhonePe: {desc} ₹{amount}",
        "amount":           amount,
        "txn_direction":    direction,
        "txn_date":         _parse_date(keys.get("date", "")),
        "counterparty_name": counterparty,
        "payment_method":   "UPI",
        "upi_reference":    keys.get("bank reference number") or keys.get("transaction id", ""),
        "source":           "phonepe_csv",
    }


def _parse_gpay(row: dict) -> dict | None:
    """
    Google Pay CSV columns (as of 2024 export):
        Date, Description, Amount (INR), Status, Transaction ID
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    status = keys.get("status", "").lower()
    if "completed" not in status and "success" not in status:
        return None  # Skip pending / failed

    raw_amount = keys.get("amount (inr)") or keys.get("amount", "")
    # Google Pay uses negative amounts for money sent
    negative = raw_amount.startswith("-")
    amount = _parse_amount(raw_amount)
    if not amount:
        return None

    direction    = "outflow" if negative else "inflow"
    desc         = keys.get("description", "")
    counterparty = _extract_counterparty(desc)

    return {
        "raw_text":          f"Google Pay: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("date", "")),
        "counterparty_name": counterparty,
        "payment_method":    "UPI",
        "upi_reference":     keys.get("transaction id", ""),
        "source":            "gpay_csv",
    }


def _parse_paytm(row: dict) -> dict | None:
    """
    Paytm CSV columns (as of 2024 export):
        Date, Txn ID, Remarks, Type, Net Amount, Status, Total Amount
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    status = keys.get("status", "").lower()
    if "success" not in status:
        return None  # Skip non-successful

    amount = _parse_amount(keys.get("net amount") or keys.get("total amount", ""))
    if not amount:
        return None

    txn_type  = keys.get("type", "").lower()
    direction = "outflow" if "debit" in txn_type or "paid" in txn_type else "inflow"
    desc      = keys.get("remarks", "")
    counterparty = _extract_counterparty(desc)

    return {
        "raw_text":          f"Paytm: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("date", "")),
        "counterparty_name": counterparty,
        "payment_method":    "UPI",
        "upi_reference":     keys.get("txn id", ""),
        "source":            "paytm_csv",
    }


def _extract_counterparty(description: str) -> str | None:
    """Best-effort extraction of a name from a transaction description."""
    if not description:
        return None
    # Common patterns: "From Ramesh", "To Anand Stores", "Paid to Priya"
    patterns = [
        r"(?:from|to|paid to|received from|by)\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\s+via|\s+for|\s+using|$|,)",
        r"^([A-Za-z][A-Za-z\s]{1,25})(?:\s+\d|$)",
    ]
    for pat in patterns:
        m = re.search(pat, description, re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
    return None


# ── Main public function ───────────────────────────────────────────────────────

_PARSERS = {
    "phonepe": _parse_phonepe,
    "gpay":    _parse_gpay,
    "paytm":   _parse_paytm,
}


def parse_csv(
    file_bytes: bytes,
    app: AppName = "auto",
    encoding: str = "utf-8-sig",  # handles BOM from Excel-saved CSVs
) -> tuple[list[dict], list[str]]:
    """
    Parse a UPI CSV export and return (transactions, errors).

    transactions — list of normalised transaction dicts ready for pipeline ingestion.
    errors       — list of human-readable parse warnings (skipped rows, etc.)
    """
    # Decode bytes → text
    try:
        text = file_bytes.decode(encoding)
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1")

    reader    = csv.DictReader(io.StringIO(text))
    headers   = reader.fieldnames or []
    if not headers:
        return [], ["CSV has no headers — make sure you're uploading the raw export file."]

    # Auto-detect app if needed
    if app == "auto":
        app = detect_app(headers)
        logger.info("CSV auto-detected as: %s", app)

    parser = _PARSERS.get(app)
    if parser is None:
        # Fall back to a generic parser: try to find amount + date columns
        return _generic_parse(reader), []

    transactions: list[dict] = []
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):  # row 1 is headers
        try:
            txn = parser(row)
            if txn:
                transactions.append(txn)
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    logger.info("CSV parsed — %d transactions, %d errors", len(transactions), len(errors))
    return transactions, errors


def _generic_parse(reader: csv.DictReader) -> list[dict]:
    """
    Fallback parser for unknown CSV formats.
    Looks for columns whose names contain 'amount', 'date', 'description'.
    """
    results = []
    for row in reader:
        keys = {k.strip().lower(): v.strip() for k, v in row.items()}
        amount_key = next((k for k in keys if "amount" in k), None)
        date_key   = next((k for k in keys if "date" in k), None)
        desc_key   = next((k for k in keys if "desc" in k or "remark" in k or "particular" in k), None)

        amount = _parse_amount(keys.get(amount_key or "", ""))
        if not amount:
            continue

        results.append({
            "raw_text":       f"Imported: {keys.get(desc_key or '', '')} ₹{amount}",
            "amount":         amount,
            "txn_direction":  "inflow",   # conservative default
            "txn_date":       _parse_date(keys.get(date_key or "", "")),
            "payment_method": "UPI",
            "source":         "generic_csv",
        })
    return results
