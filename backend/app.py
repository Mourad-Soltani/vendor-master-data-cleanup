"""Flask HTTP surface for the Vendor Master Data Cleanup engine.

Author: Mourad.Soltani
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request, send_from_directory

from backend import vendor_matcher
from backend.config import (
    AUTHOR,
    MAX_CONTENT_LENGTH,
    MAX_VENDORS_PER_REQUEST,
    PROJECT_NAME,
    SIGNATURE,
    VERSION,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"
)
_INDEX_PATH = os.path.join(FRONTEND_DIR, "index.html")

if not os.path.isfile(_INDEX_PATH):
    logger.warning(
        "frontend/index.html not found at %s — UI routes will return 404", _INDEX_PATH
    )


# --- Envelope helper ---------------------------------------------------------

def _envelope(payload: dict, status: int = 200):
    body = {"signature": SIGNATURE, "author": AUTHOR, "version": VERSION}
    body.update(payload)
    return jsonify(body), status


# --- Error handlers ----------------------------------------------------------

@app.errorhandler(400)
def _err_400(e):
    return _envelope({"error": "bad_request", "message": str(getattr(e, "description", e))}, 400)


@app.errorhandler(404)
def _err_404(e):
    return _envelope({"error": "not_found", "message": "Endpoint not found"}, 404)


@app.errorhandler(413)
def _err_413(e):
    return _envelope({"error": "payload_too_large", "message": "Request body exceeds limit"}, 413)


@app.errorhandler(500)
def _err_500(e):
    return _envelope({"error": "internal_error", "message": "Server error"}, 500)


# --- Routes ------------------------------------------------------------------

@app.get("/health")
def health():
    return _envelope({
        "status": "ok",
        "project": PROJECT_NAME,
    })


@app.get("/")
def index():
    return _envelope({
        "project": PROJECT_NAME,
        "endpoints": ["/health", "/api/classify", "/api/deduplicate", "/ui"],
    })


@app.post("/api/classify")
def classify():
    data = request.get_json(silent=True)
    if data is None:
        return _envelope({"error": "invalid_json", "message": "Body must be valid JSON"}, 400)
    if not isinstance(data, dict):
        return _envelope({"error": "invalid_payload", "message": "Body must be a JSON object"}, 400)

    a = data.get("a")
    b = data.get("b")
    if not isinstance(a, dict) or not isinstance(b, dict):
        return _envelope(
            {"error": "invalid_payload", "message": "'a' and 'b' must be JSON objects"},
            400,
        )

    result = vendor_matcher.classify_pair(a, b)
    return _envelope({"result": result})


@app.post("/api/deduplicate")
def deduplicate():
    data = request.get_json(silent=True)
    if data is None:
        return _envelope({"error": "invalid_json", "message": "Body must be valid JSON"}, 400)
    if not isinstance(data, dict):
        return _envelope({"error": "invalid_payload", "message": "Body must be a JSON object"}, 400)

    vendors = data.get("vendors")
    if not isinstance(vendors, list):
        return _envelope({"error": "invalid_payload", "message": "'vendors' must be an array"}, 400)
    if len(vendors) > MAX_VENDORS_PER_REQUEST:
        return _envelope(
            {"error": "payload_too_large",
             "message": f"Maximum {MAX_VENDORS_PER_REQUEST} vendors per request"},
            400,
        )
    for i, v in enumerate(vendors):
        if not isinstance(v, dict):
            return _envelope(
                {"error": "invalid_payload", "message": f"vendors[{i}] must be an object"},
                400,
            )

    result = vendor_matcher.deduplicate(vendors)
    return _envelope({"result": result})


# --- UI (static) -------------------------------------------------------------

@app.get("/ui")
def ui_index():
    if not os.path.isfile(_INDEX_PATH):
        return _envelope({"error": "not_found", "message": "UI not available"}, 404)
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/ui/<path:filename>")
def ui_static(filename: str):
    return send_from_directory(FRONTEND_DIR, filename)
