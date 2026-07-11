"""
ai_provider.py — Unified AI provider for Pramaan.

Priority order:
  1. Groq  (llama-3.1-70b-versatile) — 14,400 free requests/day, no project quota issues
  2. Gemini (gemini-3.5-flash)        — 20 free requests/day (project-level quota)
  3. Rule-based fallback              — always works, no API needed

Usage:
    from ai_provider import call_ai, call_ai_json

    text = call_ai("Explain this ledger entry...")
    data = call_ai_json("Return JSON of top expenses...", schema_hint="list of {name, amount}")
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

logger = logging.getLogger("pramaan_api")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _call_groq(prompt: str, system: str = "", max_tokens: int = 1500) -> str | None:
    """Call Groq API (OpenAI-compatible). 14,400 free req/day."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import urllib.request, json as _json
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = _json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }).encode()

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0 (Pramaan AI Accountant Bot)",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("Groq call failed: %s", str(e)[:120])
        return None


def _call_gemini(prompt: str, system: str = "", max_tokens: int = 1500) -> str | None:
    """Call Gemini API. 20 free req/day (project-level quota)."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        model = genai.GenerativeModel("gemini-3.5-flash")
        result = model.generate_content(full_prompt)
        return result.text.strip()
    except Exception as e:
        err = str(e)
        logger.warning("Gemini call failed: %s", err[:120])
        return None


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from AI output."""
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    return text.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_ai(prompt: str, system: str = "", max_tokens: int = 1500) -> str | None:
    """
    Call AI with text prompt. Returns plain text response.
    Tries Groq first, then Gemini. Returns None if both fail.
    """
    result = _call_groq(prompt, system=system, max_tokens=max_tokens)
    if result:
        logger.info("AI response via Groq (llama-3.1-70b)")
        return result

    result = _call_gemini(prompt, system=system, max_tokens=max_tokens)
    if result:
        logger.info("AI response via Gemini (gemini-3.5-flash)")
        return result

    logger.warning("All AI providers failed — no response")
    return None


def call_ai_json(prompt: str, system: str = "", max_tokens: int = 2000) -> dict | list | None:
    """
    Call AI expecting a JSON response. Parses and returns parsed object.
    Tries Groq first, then Gemini. Returns None if both fail or JSON is invalid.
    """
    raw = call_ai(prompt, system=system, max_tokens=max_tokens)
    if not raw:
        return None
    try:
        cleaned = _strip_fences(raw)
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("AI returned invalid JSON: %s | raw: %s", e, raw[:200])
        return None


def provider_status() -> dict:
    """Return which providers are configured (for diagnostics)."""
    return {
        "groq": bool(os.environ.get("GROQ_API_KEY", "").strip()),
        "gemini": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
    }
