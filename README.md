# Vendor Master Data Cleanup

**Author: Mourad.Soltani** · Version 1.0.0 · MIT

A deterministic vendor master data deduplication and merge-recommendation
engine for mid-market finance ops and manufacturing teams.

## Why this exists

Vendor master data rots. Every 18 months a manufacturer or finance ops
team changes a supplier's legal name, tax registration, or bank account,
and the ERP ends up with three records for one entity. The cleanup is
manual, cross-system, and audit-sensitive — exactly the class of work
that cannot be safely delegated to a raw LLM because merge decisions
must be explainable to an auditor and reversible.

This engine does the deterministic part: it produces an explainable
match label, a confidence score, a recommended action, and the exact
signals that drove the decision. The human reviewer stays in the loop.

## What it is not

- Not an LLM wrapper. The decision tree is rule-based. Every score is
  reproducible byte-for-byte across runs. No external API calls.
- Not a SaaS. No auth, no billing, no persistence. Ships as a library
  and a small HTTP API for embedding into an existing ERP/AP pipeline.

## Decision tree (summary)

Signals computed per vendor pair:

| Signal | Source | Range |
|---|---|---|
| `name_similarity` | Jaccard over normalized name tokens (legal suffixes stripped) | 0.0–1.0 or `null` |
| `address_similarity` | Jaccard over normalized address tokens | 0.0–1.0 or `null` |
| `tax_id_match` | Exact match on normalized tax identifier (both non-empty) | bool |
| `bank_account_match` | Exact match on normalized bank account (both non-empty) | bool |

Rules, in priority order:

1. Tax id match **and** any of (name ≥ 0.4, address ≥ 0.4, bank match) → `EXACT_DUPLICATE` / 0.97 / `MERGE`
2. Tax id match alone → `LIKELY_DUPLICATE` / 0.82 / `MERGE`
3. Name ≥ 0.9 **and** (address is null **or** address ≥ 0.5) → `EXACT_DUPLICATE` / 0.93 / `MERGE`
4. Name ≥ 0.8 **and** (address is null **or** address ≥ 0.4 **or** bank match) → `LIKELY_DUPLICATE` / 0.78 / `MERGE`
5. Name ≥ 0.6 **or** (name ≥ 0.5 **and** address ≥ 0.5) **or** bank match → `REVIEW_REQUIRED` / 0.60 / `REVIEW`
6. Otherwise → `DISTINCT` / weighted score / `KEEP_SEPARATE`

`null` for a similarity signal means *both sides were empty* — no evidence
either way, treated as non-blocking. `0.0` means evidence of dissimilarity.

## Install

Requires Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Run locally

```bash
python run.py
```

Then in a browser: `http://localhost:5000/ui`

## API

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health` | Liveness + version + signature |
| GET  | `/` | Project metadata + endpoint index |
| POST | `/api/classify` | Compare two vendor records |
| POST | `/api/deduplicate` | Find all duplicate pairs in a list (≤ 500 records) |
| GET  | `/ui` | Static HTML front-end |

Every JSON response carries `signature: "Mourad.Soltani"`.

### Example — classify

```bash
curl -s -X POST http://localhost:5000/api/classify \
  -H 'Content-Type: application/json' \
  -d '{"a":{"name":"Acme Corp"},"b":{"name":"Acme Corporation"}}'
```

### Example — deduplicate

```bash
curl -s -X POST http://localhost:5000/api/deduplicate \
  -H 'Content-Type: application/json' \
  -d '{"vendors":[{"id":"V1","name":"Acme Corp"},{"id":"V2","name":"Acme Corporation"}]}'
```

## Tests

30 tests across health, pure logic, and HTTP endpoints.

```bash
pytest -v
```

## Docker

```bash
docker build -t vmd-cleanup .
docker run --rm -p 5000:5000 vmd-cleanup
```

The image ships a `HEALTHCHECK` that polls `/health`.

## Limits

- Pair scan is O(n²). 500 vendors per request cap.
- Name normalization is English/European legal suffixes only.
- No phonetic abbreviation resolution (Mfg ↔ Manufacturing is not
  treated as a match in v1). This is deliberate: buyers in AP would
  rather review a borderline pair than have the engine overreach.

## License

MIT — see LICENSE. Author: Mourad.Soltani.
