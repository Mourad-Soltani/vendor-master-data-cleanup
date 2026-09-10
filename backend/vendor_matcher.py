"""Deterministic vendor master data matching engine.

The decision tree here is intentionally rule-based, not model-based:
buyers in mid-market finance ops need explainable merge decisions they
can hand to an auditor. No external API calls. No randomness. No state.

Author: Mourad.Soltani
"""

from __future__ import annotations

import re
from typing import Any


LEGAL_SUFFIXES: set[str] = {
    "inc", "incorporated", "llc", "llp", "lp", "ltd", "limited",
    "corp", "corporation", "co", "company",
    "gmbh", "ag", "kg", "ohg", "ug",
    "sa", "sas", "sarl", "bv", "nv", "plc", "pty", "pvt",
    "srl", "spa", "sprl", "kk", "oy", "ab", "as", "aps",
}


def _clean_tokens(value: Any) -> list[str]:
    """Lowercase, replace non-alphanumeric with space, split on whitespace."""
    if not isinstance(value, str):
        return []
    return [t for t in re.sub(r"[^a-z0-9]+", " ", value.lower()).split() if t]


def normalize_name(name: Any) -> str:
    """Canonical company name: lowercase, punctuation stripped, legal suffixes removed.

    If stripping suffixes would empty the name (e.g. input was literally "Inc"),
    fall back to the raw tokens so the record still has a signal.
    """
    toks = _clean_tokens(name)
    stripped = [t for t in toks if t not in LEGAL_SUFFIXES]
    final = stripped if stripped else toks
    return " ".join(final)


def name_tokens(name: Any) -> set[str]:
    return set(normalize_name(name).split())


def address_tokens(address: Any) -> set[str]:
    return set(_clean_tokens(address))


def normalize_identifier(value: Any) -> str:
    """Normalize tax ids / bank accounts: lowercase, strip non-alphanumeric."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def jaccard(a: set, b: set) -> float:
    """Public Jaccard similarity. Both empty -> 1.0 (defined as identical)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _similarity_or_none(a_tokens: set, b_tokens: set) -> float | None:
    """Like jaccard, but returns None when both sides are empty.

    None is a signal to the decision tree: 'no evidence either way',
    which is distinct from 'evidence of dissimilarity' (0.0).
    """
    if not a_tokens and not b_tokens:
        return None
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def _nonempty_match(a: Any, b: Any) -> bool:
    na, nb = normalize_identifier(a), normalize_identifier(b)
    return bool(na) and na == nb


def classify_pair(a: dict, b: dict) -> dict:
    """Classify a pair of vendor records.

    Returns a dict with keys: label, score, action, signals.
    Labels: EXACT_DUPLICATE | LIKELY_DUPLICATE | REVIEW_REQUIRED | DISTINCT
    Actions: MERGE | REVIEW | KEEP_SEPARATE
    """
    if not isinstance(a, dict) or not isinstance(b, dict):
        raise TypeError("classify_pair expects two dicts")

    name_sim = _similarity_or_none(name_tokens(a.get("name")), name_tokens(b.get("name")))
    addr_sim = _similarity_or_none(address_tokens(a.get("address")), address_tokens(b.get("address")))
    tax_match = _nonempty_match(a.get("tax_id"), b.get("tax_id"))
    bank_match = _nonempty_match(a.get("bank_account"), b.get("bank_account"))

    name_v = 0.0 if name_sim is None else name_sim
    addr_v = 0.0 if addr_sim is None else addr_sim

    if tax_match and (name_v >= 0.4 or addr_v >= 0.4 or bank_match):
        label, score, action = "EXACT_DUPLICATE", 0.97, "MERGE"
    elif tax_match:
        label, score, action = "LIKELY_DUPLICATE", 0.82, "MERGE"
    elif name_sim is not None and name_sim >= 0.9 and (addr_sim is None or addr_sim >= 0.5):
        label, score, action = "EXACT_DUPLICATE", 0.93, "MERGE"
    elif name_sim is not None and name_sim >= 0.8 and (addr_sim is None or addr_sim >= 0.4 or bank_match):
        label, score, action = "LIKELY_DUPLICATE", 0.78, "MERGE"
    elif (
        (name_sim is not None and name_sim >= 0.6)
        or (name_sim is not None and name_sim >= 0.5 and addr_sim is not None and addr_sim >= 0.5)
        or bank_match
    ):
        label, score, action = "REVIEW_REQUIRED", 0.60, "REVIEW"
    else:
        label = "DISTINCT"
        score = round(0.5 * name_v + 0.3 * addr_v, 4)
        action = "KEEP_SEPARATE"

    return {
        "label": label,
        "score": score,
        "action": action,
        "signals": {
            "name_similarity": None if name_sim is None else round(name_sim, 4),
            "address_similarity": None if addr_sim is None else round(addr_sim, 4),
            "tax_id_match": tax_match,
            "bank_account_match": bank_match,
        },
    }


def deduplicate(vendors: list[dict]) -> dict:
    """Scan all pairs, return only non-DISTINCT pairs sorted by score desc."""
    if not isinstance(vendors, list):
        raise TypeError("vendors must be a list")

    pairs: list[dict] = []
    n = len(vendors)
    for i in range(n):
        for j in range(i + 1, n):
            result = classify_pair(vendors[i], vendors[j])
            if result["action"] == "KEEP_SEPARATE":
                continue
            pairs.append({
                "a_index": i,
                "b_index": j,
                "a_id": vendors[i].get("id"),
                "b_id": vendors[j].get("id"),
                "label": result["label"],
                "score": result["score"],
                "action": result["action"],
                "signals": result["signals"],
            })
    pairs.sort(key=lambda p: p["score"], reverse=True)

    return {
        "vendor_count": n,
        "pair_count": len(pairs),
        "pairs": pairs,
    }
