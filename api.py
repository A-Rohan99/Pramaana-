"""
Pramaan — Web API + static frontend server.

One FastAPI process serves the REST endpoints AND the static frontend, so
the entire demo runs from a single  `python api.py`  command.

Endpoints (legacy — still work exactly as before):
  POST /api/verify-text   {text, language}          → verdict JSON
  POST /api/verify-image  multipart file + language  → verdict JSON
  POST /api/verify-voice  multipart file + language  → verdict JSON
  GET  /api/search        ?query=&language=          → scheme results JSON

New dashboard endpoints:
  GET  /api/dashboard/stats               → aggregated stats for the dashboard
  GET  /api/dashboard/messages            → recent processed messages
  GET  /api/dashboard/contacts            → counterparty directory
  POST /api/dashboard/confirm/{id}        → promote draft → confirmed
  POST /api/dashboard/reject/{id}         → promote draft → rejected
  POST /api/dashboard/report-scam/{id}    → flag + store community report
  GET  /api/dashboard/export              → download confirmed txns as JSON

Channel ingestion webhooks (optional):
  POST /api/whatsapp-webhook              → WhatsApp Cloud API message handler
  POST /api/sms-webhook                   → Self-hosted Android SMS gateway
  GET  /                                  → frontend (index.html)
"""

import os
import tempfile
import logging
import threading
import time

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pramaan_api")

# ── Core imports ─────────────────────────────────────────────────────────────
import db
from pipeline import process_message
from ocr import extract_text, OcrUnavailableError
from voice_pipeline import transcribe, AudioExtractionError
from translate import translate_text, translate_verdict_dict, LANGUAGE_CODES, to_english_for_matching
from rate_limiter import is_rate_limited
from scheme_check import build_collection, search_schemes
from csv_importer import parse_csv

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="Pramaan API", version="2.0")

# Add JWT middleware before CORS middleware
# This ensures shop_id is injected into request scope for all authenticated routes
# from auth.middleware import ShopScopeMiddleware
# app.add_middleware(ShopScopeMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    db.init_db()
    logger.info("Pramaan database initialized.")
    from scripts.setup_demo_merchants import setup_demo_merchants
    setup_demo_merchants()
    _start_telegram_bot()


# ── Helpers ───────────────────────────────────────────────────────────────────

def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def validate_language(language: str) -> str:
    normalized = (language or "english").strip().lower()
    if normalized not in LANGUAGE_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{language}'. Choose from {list(LANGUAGE_CODES)}.",
        )
    return normalized


def _translate_result(result: dict, language: str) -> dict:
    """Apply display-time translation to the user-facing text fields of a pipeline result."""
    if language == "english":
        return result
    # Translate top-level matches
    for m in result.get("matches", []):
        if "label" in m:
            m["label"] = translate_text(m["label"], language)
        if "advice" in m:
            m["advice"] = translate_text(m["advice"], language)
    # Translate scheme result fields
    if result.get("scheme_result"):
        result["scheme_result"] = translate_verdict_dict(result["scheme_result"], language)
    # Translate explanation
    if result.get("explanation"):
        result["explanation"] = translate_text(result["explanation"], language)
    return result


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/auth/signup")
async def signup(request: Request):
    """
    POST /auth/signup
    Body: {"email": "merchant@example.com", "password": "password123", "shop_name": "My Store"}
    Returns: {"access_token": "<jwt>", "token_type": "bearer", "shop_id": 1, "shop_name": "My Store"}
    
    Validates email format, password length (min 8 chars), checks for duplicates.
    Creates User + Shop, then returns JWT.
    """
    import re
    from auth.password import hash_password
    from auth.jwt_utils import create_access_token
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    shop_name = (body.get("shop_name") or "").strip()
    
    # Validate email format
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not email or not re.match(email_regex, email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    # Validate password length
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Validate shop_name
    if not shop_name:
        raise HTTPException(status_code=400, detail="Shop name is required")
    
    # Check for duplicate email
    existing_user = db.get_user_by_email(email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create Shop first
    shop = db.create_shop(name=shop_name)
    shop_id = shop["id"]
    
    # Hash password and create User
    password_hash = hash_password(password)
    user = db.create_user(
        shop_id=shop_id,
        email=email,
        password_hash=password_hash
    )
    user_id = user["id"]
    
    # Generate JWT
    token = create_access_token({
        "shop_id": shop_id,
        "user_id": user_id,
        "email": email,
    })
    
    logger.info(f"New signup: {email} (shop_id={shop_id})")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "shop_id": shop_id,
        "shop_name": shop_name,
        "user_id": user_id,
    }


@app.post("/auth/login")
async def login(request: Request):
    """
    POST /auth/login
    Body: {"email": "merchant@example.com", "password": "password123"}
    Returns: {"access_token": "<jwt>", "token_type": "bearer", "shop_id": 1}
    
    Queries User table, verifies password, generates new JWT.
    Returns HTTP 401 for invalid credentials (generic message).
    """
    from auth.password import verify_password
    from auth.jwt_utils import create_access_token
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    
    # Query user by email
    user = db.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    if not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account is disabled")
    
    # Get shop details
    shop = db.get_shop(user["shop_id"])
    if not shop:
        raise HTTPException(status_code=500, detail="Shop not found for user")
    
    # Generate new access token
    token = create_access_token({
        "shop_id": user["shop_id"],
        "user_id": user["id"],
        "email": user["email"],
    })
    
    logger.info(f"Login: {email} (shop_id={user['shop_id']})")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "shop_id": user["shop_id"],
        "shop_name": shop.get("name", ""),
        "user_id": user["id"],
    }


# ── Verification endpoints ─────────────────────────────────────────────────────

@app.post("/api/verify-text")
async def verify_text(request: Request, payload: dict):
    key = client_key(request)
    if is_rate_limited(key):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

    text = payload.get("text", "").strip()
    language = validate_language(payload.get("language", "english"))
    if not text:
        raise HTTPException(status_code=400, detail="No text provided.")

    result = process_message(raw_text=text, language=language)
    return _translate_result(result, language)


@app.post("/api/verify-image")
async def verify_image(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("english"),
):
    key = client_key(request)
    if is_rate_limited(key):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

    language = validate_language(language)
    image_bytes = await file.read()
    try:
        raw_text = extract_text(image_bytes)
    except OcrUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Couldn't read text from that image clearly. Try a sharper screenshot.")

    result = process_message(raw_text=raw_text, language=language)
    return _translate_result(result, language)


@app.post("/api/verify-voice")
async def verify_voice(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("english"),
):
    key = client_key(request)
    if is_rate_limited(key):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

    language = validate_language(language)
    suffix = os.path.splitext(file.filename or "")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        transcription = transcribe(tmp_path)
    except AudioExtractionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not transcription["transcript"]:
        raise HTTPException(status_code=422, detail="Couldn't extract clear speech from that recording.")

    result = process_message(raw_text=transcription["transcript"], language=language)
    result["detected_language"] = transcription["detected_language_name"]
    result["transcript"] = transcription["transcript"]
    return _translate_result(result, language)


@app.get("/api/search")
async def search(request: Request, query: str, language: str = "english"):
    key = client_key(request)
    if is_rate_limited(key):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")

    language = validate_language(language)
    if not query.strip():
        raise HTTPException(status_code=400, detail="No search query provided.")

    collection = build_collection()
    results = search_schemes(query, collection)
    if language != "english":
        results = [translate_verdict_dict(r, language) for r in results]
    return {"results": results}


# ── Dashboard endpoints ───────────────────────────────────────────────────────

@app.get("/api/dashboard/stats")
async def dashboard_stats(ledger_month: str | None = None):
    """
    Returns aggregated stats including P&L for the active (or specified) ledger month.
    Pass ?ledger_month=2026-07 to filter to a specific month.
    """
    return db.get_stats(ledger_month=ledger_month)


@app.get("/api/dashboard/messages")
async def dashboard_messages(limit: int = 60, ledger_month: str | None = None):
    """
    Returns recent processed messages. Pass ?ledger_month=2026-07 to filter by month.
    """
    messages = db.get_messages(limit=limit, ledger_month=ledger_month)
    return {"messages": messages}


@app.get("/api/dashboard/contacts")
async def dashboard_contacts(limit: int = 20):
    return {"contacts": db.get_contacts(limit=limit)}


@app.post("/api/dashboard/confirm/{msg_id}")
async def confirm_transaction(msg_id: int):
    ok = db.update_ledger_status(msg_id, "confirmed")
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found.")
    return {"status": "confirmed", "id": msg_id}


@app.post("/api/dashboard/reject/{msg_id}")
async def reject_transaction(msg_id: int):
    ok = db.update_ledger_status(msg_id, "rejected")
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found.")
    return {"status": "rejected", "id": msg_id}


@app.post("/api/dashboard/report-scam/{msg_id}")
async def report_scam(msg_id: int):
    """
    Flag a message as a community scam report.
    Stores an embedding of the message text for future similarity checks and
    updates the sender's contact trust score.
    """
    messages = db.get_messages(limit=1000)
    target = next((m for m in messages if m["id"] == msg_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Message not found.")

    embedding = None
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embedding = model.encode([target["raw_text"]])[0].tolist()
    except Exception:
        pass

    db.add_community_report(
        text=target["raw_text"],
        embedding=embedding,
        summary=target.get("explanation", ""),
    )

    if target.get("counterparty_phone"):
        db.report_contact_as_scam(target["counterparty_phone"])

    return {"status": "reported", "id": msg_id}


@app.get("/api/dashboard/export")
async def export_transactions(ledger_month: str | None = None):
    """Return confirmed transactions in a credit-ready JSON format."""
    data = db.get_export_data(ledger_month=ledger_month)
    month_label = db._month_label(ledger_month) if ledger_month else "all"
    return JSONResponse(
        content={"export": data, "count": len(data), "month": month_label},
        headers={"Content-Disposition": f"attachment; filename=pramaan_{ledger_month or 'all'}_export.json"},
    )


# ── Settings endpoints ─────────────────────────────────────────────────────────

@app.get("/api/dashboard/settings")
async def get_settings():
    """Return all current settings (e.g. auto_upi_sync)."""
    return db.get_all_settings()


@app.post("/api/dashboard/settings")
async def update_settings(payload: dict):
    """
    Update one or more settings.
    Body: {"auto_upi_sync": "true"} or {"auto_upi_sync": "false"}
    """
    allowed_keys = {"auto_upi_sync"}
    updated = {}
    for key, value in payload.items():
        if key in allowed_keys:
            db.set_setting(key, str(value).lower())
            updated[key] = str(value).lower()
    return {"updated": updated}


# ── Ledger management endpoints ───────────────────────────────────────────────

@app.get("/api/dashboard/ledgers")
async def list_ledgers():
    """List all monthly ledger periods."""
    return {"ledgers": db.list_ledgers()}


@app.get("/api/dashboard/ledgers/check")
async def check_ledger(month: str | None = None):
    """
    Check whether a ledger exists for the given month (defaults to current calendar month).
    Frontend uses this on startup to decide whether to show the roll-over modal.
    """
    return db.check_ledger_for_month(month)


@app.post("/api/dashboard/ledgers/create")
async def create_ledger(payload: dict):
    """
    Create a new monthly ledger.
    Body: {"month_key": "2026-07", "inherit": false}
    inherit=true keeps previous ledger data in view (inherited) rather than closing it.
    """
    month_key = payload.get("month_key") or None
    inherit   = bool(payload.get("inherit", False))
    return db.create_ledger(month_key=month_key, inherit=inherit)



@app.post("/api/whatsapp-webhook")
async def whatsapp_webhook(payload: dict):
    """
    WhatsApp Business Cloud API webhook handler.
    Parses the message from the Cloud API format, runs it through the
    Pramaan pipeline, and returns the verdict.
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return {"status": "no_message"}

        msg = messages[0]
        text = (msg.get("text") or {}).get("body", "")
        sender = msg.get("from", "whatsapp_user")

        if not text:
            return {"status": "unsupported_message_type"}

        result = process_message(
            raw_text=text,
            channel="whatsapp",
            sender_id=sender,
        )
        return {"status": "processed", "verdict": result["classification"], "id": result["id"]}
    except Exception as e:
        logger.error("WhatsApp webhook error: %s", e)
        return {"status": "error"}


@app.post("/api/sms-webhook")
async def sms_webhook(request: Request, payload: dict):
    """
    Self-hosted Android SMS gateway webhook.
    Compatible with SMS Forwarder, HTTP SMS, and similar apps.
    Expects JSON body: {from, message, receivedAt}
    Optional header: X-Device-Name (identifies which phone/SIM sent the SMS)
    """
    # Check multiple common payload keys for flexibility with various SMS apps
    text = (
        payload.get("message") or 
        payload.get("text") or 
        payload.get("body") or 
        payload.get("msg") or 
        payload.get("content") or ""
    ).strip()
    
    sender = (
        payload.get("from") or 
        payload.get("sender") or 
        payload.get("phone") or 
        payload.get("phone_number") or 
        payload.get("senderNumber") or "sms_sender"
    )
    
    device = request.headers.get("X-Device-Name", "android")
    if not text:
        return {"status": "empty_message"}
    result = process_message(
        raw_text=text,
        channel="sms",
        sender_id=sender,
        sender_name=device,
    )
    # Return a structured response that SMS apps can parse/log
    return {
        "status":        "processed",
        "verdict":       result["classification"],
        "risk_score":    result["risk_score"],
        "ledger_status": result["ledger_status"],
        "id":            result["id"],
    }


# ── Telegram bot (optional background thread) ─────────────────────────────────

def _telegram_poll_loop(token: str):
    """
    Long-polling Telegram bot using the raw Bot API via requests.
    No external library needed beyond requests (already in requirements.txt).
    Runs in a daemon thread; exits silently if the token is invalid.
    """
    import requests as rq
    base = f"https://api.telegram.org/bot{token}"
    offset = 0
    logger.info("Telegram bot started (long-polling).")

    while True:
        try:
            resp = rq.get(
                f"{base}/getUpdates",
                params={"timeout": 30, "offset": offset},
                timeout=35,
            )
            if not resp.ok:
                logger.warning("Telegram getUpdates error: %s", resp.text[:200])
                time.sleep(5)
                continue

            updates = resp.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                if not chat_id:
                    continue

                sender = str(msg.get("from", {}).get("id", "tg_user"))
                sender_name = msg.get("from", {}).get("first_name") or "Merchant"

                text = (msg.get("text") or "").strip()
                voice = msg.get("voice") or msg.get("audio")
                photo = msg.get("photo")
                document = msg.get("document")

                if not text and not voice and not photo and not document:
                    continue

                # Route 1: Voice Note / Audio
                if voice:
                    file_id = voice["file_id"]
                    try:
                        ext = ".ogg"
                        if msg.get("audio") and msg["audio"].get("file_name"):
                            ext = os.path.splitext(msg["audio"]["file_name"])[1]
                        temp_fd, temp_path = tempfile.mkstemp(suffix=ext)
                        os.close(temp_fd)

                        _telegram_download_file_to_path(token, file_id, temp_path)
                        transcription_res = transcribe(temp_path)
                        text = transcription_res.get("transcript", "").strip()
                        
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
                            
                        if not text:
                            rq.post(
                                f"{base}/sendMessage",
                                json={"chat_id": chat_id, "text": "❌ Voice transcription failed: no speech detected."},
                                timeout=10,
                            )
                            continue
                            
                        rq.post(
                            f"{base}/sendMessage",
                            json={"chat_id": chat_id, "text": f"🎙️ Transcribed Speech ({transcription_res.get('detected_language_name', 'Unknown')}):\n_{text}_", "parse_mode": "Markdown"},
                            timeout=10,
                        )
                    except Exception as ve:
                        logger.error("Telegram voice processing failed: %s", ve)
                        rq.post(
                            f"{base}/sendMessage",
                            json={"chat_id": chat_id, "text": f"❌ Voice processing failed: {str(ve)}"},
                            timeout=10,
                        )
                        continue

                # Route 2: Photo / Image OCR
                elif photo:
                    file_id = photo[-1]["file_id"]
                    try:
                        image_bytes = _telegram_download_file(token, file_id)
                        text = extract_text(image_bytes).strip()
                        if not text:
                            rq.post(
                                f"{base}/sendMessage",
                                json={"chat_id": chat_id, "text": "❌ OCR failed: no text could be read from the image."},
                                timeout=10,
                            )
                            continue
                        rq.post(
                            f"{base}/sendMessage",
                            json={"chat_id": chat_id, "text": f"📷 OCR Extracted Text:\n```\n{text[:500]}\n```", "parse_mode": "Markdown"},
                            timeout=10,
                        )
                    except Exception as oe:
                        logger.error("Telegram OCR processing failed: %s", oe)
                        rq.post(
                            f"{base}/sendMessage",
                            json={"chat_id": chat_id, "text": f"❌ OCR failed: {str(oe)}"},
                            timeout=10,
                        )
                        continue

                # Route 3: Documents (CSV, XLSX, or PDF)
                elif document:
                    file_id = document["file_id"]
                    file_name = document.get("file_name", "").lower()
                    
                    if file_name.endswith(".csv") or file_name.endswith(".xlsx") or file_name.endswith(".xls"):
                        try:
                            csv_bytes = _telegram_download_file(token, file_id)
                            transactions, parse_errors = parse_csv(csv_bytes, app="auto", filename=file_name)
                            if not transactions and parse_errors:
                                rq.post(
                                    f"{base}/sendMessage",
                                    json={"chat_id": chat_id, "text": f"❌ Could not parse file: {parse_errors[0]}"},
                                    timeout=10,
                                )
                                continue

                            imported = 0
                            skipped = 0
                            flagged = 0
                            
                            for txn in transactions:
                                raw_txn_text = txn.get("raw_text", "")
                                if not raw_txn_text:
                                    skipped += 1
                                    continue
                                try:
                                    res = process_message(
                                        raw_text=raw_txn_text,
                                        channel="telegram_csv",
                                        sender_id=sender,
                                    )
                                    override_fields = {
                                        k: v for k, v in txn.items()
                                        if k not in ("raw_text", "source") and v is not None
                                    }
                                    if override_fields.get("amount"):
                                        msg_id = res["id"]
                                        set_clauses = ", ".join(
                                            f"{k}=:{k}" for k in override_fields
                                            if k in ("amount", "txn_direction", "txn_date",
                                                     "counterparty_name", "payment_method", "upi_reference")
                                        )
                                        if set_clauses:
                                            with db._lock:
                                                db.get_conn().execute(
                                                    f"UPDATE messages SET {set_clauses} WHERE id=:id",
                                                    {**override_fields, "id": msg_id},
                                                )
                                                db.get_conn().commit()
                                                
                                    ls = res.get("ledger_status", "n/a")
                                    if ls == "flagged":
                                        flagged += 1
                                    elif ls in ("draft", "confirmed"):
                                        imported += 1
                                    else:
                                        skipped += 1
                                except Exception as txn_err:
                                    logger.error("Telegram CSV row error: %s", txn_err)
                                    skipped += 1
                                    
                            summary = (
                                f"📊 *CSV Bulk Import Completed*\n"
                                f"🟢 Imported: {imported}\n"
                                f"🟡 Skipped: {skipped}\n"
                                f"🔴 Flagged Scams: {flagged}"
                            )
                            rq.post(
                                f"{base}/sendMessage",
                                json={"chat_id": chat_id, "text": summary, "parse_mode": "Markdown"},
                                timeout=10,
                            )
                            continue
                        except Exception as ce:
                            logger.error("Telegram CSV processing failed: %s", ce)
                            rq.post(
                                f"{base}/sendMessage",
                                json={"chat_id": chat_id, "text": f"❌ CSV import failed: {str(ce)}"},
                                timeout=10,
                            )
                            continue

                    elif file_name.endswith(".pdf"):
                        try:
                            pdf_bytes = _telegram_download_file(token, file_id)
                            from csv_importer import parse_bank_statement_pdf
                            rq.post(
                                f"{base}/sendMessage",
                                json={"chat_id": chat_id, "text": "📄 PDF received. Extracting transactions with AI…"},
                                timeout=10,
                            )
                            transactions, parse_errors = parse_bank_statement_pdf(pdf_bytes, language="english")

                            if not transactions:
                                err_msg = parse_errors[0] if parse_errors else "No transactions found in this PDF."
                                rq.post(
                                    f"{base}/sendMessage",
                                    json={"chat_id": chat_id, "text": f"❌ {err_msg}"},
                                    timeout=10,
                                )
                                continue

                            imported = 0
                            skipped  = 0
                            flagged  = 0
                            for txn in transactions:
                                raw_txn_text = txn.get("raw_text", "")
                                if not raw_txn_text:
                                    skipped += 1
                                    continue
                                try:
                                    res = process_message(
                                        raw_text=raw_txn_text,
                                        channel="telegram_pdf",
                                        sender_id=sender,
                                    )
                                    override_fields = {
                                        k: v for k, v in txn.items()
                                        if k not in ("raw_text", "source") and v is not None
                                    }
                                    if override_fields.get("amount"):
                                        msg_id = res["id"]
                                        set_clauses = ", ".join(
                                            f"{k}=:{k}" for k in override_fields
                                            if k in ("amount", "txn_direction", "txn_date",
                                                     "counterparty_name", "payment_method", "upi_reference")
                                        )
                                        if set_clauses:
                                            with db._lock:
                                                db.get_conn().execute(
                                                    f"UPDATE messages SET {set_clauses} WHERE id=:id",
                                                    {**override_fields, "id": msg_id},
                                                )
                                                db.get_conn().commit()
                                    ls = res.get("ledger_status", "n/a")
                                    if ls == "flagged":
                                        flagged += 1
                                    elif ls in ("draft", "confirmed"):
                                        imported += 1
                                    else:
                                        skipped += 1
                                except Exception as txn_err:
                                    logger.error("Telegram PDF row error: %s", txn_err)
                                    skipped += 1

                            summary = (
                                f"📊 *PDF Import Completed*\n"
                                f"🟢 Imported: {imported}\n"
                                f"🟡 Skipped: {skipped}\n"
                                f"🔴 Flagged Scams: {flagged}"
                            )
                            rq.post(
                                f"{base}/sendMessage",
                                json={"chat_id": chat_id, "text": summary, "parse_mode": "Markdown"},
                                timeout=10,
                            )
                            continue
                        except Exception as pe:
                            logger.error("Telegram PDF processing failed: %s", pe)
                            rq.post(
                                f"{base}/sendMessage",
                                json={"chat_id": chat_id, "text": f"❌ PDF import failed: {str(pe)}"},
                                timeout=10,
                            )
                            continue
                    else:
                        rq.post(
                            f"{base}/sendMessage",
                            json={"chat_id": chat_id, "text": "❌ Unsupported document format. Please send a .csv, .xlsx, or .pdf file."},
                            timeout=10,
                        )
                        continue

                # Post-processing routing: Invoice extraction vs normal transaction detection
                lower_text = text.lower()
                is_invoice = any(kw in lower_text for kw in ("invoice", "tax invoice", "bill", "challan", "purchased", "invoice no", "total amount"))

                if is_invoice:
                    rq.post(
                        f"{base}/sendMessage",
                        json={"chat_id": chat_id, "text": "🤖 Invoice detected! Extracting line items..."},
                        timeout=5,
                    )
                    from pipeline import extract_invoice_items_llm, sync_invoice_to_inventory
                    items = extract_invoice_items_llm(text)
                    if not items:
                        rq.post(
                            f"{base}/sendMessage",
                            json={
                                "chat_id": chat_id,
                                "text": (
                                    "⚠️ Could not extract line items automatically.\n\n"
                                    "This may happen when:\n"
                                    "• The AI model is temporarily unavailable\n"
                                    "• The invoice has a non-standard format\n\n"
                                    "✅ The text was parsed successfully. You can manually add items via the Inventory panel."
                                ),
                            },
                            timeout=10,
                        )
                    else:
                        sync_logs = sync_invoice_to_inventory(items)
                        reply = f"📦 *Invoice Sync Complete* — {len(items)} item(s) found:\n" + "\n".join(f"• {log}" for log in sync_logs)
                        rq.post(
                            f"{base}/sendMessage",
                            json={"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"},
                            timeout=10,
                        )
                else:
                    result = process_message(
                        raw_text=text,
                        channel="telegram",
                        sender_id=sender,
                        sender_name=sender_name,
                    )

                    verdict_emoji = {"scam": "🔴", "suspicious": "🟡", "legitimate": "🟢"}.get(
                        result["classification"], "⚪"
                    )
                    reply = (
                        f"{verdict_emoji} *{result['classification'].upper()}*"
                        f" — Risk: {result['risk_score']}/100\n"
                    )
                    if result.get("explanation"):
                        reply += f"\n_{result['explanation']}_\n"
                    if result.get("transaction") and result["transaction"].get("amount"):
                        txn = result["transaction"]
                        reply += (
                            f"\n💰 Transaction detected: ₹{txn.get('amount')} "
                            f"from {txn.get('counterparty_name') or 'unknown'}\n"
                            f"Status: {result['ledger_status']}"
                        )
                    if result.get("risk_signals"):
                        reply += "\n\n⚠️ " + " · ".join(result["risk_signals"][:3])

                    rq.post(
                        f"{base}/sendMessage",
                        json={"chat_id": chat_id, "text": reply, "parse_mode": "Markdown"},
                        timeout=10,
                    )

        except Exception as e:
            logger.error("Telegram poll error: %s", e)
            time.sleep(10)


def _telegram_download_file(token: str, file_id: str) -> bytes:
    import requests as rq
    base = f"https://api.telegram.org/bot{token}"
    resp = rq.get(f"{base}/getFile", params={"file_id": file_id}, timeout=15)
    if not resp.ok:
        raise ValueError(f"Telegram getFile failed: {resp.text}")
    file_path = resp.json().get("result", {}).get("file_path")
    if not file_path:
        raise ValueError(f"No file path returned for file_id {file_id}")
    
    file_resp = rq.get(f"https://api.telegram.org/file/bot{token}/{file_path}", timeout=30)
    if not file_resp.ok:
        raise ValueError(f"Telegram file download failed: {file_resp.status_code}")
    return file_resp.content


def _telegram_download_file_to_path(token: str, file_id: str, dest_path: str):
    content = _telegram_download_file(token, file_id)
    with open(dest_path, "wb") as f:
        f.write(content)


def _start_telegram_bot():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "your_telegram_bot_token":
        logger.info("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")
        return
    t = threading.Thread(target=_telegram_poll_loop, args=(token,), daemon=True)
    t.start()


# ── Connection info (for SMS setup UI) ───────────────────────────────────────

@app.get("/api/connection-info")
async def connection_info():
    """
    Returns the local network IP and webhook URL so the frontend can display
    setup instructions and a QR code for the SMS Forwarder Android app.
    """
    import socket
    try:
        # Connect to a public address to discover the local network IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    webhook_url = f"http://{local_ip}:8000/api/sms-webhook"
    return {
        "local_ip":    local_ip,
        "webhook_url": webhook_url,
        "port":        8000,
    }


# ── CSV Bulk Import ───────────────────────────────────────────────────────────

@app.post("/api/import/csv")
async def import_csv(
    file:     UploadFile = File(...),
    app_name: str        = Form("auto"),
    language: str        = Form("english"),
):
    """
    Bulk-import a transaction CSV or XLSX exported from:
      PhonePe, Google Pay, Paytm (CSV & XLSX),
      HDFC, SBI, ICICI, Axis, Kotak bank statements,
      or any generic CSV/XLSX with debit/credit columns.

    Each row is parsed into a transaction dict and run through the full pipeline.
    Clean transactions are inserted into the active monthly ledger.

    app_name: 'phonepe' | 'gpay' | 'paytm' | 'hdfc' | 'sbi' | 'icici' | 'axis' | 'kotak' | 'auto'
    Returns:  { imported, skipped, flagged, errors, results }
    """
    fname = (file.filename or "").lower()
    if not any(fname.endswith(ext) for ext in (".csv", ".xlsx", ".xls", ".pdf")):
        raise HTTPException(status_code=400, detail="Please upload a .csv, .xlsx, or .pdf file.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10 MB limit (PDFs can be larger)
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")

    language = validate_language(language)

    # Route PDF through the dedicated AI-powered PDF parser
    if fname.endswith(".pdf"):
        from csv_importer import parse_bank_statement_pdf
        transactions, parse_errors = parse_bank_statement_pdf(contents, language=language)
    else:
        # Parse CSV / XLSX into normalised transaction rows
        transactions, parse_errors = parse_csv(contents, app=app_name, filename=file.filename or "")
    if not transactions and parse_errors:
        raise HTTPException(
            status_code=422,
            detail=f"Could not parse file: {parse_errors[0]}",
        )

    imported = 0
    skipped  = 0
    flagged  = 0
    results  = []

    for txn in transactions:
        # Build a human-readable message for the pipeline
        raw_text = txn.get("raw_text", "")
        if not raw_text:
            skipped += 1
            continue

        try:
            # Run through the full fraud + extraction pipeline
            result = process_message(
                raw_text=raw_text,
                channel="csv_import",
                sender_id=app_name,
            )

            # Override transaction fields with the already-parsed CSV data
            # (more reliable than LLM extraction for structured CSVs)
            override_fields = {
                k: v for k, v in txn.items()
                if k not in ("raw_text", "source") and v is not None
            }
            if override_fields.get("amount"):
                msg_id = result["id"]
                # Update the DB record with parsed CSV fields
                import db as _db
                conn = _db.get_conn()
                set_clauses = ", ".join(
                    f"{k}=:{k}" for k in override_fields
                    if k in ("amount", "txn_direction", "txn_date",
                             "counterparty_name", "payment_method", "upi_reference")
                )
                if set_clauses:
                    with _db._lock:
                        conn.execute(
                            f"UPDATE messages SET {set_clauses} WHERE id=:id",
                            {**override_fields, "id": msg_id},
                        )
                        conn.commit()

            ls = result.get("ledger_status", "n/a")
            if ls == "flagged":
                flagged += 1
            elif ls in ("draft", "confirmed"):
                imported += 1
            else:
                skipped += 1

            results.append({
                "text":          raw_text[:80],
                "amount":        txn.get("amount"),
                "direction":     txn.get("txn_direction"),
                "ledger_status": ls,
                "risk_score":    result["risk_score"],
                "classification": result["classification"],
            })
        except Exception as e:
            logger.error("CSV import row error: %s", e)
            skipped += 1
            parse_errors.append(str(e))

    return {
        "imported": imported,
        "flagged":  flagged,
        "skipped":  skipped,
        "total":    len(transactions),
        "errors":   parse_errors[:10],
        "results":  results,
    }



# ── Serve frontend (must be last so /api/* routes take priority) ──────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")


# =============================================================================
# INVENTORY endpoints
# =============================================================================

@app.get("/api/inventory")
def get_inventory():
    """Return all inventory / stock items."""
    return db.get_inventory()


@app.post("/api/inventory")
async def upsert_inventory_item(request: Request):
    """Add or update a stock item.
    Body: {item_name, quantity, cost_price, unit}
    """
    body = await request.json()
    name = (body.get("item_name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="item_name is required")
    item = db.add_or_update_inventory_item(
        item_name=name,
        quantity=float(body.get("quantity") or 0),
        cost_price=float(body.get("cost_price") or 0),
        unit=body.get("unit", "unit"),
    )
    return item


@app.delete("/api/inventory/{item_id}")
def delete_inventory_item(item_id: int):
    """Delete a stock item by ID."""
    ok = db.delete_inventory_item(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "deleted", "id": item_id}


@app.post("/api/inventory/manual-cash")
async def manual_cash_transaction(request: Request):
    """
    Record a manual cash transaction (sale or purchase) and update stock.
    Body: {item_name, quantity, unit_price, direction ('inflow'|'outflow'), note}
    """
    body = await request.json()
    item_name = (body.get("item_name") or "").strip()
    quantity   = float(body.get("quantity") or 0)
    unit_price = float(body.get("unit_price") or 0)
    direction  = body.get("direction", "inflow")   # inflow = sale, outflow = purchase
    note       = body.get("note", "")

    if not item_name or quantity <= 0:
        raise HTTPException(status_code=400, detail="item_name and positive quantity required")

    amount = round(quantity * unit_price, 2)

    # Build synthetic raw_text for pipeline logging
    action = "sold" if direction == "inflow" else "purchased"
    raw_text = f"Manual: {action} {quantity} {item_name} at ₹{unit_price} each. Total ₹{amount}. {note}".strip()

    from pipeline import categorize_transaction
    category = categorize_transaction(raw_text, direction)

    # Persist to DB as a confirmed ledger entry
    import datetime as _dt
    msg_id = db.insert_message({
        "channel":          "manual",
        "sender_id":        "manual_entry",
        "sender_name":      "Merchant",
        "raw_text":         raw_text,
        "language":         "english",
        "classification":   "legitimate",
        "classifier_stage": "manual",
        "confidence":       1.0,
        "amount":           amount,
        "currency":         "INR",
        "counterparty_name": item_name,
        "txn_direction":    direction,
        "purpose":          f"{action.capitalize()} {item_name}",
        "risk_score":       0,
        "risk_signals":     [],
        "explanation":      "Manual cash entry",
        "ledger_status":    "confirmed",
        "category":         category,
    })

    # Update stock
    delta = -quantity if direction == "inflow" else +quantity
    updated_item = db.adjust_stock(item_name, delta)

    return {
        "status":       "recorded",
        "msg_id":       msg_id,
        "amount":       amount,
        "direction":    direction,
        "item_name":    item_name,
        "quantity":     quantity,
        "stock_after":  updated_item.get("quantity") if updated_item else None,
    }


# =============================================================================
# KHATA / DUES NUDGE
# =============================================================================

@app.get("/api/dashboard/dues-nudge")
def dues_nudge():
    """
    Return a human-readable morning nudge listing outstanding informal credit.
    """
    dues = db.get_outstanding_dues()
    if not dues:
        return {"nudge": "All clear! No outstanding dues today.", "dues": []}

    lines = []
    for d in dues:
        name   = d.get("counterparty_name") or "Unknown"
        amount = d.get("net_owed", 0)
        days   = d.get("days_outstanding", 0)
        if days == 0:
            when = "today"
        elif days == 1:
            when = "yesterday"
        else:
            when = f"{days} days ago"
        lines.append(f"{name} owes ₹{amount:,.0f} (since {when})")

    nudge_text = "Outstanding dues: " + "; ".join(lines) + "."
    return {"nudge": nudge_text, "dues": dues}


# =============================================================================
# AI LEDGER CHAT (conversational LLM over ledger data)
# =============================================================================
# AI BUSINESS COPILOT (enhanced chat + Digital Twin what-if)
# =============================================================================

@app.post("/api/chat/ledger")
async def ledger_chat(request: Request):
    """
    AI Business Copilot — natural language Q&A over the merchant's full ledger.
    Supports:
      - Normal questions: 'Which supplier increased prices?'
      - Root-cause analysis: 'Why did my profit decrease?'
      - Digital Twin what-if: 'What if I increase rice price by ₹5?'
    Body: {question: str, month: str|null}
    """
    import json as _json
    import google.generativeai as genai
    import os as _os

    body     = await request.json()
    question = (body.get("question") or "").strip()
    month    = body.get("month")
    language = validate_language(body.get("language", "english"))

    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    genai.configure(api_key=_os.environ.get("GEMINI_API_KEY", ""))

    # Gather rich context including supplier + memory
    stats      = db.get_stats(month)
    dues       = db.get_outstanding_dues()
    inventory  = db.get_inventory()
    breakdown  = db.get_category_breakdown(month)
    messages   = db.get_messages(limit=50)
    suppliers  = db.get_supplier_history(limit=10)
    velocity   = db.get_sales_velocity(days=90)
    memory     = db.get_business_memory()

    # Detect question mode for richer system prompt
    q_lower = question.lower()
    is_why   = any(w in q_lower for w in ["why", "reason", "cause", "because", "decline", "decrease", "drop"])
    is_what_if = any(w in q_lower for w in ["what if", "what happens if", "if i", "simulate", "suppose"])

    if is_what_if:
        mode_instruction = (
            "The merchant is asking a WHAT-IF SIMULATION (Digital Twin). "
            "Estimate the likely impact on revenue, profit, demand, and inventory. "
            "Be specific: give percentage and ₹ estimates. Acknowledge uncertainty clearly."
        )
    elif is_why:
        mode_instruction = (
            "The merchant wants ROOT CAUSE ANALYSIS. "
            "Identify 2–4 specific contributing factors from the data. "
            "Explain WHAT happened, WHY it happened, and WHAT to do about it."
        )
    else:
        mode_instruction = (
            "Answer the merchant's question directly and concisely using the ledger data. "
            "Provide actionable follow-up advice where relevant."
        )

    context = {
        "period":             stats.get("active_month", "current month"),
        "total_inflow":       stats.get("total_earnings", 0),
        "total_spendings":    stats.get("total_spendings", 0),
        "net_profit_loss":    stats.get("net_profit_loss", 0),
        "confirmed_txns":     stats.get("confirmed_txns", 0),
        "category_breakdown": breakdown,
        "outstanding_dues":   dues[:5],
        "inventory":          [{"item": i["item_name"], "qty": i["quantity"], "cost": i["cost_price"]} for i in inventory[:20]],
        "supplier_history":   suppliers[:5],
        "sales_velocity":     velocity[:10],
        "business_memory":    memory,
        "recent_transactions": [
            {k: m.get(k) for k in ("raw_text", "amount", "txn_direction", "counterparty_name", "purpose", "category", "confirmed_at")}
            for m in messages if m.get("ledger_status") == "confirmed"
        ][:20],
    }

    system_prompt = (
        "You are an expert AI Business Copilot for a small Indian shopkeeper (kirana/grocery/medical store). "
        "You have access to their complete financial ledger, inventory, supplier history, and sales velocity. "
        "Be warm, practical, and use ₹ for amounts. Speak like a trusted CA friend, not a corporate bot. "
        "CRITICAL RULE: If the user's question is entirely unrelated to their business, finance, accounting, or ledger data, "
        "politely refuse to answer and remind them that you are their AI business accountant.\n"
        f"{mode_instruction}\n"
        f"You MUST generate the entire response in the '{language.capitalize()}' language."
    )
    user_prompt = (
        f"Business data:\n{_json.dumps(context, ensure_ascii=False, indent=2)[:3000]}\n\n"
        f"Question: {question}"
    )

    try:
        model  = genai.GenerativeModel("gemini-3.5-flash")
        result = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
        answer = result.text.strip()
    except Exception as e:
        logger.error("AI Copilot LLM error: %s", e)
        answer = "Sorry, I couldn't process that right now. Please try again in a moment."

    return {"question": question, "answer": answer, "mode": "what_if" if is_what_if else "root_cause" if is_why else "standard"}


# =============================================================================
# AI MONTHLY NARRATIVE
# =============================================================================

@app.get("/api/dashboard/narrative")
def monthly_narrative(month: str | None = None, language: str = "english"):
    """
    Generate a plain-language accountant's summary of the month's financials.
    """
    import json as _json
    import google.generativeai as genai
    import os as _os

    genai.configure(api_key=_os.environ.get("GEMINI_API_KEY", ""))

    stats     = db.get_stats(month)
    breakdown = db.get_category_breakdown(month)
    dues      = db.get_outstanding_dues()
    snapshots = db.get_daily_snapshots(7)

    context = {
        "period":          stats.get("active_month", "this month"),
        "total_earnings":  stats.get("total_earnings", 0),
        "total_spendings": stats.get("total_spendings", 0),
        "net_profit_loss": stats.get("net_profit_loss", 0),
        "confirmed_txns":  stats.get("confirmed_txns", 0),
        "scam_count":      stats.get("scam_count", 0),
        "category_breakdown": breakdown,
        "outstanding_dues_count": len(dues),
        "recent_snapshots": snapshots[:7],
    }

    prompt = (
        "You are a friendly accountant summarising a small Indian shopkeeper's month. "
        "Write 3–5 sentences in a warm, plain tone — like a friend who is also a CA. "
        "Highlight key wins, one concern to watch, and end with a practical tip. "
        "Use ₹ for amounts. Do NOT use bullet points — write flowing prose.\n"
        f"You MUST generate the entire summary in the '{language.capitalize()}' language.\n\n"
        f"Financial data:\n{_json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    try:
        model     = genai.GenerativeModel("gemini-3.5-flash")
        result    = model.generate_content(prompt)
        narrative = result.text.strip()
    except Exception as e:
        logger.error("Narrative LLM error: %s", e)
        earnings  = stats.get("total_earnings", 0)
        spendings = stats.get("total_spendings", 0)
        pnl       = stats.get("net_profit_loss", 0)
        narrative = (
            f"This month you earned ₹{earnings:,.0f} and spent ₹{spendings:,.0f}, "
            f"leaving a net {'profit' if pnl >= 0 else 'loss'} of ₹{abs(pnl):,.0f}. "
            f"You processed {stats.get('confirmed_txns',0)} confirmed transactions. "
            f"Keep reviewing your spending categories to find savings!"
        )
        if language != "english":
            from translate import translate_text
            narrative = translate_text(narrative, language)

    return {"month": stats.get("active_month"), "narrative": narrative}


# =============================================================================
# DAILY CLOSING SNAPSHOT
# =============================================================================

@app.post("/api/dashboard/close-day")
async def close_day(request: Request):
    """
    Lock in today's closing position.
    Body: {cash_balance, note}  (inventory_value and khata auto-computed)
    """
    body = await request.json()
    cash  = float(body.get("cash_balance") or 0)
    note  = body.get("note", "")

    # Auto-compute inventory value
    inventory = db.get_inventory()
    inv_value = sum((i.get("quantity") or 0) * (i.get("cost_price") or 0) for i in inventory)

    # Auto-compute khata receivable
    dues = db.get_outstanding_dues()
    khata = sum(d.get("net_owed", 0) for d in dues)

    snapshot = db.save_daily_snapshot(
        cash_balance=cash,
        inventory_value=round(inv_value, 2),
        khata_receivable=round(khata, 2),
        note=note,
    )
    return {"status": "saved", "snapshot": snapshot}


@app.get("/api/dashboard/snapshots")
def get_snapshots():
    """Return recent daily closing snapshots."""
    return db.get_daily_snapshots(30)


# =============================================================================
# CATEGORY BREAKDOWN
# =============================================================================

@app.get("/api/dashboard/category-breakdown")
def category_breakdown(month: str | None = None):
    """Return expense totals grouped by category for the given month."""
    return db.get_category_breakdown(month)


# =============================================================================
# CSV EXPORT
# =============================================================================

@app.get("/api/dashboard/export/csv")
def export_csv(month: str | None = None):
    """
    Download the month's confirmed transactions as a CSV file.
    """
    import csv
    import io
    from fastapi.responses import StreamingResponse

    rows = db.get_export_data(month)
    if not rows:
        raise HTTPException(status_code=404, detail="No confirmed transactions found for this period")

    output = io.StringIO()
    fieldnames = [
        "id", "received_at", "ledger_month", "channel",
        "counterparty_name", "counterparty_phone",
        "amount", "currency", "purpose", "payment_method",
        "upi_reference", "txn_direction", "risk_score",
        "classification", "confirmed_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    filename = f"pramaan_ledger_{month or 'all'}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# =============================================================================
# AI DECISION INTELLIGENCE LAYER
# =============================================================================

@app.get("/api/dashboard/insights")
async def get_insights(month: str | None = None, language: str = "english"):
    """
    Unified AI Decision Intelligence endpoint.
    Returns all 10 insight modules in a single response:
      - AI Business Copilot health + priority actions
      - Pricing Optimizer recommendations
      - Demand Forecasting (days of stock, reorder urgency)
      - Purchase Optimizer (supplier + items + cost)
      - Supplier Intelligence scores
      - AI Promotion Advisor (weekend/festival/clearance/combo)
      - Smart Bundle Recommendations
      - Profit Leakage Detection report
    Falls back to rule-based insights if LLM is unavailable.
    """
    from insights import generate_insights

    inventory = db.get_inventory()
    stats     = db.get_stats(month)
    velocity  = db.get_sales_velocity(days=90)
    suppliers = db.get_supplier_history(limit=20)
    dues      = db.get_outstanding_dues()
    memory    = db.get_business_memory()

    result = generate_insights(
        inventory=inventory,
        stats=stats,
        velocity=velocity,
        suppliers=suppliers,
        dues=dues,
        memory=memory,
    )

    # Persist updated business memory if LLM returned one
    if result.get("business_memory_update"):
        db.set_business_memory(result["business_memory_update"])

    return result


@app.post("/api/inventory/update-price")
async def update_inventory_price_endpoint(request: Request):
    """
    Apply an AI pricing recommendation to inventory.
    Body: {item_name: str, new_price: float}
    """
    body      = await request.json()
    item_name = (body.get("item_name") or "").strip()
    new_price = body.get("new_price")

    if not item_name:
        raise HTTPException(status_code=400, detail="item_name is required")
    if new_price is None or float(new_price) < 0:
        raise HTTPException(status_code=400, detail="new_price must be a non-negative number")

    updated = db.update_inventory_price(item_name, float(new_price))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Item '{item_name}' not found in inventory")

    return {"status": "updated", "item": updated}


@app.get("/api/dashboard/business-memory")
async def get_business_memory_endpoint():
    """
    Retrieve the AI's current business memory / personalization summary.
    """
    memory = db.get_business_memory()
    return {"memory": memory, "has_memory": bool(memory)}


app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
