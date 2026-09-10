"""Pure-logic tests for the matching engine.

Author: Mourad.Soltani
"""

import pytest

from backend.vendor_matcher import (
    address_tokens,
    classify_pair,
    deduplicate,
    jaccard,
    name_tokens,
    normalize_identifier,
    normalize_name,
)


# --- Normalization -----------------------------------------------------------

def test_normalize_name_strips_legal_suffixes():
    assert normalize_name("Acme Corp") == "acme"


def test_normalize_name_multiple_suffixes():
    assert normalize_name("Foo Bar Inc") == "foo bar"


def test_normalize_name_empty():
    assert normalize_name("") == ""


def test_normalize_name_non_string():
    assert normalize_name(None) == ""


def test_normalize_identifier_strips_punctuation():
    assert normalize_identifier("12-345 6789") == "123456789"


def test_name_tokens_basic():
    assert name_tokens("Acme Widgets Inc") == {"acme", "widgets"}


# --- Jaccard -----------------------------------------------------------------

def test_jaccard_identical():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_empty_both():
    assert jaccard(set(), set()) == 1.0


def test_jaccard_partial():
    assert jaccard({"a", "b"}, {"a", "c"}) == pytest.approx(1 / 3)


# --- Classification ----------------------------------------------------------

def test_classify_exact_duplicate_via_name():
    a = {"name": "Acme Corp", "address": "", "tax_id": "", "bank_account": ""}
    b = {"name": "Acme Corporation", "address": "", "tax_id": "", "bank_account": ""}
    r = classify_pair(a, b)
    assert r["label"] == "EXACT_DUPLICATE"
    assert r["action"] == "MERGE"
    assert r["score"] == 0.93
    assert r["signals"]["name_similarity"] == 1.0
    assert r["signals"]["tax_id_match"] is False


def test_classify_exact_duplicate_via_tax_and_name():
    a = {"name": "Acme", "tax_id": "12-3456789"}
    b = {"name": "Acme Inc", "tax_id": "123456789"}
    r = classify_pair(a, b)
    assert r["label"] == "EXACT_DUPLICATE"
    assert r["action"] == "MERGE"
    assert r["score"] == 0.97
    assert r["signals"]["tax_id_match"] is True


def test_classify_likely_duplicate_via_tax_only():
    a = {"name": "Alpha", "tax_id": "12345"}
    b = {"name": "Beta", "tax_id": "12345"}
    r = classify_pair(a, b)
    assert r["label"] == "LIKELY_DUPLICATE"
    assert r["action"] == "MERGE"
    assert r["score"] == 0.82
    assert r["signals"]["name_similarity"] == 0.0


def test_classify_review_required():
    a = {"name": "Alpha Beta Gamma Delta"}
    b = {"name": "Alpha Beta Gamma Epsilon"}
    r = classify_pair(a, b)
    # 3 shared / 5 union = 0.6
    assert r["signals"]["name_similarity"] == 0.6
    assert r["label"] == "REVIEW_REQUIRED"
    assert r["action"] == "REVIEW"
    assert r["score"] == 0.60


def test_classify_distinct():
    a = {"name": "Alpha"}
    b = {"name": "Beta"}
    r = classify_pair(a, b)
    assert r["label"] == "DISTINCT"
    assert r["action"] == "KEEP_SEPARATE"
    assert r["score"] == 0.0


def test_classify_bank_account_triggers_review():
    a = {"name": "Foo", "bank_account": "12345"}
    b = {"name": "Bar", "bank_account": "12345"}
    r = classify_pair(a, b)
    assert r["signals"]["bank_account_match"] is True
    assert r["label"] == "REVIEW_REQUIRED"
    assert r["action"] == "REVIEW"


def test_classify_missing_tax_id_does_not_match():
    # Both tax ids empty -> tax_match MUST be False, not True.
    a = {"name": "Foo", "tax_id": ""}
    b = {"name": "Foo", "tax_id": ""}
    r = classify_pair(a, b)
    assert r["signals"]["tax_id_match"] is False
    # Name similarity alone still catches it.
    assert r["label"] == "EXACT_DUPLICATE"


def test_classify_signals_shape():
    a = {"name": "Acme Corp", "address": "1 Main St", "tax_id": "12-345", "bank_account": "999"}
    b = {"name": "Acme Corporation", "address": "1 Main Street", "tax_id": "12345", "bank_account": "999"}
    r = classify_pair(a, b)
    assert set(r["signals"].keys()) == {
        "name_similarity", "address_similarity", "tax_id_match", "bank_account_match"
    }
    assert r["signals"]["name_similarity"] == 1.0
    assert r["signals"]["address_similarity"] == 0.5
    assert r["signals"]["tax_id_match"] is True
    assert r["signals"]["bank_account_match"] is True
    assert r["label"] == "EXACT_DUPLICATE"


# --- Batch dedupe ------------------------------------------------------------

def test_deduplicate_sorted_by_score():
    vendors = [
        {"id": "V1", "name": "Acme Corp"},
        {"id": "V2", "name": "Acme Corporation"},
        {"id": "V3", "name": "Alpha Beta Gamma Delta"},
        {"id": "V4", "name": "Alpha Beta Gamma Epsilon"},
        {"id": "V5", "name": "Globex"},
    ]
    result = deduplicate(vendors)
    assert result["vendor_count"] == 5
    assert result["pair_count"] == 2
    assert result["pairs"][0]["score"] == 0.93
    assert result["pairs"][0]["a_id"] == "V1"
    assert result["pairs"][0]["b_id"] == "V2"
    assert result["pairs"][1]["score"] == 0.60
    assert result["pairs"][1]["a_id"] == "V3"
    assert result["pairs"][1]["b_id"] == "V4"
    # non-increasing score ordering
    assert result["pairs"][0]["score"] >= result["pairs"][1]["score"]


def test_deduplicate_filters_distinct():
    vendors = [
        {"id": "A", "name": "Alpha"},
        {"id": "B", "name": "Beta"},
        {"id": "C", "name": "Gamma"},
    ]
    result = deduplicate(vendors)
    assert result["vendor_count"] == 3
    assert result["pair_count"] == 0
    assert result["pairs"] == []


def test_deduplicate_invalid_input():
    with pytest.raises(TypeError):
        deduplicate("not a list")


def test_scores_within_range():
    probes = [
        ({"name": "Acme Corp"}, {"name": "Acme Corporation"}),
        ({"name": "A B C D"}, {"name": "A B C E"}),
        ({"name": "Alpha"}, {"name": "Beta"}),
        ({"name": "X", "tax_id": "1"}, {"name": "Y", "tax_id": "1"}),
    ]
    for a, b in probes:
        r = classify_pair(a, b)
        assert 0.0 <= r["score"] <= 1.0
