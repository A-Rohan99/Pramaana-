"""
Scheme cross-check + on-demand scheme search module.

Two entry points into the same underlying seeded ChromaDB:
  - check_scheme_claim(): triggered when a forwarded message appears to
    reference a scheme (used by api.py's verification pipeline)
  - search_schemes(): triggered directly by a user asking "what schemes
    am I eligible for" or searching by scheme name (on-demand feature)

Both return results through format_scheme_layout(), which ALWAYS
produces the exact four-field layout specified: Eligibility, Location,
Required Documents, Contact Info -- falling back to explicit "not
mentioned" style defaults rather than inventing information that isn't
in the seed data. This is deliberate: fabricating a plausible-sounding
eligibility criterion or document requirement is exactly the kind of
false-certainty failure this project exists to avoid.

Dynamic Online Expansion (new)
-------------------------------
When a query has no close match in the local ChromaDB (distance above
UNKNOWN_DISTANCE_THRESHOLD), the system falls back to an online search
via Gemini with Search Grounding (online_scheme.py).

  - If the online lookup confirms the scheme is REAL: the scheme is
    persisted to ChromaDB and to the seed JSON so it is available on all
    future queries without calling the API again.
  - If the online lookup marks the scheme as FAKE/SCAM: a warning card
    is returned and NOTHING is added to the DB.
  - If the API key is not set or the network call fails: the function
    returns None gracefully (no crash, no false data).
"""

import json
import logging
import os
import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

SEED_PATH = "data/schemes_seed.json"
COLLECTION_NAME = "gov_schemes"

# L2/cosine distance above this value means the query did not closely
# match any scheme in the local DB -- trigger the online lookup.
UNKNOWN_DISTANCE_THRESHOLD = 1.0

_embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


def build_collection(persist_path: str = "./chroma_store"):
    """Run once at startup to seed the DB from the local JSON source of truth."""
    client = chromadb.PersistentClient(path=persist_path)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_fn,
    )

    if collection.count() > 0:
        return collection

    with open(SEED_PATH, encoding="utf-8") as f:
        schemes = json.load(f)

    documents, ids, metadatas = [], [], []
    for i, s in enumerate(schemes):
        doc_text = f"{s['scheme_name']} ({s.get('full_name', '')}). Benefit: {s.get('benefit', '')}. Eligibility: {s.get('eligibility', '')}."
        documents.append(doc_text)
        ids.append(f"scheme_{i}")
        # ChromaDB metadata can't store None -- normalize nulls to empty
        # string here, and format_scheme_layout() maps empty -> the
        # correct "not mentioned" default text.
        meta = {k: (v if v is not None else "") for k, v in s.items()}
        metadatas.append(meta)

    collection.add(documents=documents, ids=ids, metadatas=metadatas)
    return collection


def format_scheme_layout(meta: dict) -> dict:
    """
    Enforces the strict four-field output layout. Never fabricates a
    value -- falls back to the specified default text when the seed
    data genuinely has no entry for that field.
    """
    return {
        "scheme_name": meta.get("scheme_name", "Unknown scheme"),
        "eligibility": meta.get("eligibility") or "Not mentioned",
        "location": meta.get("location") or "No location restriction -- apply online only",
        "required_documents": meta.get("required_documents") or "Not mentioned",
        "contact_info": meta.get("contact_info") or f"Visit official website: {meta.get('official_source', 'N/A')}",
        "official_source": meta.get("official_source", "N/A"),
    }


def add_new_scheme_to_db(scheme: dict, collection) -> None:
    """
    Persist a newly verified (real) scheme to ChromaDB and to the seed
    JSON file so future server restarts don't need to re-query online.

    Only called when online_scheme.lookup_scheme_online() returns
    is_real=True -- fake schemes are NEVER added to the DB.
    """
    # Generate a unique ID based on the scheme name slug
    slug = scheme.get("scheme_name", "unknown").lower().replace(" ", "_")
    new_id = f"scheme_online_{slug}"

    # Avoid adding duplicates to the vector store
    existing = collection.get(ids=[new_id])
    if existing and existing.get("ids"):
        logger.info("Scheme '%s' already in DB, skipping add.", scheme.get("scheme_name"))
        return

    doc_text = (
        f"{scheme.get('scheme_name', '')} ({scheme.get('full_name', '')}). "
        f"Benefit: {scheme.get('benefit', '')}. "
        f"Eligibility: {scheme.get('eligibility', '')}."
    )
    meta = {k: (v if v is not None else "") for k, v in scheme.items()
            if isinstance(v, (str, int, float, bool))}

    collection.add(documents=[doc_text], ids=[new_id], metadatas=[meta])
    logger.info("Added new scheme '%s' to ChromaDB.", scheme.get("scheme_name"))

    # Append to the seed JSON for persistence across restarts
    try:
        seed_entry = {
            "scheme_name": scheme.get("scheme_name", ""),
            "full_name": scheme.get("full_name", ""),
            "benefit": scheme.get("benefit", ""),
            "eligibility": scheme.get("eligibility"),
            "location": scheme.get("location"),
            "required_documents": scheme.get("required_documents"),
            "contact_info": scheme.get("contact_info"),
            "real_process": scheme.get("real_process"),
            "official_source": scheme.get("official_source", ""),
        }
        if os.path.exists(SEED_PATH):
            with open(SEED_PATH, encoding="utf-8") as f:
                seeds = json.load(f)
        else:
            seeds = []

        # Skip if already present in seed file
        existing_names = {s.get("scheme_name", "").lower() for s in seeds}
        if seed_entry["scheme_name"].lower() not in existing_names:
            seeds.append(seed_entry)
            with open(SEED_PATH, "w", encoding="utf-8") as f:
                json.dump(seeds, f, indent=2, ensure_ascii=False)
            logger.info("Persisted scheme '%s' to seed JSON.", scheme.get("scheme_name"))
    except Exception as e:
        logger.error("Failed to persist scheme to seed JSON: %s", e)


def _try_online_lookup(query_text: str, collection) -> dict | None:
    """
    Internal helper: attempt an online lookup and persist to DB if real.
    Returns a formatted layout dict, or None if unavailable.
    """
    try:
        from online_scheme import lookup_scheme_online
        result = lookup_scheme_online(query_text)
        if result is None:
            return None

        if result.get("is_real"):
            # Verified real scheme -- persist it and return the layout
            add_new_scheme_to_db(result, collection)
            layout = format_scheme_layout(result)
            layout["real_process"] = result.get("real_process", "")
            layout["is_online_result"] = True
            return layout
        else:
            # Fake/unverified -- return a warning card, do NOT persist
            result["is_online_result"] = True
            return result

    except ImportError:
        logger.warning("online_scheme module not available.")
        return None
    except Exception as e:
        logger.error("Online scheme lookup error: %s", e)
        return None


def check_scheme_claim(clean_text: str, collection, top_k: int = 1) -> dict | None:
    """
    Used by the verification pipeline when a forwarded message appears
    to reference a scheme. Returns the real process comparison PLUS
    the strict layout, so the bot can show both "here's what actually
    happens" and the full reference card in one response.

    If the closest local match distance exceeds UNKNOWN_DISTANCE_THRESHOLD,
    falls back to an online Gemini-grounded search.
    """
    results = collection.query(query_texts=[clean_text], n_results=top_k)
    if not results["metadatas"] or not results["metadatas"][0]:
        return _try_online_lookup(clean_text, collection)

    meta = results["metadatas"][0][0]
    distance = results["distances"][0][0] if results.get("distances") else None

    # If the match is too distant, the local DB doesn't know this scheme
    if distance is not None and distance > UNKNOWN_DISTANCE_THRESHOLD:
        logger.info(
            "No close local match (distance=%.4f) for query '%s' -- trying online lookup.",
            distance, clean_text[:80]
        )
        online_result = _try_online_lookup(clean_text, collection)
        if online_result is not None:
            return online_result
        # Online lookup unavailable -- fall through to the best local match
        # rather than returning nothing, but flag it clearly
        logger.info("Falling back to best local match for '%s'.", clean_text[:80])

    layout = format_scheme_layout(meta)
    layout["real_process"] = meta.get("real_process", "")
    layout["match_distance"] = distance
    return layout


def search_schemes(query_text: str, collection, top_k: int = 3) -> list[dict]:
    """
    On-demand search -- user asks "what am I eligible for" or searches
    by scheme name directly. Returns the strict layout for each match,
    ranked by relevance, so the user can browse rather than only ever
    getting one result.

    If the top result's distance exceeds UNKNOWN_DISTANCE_THRESHOLD,
    an online lookup is attempted first and prepended to the results.
    """
    results = collection.query(query_texts=[query_text], n_results=top_k)

    if not results["metadatas"] or not results["metadatas"][0]:
        # Nothing in local DB at all -- go online only
        online = _try_online_lookup(query_text, collection)
        return [online] if online else []

    top_distance = (
        results["distances"][0][0]
        if results.get("distances") and results["distances"][0]
        else None
    )

    local_results = [format_scheme_layout(meta) for meta in results["metadatas"][0]]

    # If the top match is poor, try online and prepend the live result
    if top_distance is not None and top_distance > UNKNOWN_DISTANCE_THRESHOLD:
        logger.info(
            "Top local search match distance=%.4f for '%s' -- trying online lookup.",
            top_distance, query_text[:80]
        )
        online = _try_online_lookup(query_text, collection)
        if online is not None:
            return [online] + local_results

    return local_results
