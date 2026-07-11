"""
Pramaan — CSV / XLSX Transaction Importer.

Parses exported transaction files from:
  - PhonePe CSV
  - Google Pay CSV
  - Paytm CSV or XLSX
  - Bank statement CSV/XLSX (HDFC, SBI, ICICI, Axis, Kotak, generic)

Each format has slightly different column names and amount structures.
This module auto-detects the source from the header row, normalises the
data, and returns a list of dicts ready for pipeline.process_message().

DEBIT / CREDIT CONTRACT
-----------------------
  direction = "outflow"  →  money LEFT your account  (debit)   →  subtracted
  direction = "inflow"   →  money ENTERED your account (credit) →  added

The _generic_parse fallback no longer blindly defaults to "inflow".
It inspects debit/credit columns, negative amount signs, and type/narration
keywords before deciding direction.
"""

from __future__ import annotations

import csv
import io
import re
import datetime
import logging
from typing import Literal

logger = logging.getLogger(__name__)

# ── Supported format names ────────────────────────────────────────────────────

AppName = Literal["phonepe", "gpay", "paytm", "hdfc", "sbi", "icici", "axis", "kotak", "auto"]

# Signature column sets for auto-detection (all must be present, lowercase)
_SIGNATURES: dict[str, list[str]] = {
    "phonepe": ["transaction id", "debit", "credit"],
    "gpay":    ["transaction id", "description", "amount (inr)"],
    "paytm":   ["txn id", "remarks", "net amount"],
    "hdfc":    ["narration", "chq./ref.no.", "withdrawal amt."],
    "sbi":     ["txn date", "description", "debit", "credit", "balance"],
    "icici":   ["transaction date", "transaction remarks", "withdrawal amount (inr)"],
    "axis":    ["tran date", "particulars", "debit"],
    "kotak":   ["transaction date", "description", "debit amount"],
}


def detect_app(headers: list[str]) -> AppName:
    """Detect which source produced the file from its column headers."""
    normalised = [h.strip().lower() for h in headers]
    for app, sigs in _SIGNATURES.items():
        if all(s in normalised for s in sigs):
            return app  # type: ignore[return-value]
    return "auto"


# ── Amount helpers ────────────────────────────────────────────────────────────

def _parse_amount(raw: str) -> float | None:
    """Strip currency symbols and commas; return absolute float or None."""
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", raw.replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_date(raw: str) -> str | None:
    """Try several common date formats and return ISO date string."""
    for fmt in (
        "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S", "%d-%m-%Y", "%Y-%m-%d",
        "%d %b %Y", "%b %d, %Y", "%d/%m/%Y", "%m/%d/%Y",
        "%d-%b-%Y", "%d %B %Y",
    ):
        try:
            return datetime.datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return raw.strip() or None


def _direction_from_debit_credit(debit_raw: str, credit_raw: str) -> tuple[str, float | None]:
    """
    Given raw debit and credit strings (either can be blank/0),
    return (direction, amount).
    """
    debit  = _parse_amount(debit_raw or "")
    credit = _parse_amount(credit_raw or "")

    if (debit or 0) > 0 and (credit or 0) == 0:
        return "outflow", debit
    if (credit or 0) > 0 and (debit or 0) == 0:
        return "inflow", credit
    if (debit or 0) > 0:
        return "outflow", debit
    return "inflow", credit


# ── Per-format parsers ────────────────────────────────────────────────────────

def _parse_phonepe(row: dict) -> dict | None:
    """
    PhonePe CSV columns (2024 export):
        Date, Particulars, Debit, Credit, Bank Reference Number
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    direction, amount = _direction_from_debit_credit(
        keys.get("debit", ""), keys.get("credit", "")
    )
    if not amount:
        return None

    desc = keys.get("particulars") or keys.get("description") or ""
    return {
        "raw_text":          f"PhonePe: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("date", "")),
        "counterparty_name": _extract_counterparty(desc),
        "payment_method":    "UPI",
        "upi_reference":     keys.get("bank reference number") or keys.get("transaction id", ""),
        "source":            "phonepe_csv",
    }


def _parse_gpay(row: dict) -> dict | None:
    """
    Google Pay CSV columns (2024 export):
        Date, Description, Amount (INR), Status, Transaction ID
    Google Pay uses negative amounts for money sent (outflow).
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    status = keys.get("status", "").lower()
    if "completed" not in status and "success" not in status:
        return None

    raw_amount = keys.get("amount (inr)") or keys.get("amount", "")
    negative   = raw_amount.strip().startswith("-")
    amount     = _parse_amount(raw_amount)
    if not amount:
        return None

    direction = "outflow" if negative else "inflow"
    desc      = keys.get("description", "")
    return {
        "raw_text":          f"Google Pay: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("date", "")),
        "counterparty_name": _extract_counterparty(desc),
        "payment_method":    "UPI",
        "upi_reference":     keys.get("transaction id", ""),
        "source":            "gpay_csv",
    }


def _parse_paytm(row: dict) -> dict | None:
    """
    Paytm CSV / XLSX columns (2024 export):
        Date, Txn ID, Remarks, Type, Net Amount, Status, Total Amount
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    status = keys.get("status", "").lower()
    if status and "success" not in status:
        return None

    amount = _parse_amount(keys.get("net amount") or keys.get("total amount", ""))
    if not amount:
        return None

    txn_type  = keys.get("type", "").lower()
    direction = "outflow" if any(w in txn_type for w in ("debit", "paid", "sent", "payment")) else "inflow"
    desc      = keys.get("remarks", "")
    return {
        "raw_text":          f"Paytm: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("date", "")),
        "counterparty_name": _extract_counterparty(desc),
        "payment_method":    "UPI",
        "upi_reference":     keys.get("txn id", ""),
        "source":            "paytm_csv",
    }


def _parse_hdfc(row: dict) -> dict | None:
    """
    HDFC Bank statement CSV columns:
        Date, Narration, Chq./Ref.No., Value Dt, Withdrawal Amt., Deposit Amt., Closing Balance
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    direction, amount = _direction_from_debit_credit(
        keys.get("withdrawal amt.", ""), keys.get("deposit amt.", "")
    )
    if not amount:
        return None

    desc = keys.get("narration", "")
    return {
        "raw_text":          f"HDFC: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("date", "")),
        "counterparty_name": _extract_counterparty(desc),
        "payment_method":    "Bank Transfer",
        "upi_reference":     keys.get("chq./ref.no.", ""),
        "source":            "hdfc_bank",
    }


def _parse_sbi(row: dict) -> dict | None:
    """
    SBI Bank statement CSV columns:
        Txn Date, Value Date, Description, Ref No./Cheque No., Debit, Credit, Balance
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    direction, amount = _direction_from_debit_credit(
        keys.get("debit", ""), keys.get("credit", "")
    )
    if not amount:
        return None

    desc = keys.get("description", "")
    return {
        "raw_text":          f"SBI: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("txn date", "")),
        "counterparty_name": _extract_counterparty(desc),
        "payment_method":    "Bank Transfer",
        "upi_reference":     keys.get("ref no./cheque no.", ""),
        "source":            "sbi_bank",
    }


def _parse_icici(row: dict) -> dict | None:
    """
    ICICI Bank statement CSV columns:
        Transaction Date, Transaction Remarks, Withdrawal Amount (INR), Deposit Amount (INR), Balance (INR)
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    direction, amount = _direction_from_debit_credit(
        keys.get("withdrawal amount (inr)", ""), keys.get("deposit amount (inr)", "")
    )
    if not amount:
        return None

    desc = keys.get("transaction remarks", "")
    return {
        "raw_text":          f"ICICI: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("transaction date", "")),
        "counterparty_name": _extract_counterparty(desc),
        "payment_method":    "Bank Transfer",
        "upi_reference":     "",
        "source":            "icici_bank",
    }


def _parse_axis(row: dict) -> dict | None:
    """
    Axis Bank statement CSV columns:
        Tran Date, Particulars, Chq/Ref No., Value Date, Debit, Credit, Balance
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    direction, amount = _direction_from_debit_credit(
        keys.get("debit", ""), keys.get("credit", "")
    )
    if not amount:
        return None

    desc = keys.get("particulars", "")
    return {
        "raw_text":          f"Axis: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("tran date", "")),
        "counterparty_name": _extract_counterparty(desc),
        "payment_method":    "Bank Transfer",
        "upi_reference":     keys.get("chq/ref no.", ""),
        "source":            "axis_bank",
    }


def _parse_kotak(row: dict) -> dict | None:
    """
    Kotak Bank statement CSV columns:
        Transaction Date, Description, Chq / Ref No., Debit Amount, Credit Amount, Balance
    """
    keys = {k.strip().lower(): v.strip() for k, v in row.items()}
    direction, amount = _direction_from_debit_credit(
        keys.get("debit amount", ""), keys.get("credit amount", "")
    )
    if not amount:
        return None

    desc = keys.get("description", "")
    return {
        "raw_text":          f"Kotak: {desc} ₹{amount}",
        "amount":            amount,
        "txn_direction":     direction,
        "txn_date":          _parse_date(keys.get("transaction date", "")),
        "counterparty_name": _extract_counterparty(desc),
        "payment_method":    "Bank Transfer",
        "upi_reference":     keys.get("chq / ref no.", ""),
        "source":            "kotak_bank",
    }


def _extract_counterparty(description: str) -> str | None:
    """Best-effort extraction of a name from a transaction description."""
    if not description:
        return None
    patterns = [
        r"(?:from|to|paid to|received from|by)\s+([A-Za-z][A-Za-z\s]{1,30}?)(?:\s+via|\s+for|\s+using|$|,)",
        r"^([A-Za-z][A-Za-z\s]{1,25})(?:\s+\d|$)",
    ]
    for pat in patterns:
        m = re.search(pat, description, re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
    return None


# ── XLSX → rows converter ─────────────────────────────────────────────────────

def _xlsx_to_rows(file_bytes: bytes) -> tuple[list[str], list[dict]]:
    """
    Convert XLSX bytes into (headers, list_of_row_dicts).
    Returns empty lists on failure.
    """
    try:
        import openpyxl
    except ImportError:
        logger.error("openpyxl not installed. Run: pip install openpyxl")
        return [], []

    import io as _io
    try:
        wb = openpyxl.load_workbook(_io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], []

        # Skip completely empty leading rows (some bank exports have metadata at top)
        header_idx = 0
        for i, row in enumerate(rows):
            if any(cell is not None and str(cell).strip() for cell in row):
                header_idx = i
                break

        raw_headers = [str(c).strip() if c is not None else "" for c in rows[header_idx]]
        data_rows   = []
        for row in rows[header_idx + 1:]:
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue  # skip blank rows
            row_dict = {raw_headers[i]: (str(row[i]).strip() if row[i] is not None else "")
                        for i in range(min(len(raw_headers), len(row)))}
            data_rows.append(row_dict)

        return raw_headers, data_rows
    except Exception as e:
        logger.error("XLSX parse error: %s", e)
        return [], []


# ── Parser registry ───────────────────────────────────────────────────────────

_PARSERS = {
    "phonepe": _parse_phonepe,
    "gpay":    _parse_gpay,
    "paytm":   _parse_paytm,
    "hdfc":    _parse_hdfc,
    "sbi":     _parse_sbi,
    "icici":   _parse_icici,
    "axis":    _parse_axis,
    "kotak":   _parse_kotak,
}


# ── Main public function ──────────────────────────────────────────────────────

def parse_csv(
    file_bytes: bytes,
    app: AppName = "auto",
    encoding: str = "utf-8-sig",  # handles BOM from Excel-saved CSVs
    filename: str = "",
) -> tuple[list[dict], list[str]]:
    """
    Parse a UPI / bank statement CSV or XLSX export and return (transactions, errors).

    transactions — list of normalised transaction dicts ready for pipeline ingestion.
    errors       — list of human-readable parse warnings (skipped rows, etc.)
    """
    is_xlsx = filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls")

    if is_xlsx:
        headers, data_rows = _xlsx_to_rows(file_bytes)
        if not headers:
            return [], ["Could not read XLSX file. Make sure it is a valid Excel file."]
    else:
        # CSV path
        try:
            text = file_bytes.decode(encoding)
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1")
        reader   = csv.DictReader(io.StringIO(text))
        headers  = list(reader.fieldnames or [])
        data_rows = list(reader)

    if not headers:
        return [], ["File has no headers — make sure you're uploading the raw export file."]

    # Auto-detect source
    if app == "auto":
        app = detect_app(headers)
        logger.info("File auto-detected as: %s format", app)

    parser = _PARSERS.get(app)
    if parser is None:
        return _generic_parse(data_rows), []

    transactions: list[dict] = []
    errors: list[str] = []

    for i, row in enumerate(data_rows, start=2):
        try:
            txn = parser(row)
            if txn:
                transactions.append(txn)
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    logger.info("File parsed — %d transactions, %d errors", len(transactions), len(errors))
    return transactions, errors


def _generic_parse(data_rows: list[dict]) -> list[dict]:
    """
    Fallback parser for unknown CSV/XLSX formats.

    Intelligently determines direction by:
      1. Separate Debit / Credit columns (most bank statements)
      2. Negative amount sign (Google Pay style)
      3. Type / Narration column keywords (PAID, RECEIVED, etc.)
      4. Falls back to inflow ONLY when no other signal exists.
    """
    results = []
    for row in data_rows:
        keys = {k.strip().lower(): v.strip() for k, v in row.items() if k}

        # ── Find description ──────────────────────────────────────────
        desc_key = next(
            (k for k in keys if any(w in k for w in ("desc", "remark", "particular", "narration", "detail"))),
            None,
        )
        desc = keys.get(desc_key or "", "")

        # ── Find date ─────────────────────────────────────────────────
        date_key = next((k for k in keys if "date" in k), None)
        txn_date = _parse_date(keys.get(date_key or "", ""))

        # ── Find reference number ─────────────────────────────────────
        ref_key = next(
            (k for k in keys if any(w in k for w in ("ref", "chq", "utr", "transaction id", "txn id"))),
            None,
        )
        ref = keys.get(ref_key or "", "")

        # ── Detect direction + amount (priority order) ─────────────────

        # Strategy 1: Separate debit and credit columns
        debit_key  = next((k for k in keys if k in ("debit", "withdrawal", "withdrawal amt.", "debit amount", "dr")), None)
        credit_key = next((k for k in keys if k in ("credit", "deposit", "deposit amt.", "credit amount", "cr")), None)

        if debit_key and credit_key:
            direction, amount = _direction_from_debit_credit(
                keys.get(debit_key, ""), keys.get(credit_key, "")
            )
            if not amount:
                continue
        else:
            # Strategy 2: Single amount column
            amount_key = next((k for k in keys if "amount" in k), None)
            if not amount_key:
                continue
            raw_amount = keys.get(amount_key, "")
            negative   = raw_amount.strip().startswith("-")
            amount     = _parse_amount(raw_amount)
            if not amount:
                continue

            # Strategy 3: Infer direction from type/narration keywords
            type_key  = next((k for k in keys if k in ("type", "txn type", "transaction type", "mode")), None)
            type_val  = (keys.get(type_key or "", "") + " " + desc).lower()

            if negative or any(w in type_val for w in ("debit", "dr", "withdrawal", "paid", "payment", "sent", "purchase", "transfer out")):
                direction = "outflow"
            elif any(w in type_val for w in ("credit", "cr", "deposit", "received", "inward", "transfer in", "salary", "refund")):
                direction = "inflow"
            else:
                direction = "inflow"  # conservative final default

        results.append({
            "raw_text":          f"Bank: {desc} ₹{amount}",
            "amount":            amount,
            "txn_direction":     direction,
            "txn_date":          txn_date,
            "counterparty_name": _extract_counterparty(desc),
            "payment_method":    "Bank Transfer",
            "upi_reference":     ref,
            "source":            "generic_bank",
        })

    return results
