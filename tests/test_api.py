"""HTTP surface tests.

Author: Mourad.Soltani
"""


def test_classify_endpoint_happy(client):
    payload = {"a": {"name": "Acme Corp"}, "b": {"name": "Acme Corporation"}}
    r = client.post("/api/classify", json=payload)
    assert r.status_code == 200
    data = r.get_json()
    assert data["signature"] == "Mourad.Soltani"
    assert data["result"]["label"] == "EXACT_DUPLICATE"
    assert data["result"]["action"] == "MERGE"
    assert data["result"]["score"] == 0.93


def test_classify_endpoint_bad_json(client):
    r = client.post("/api/classify", data="not json", content_type="application/json")
    assert r.status_code == 400
    body = r.get_json()
    assert body["error"] == "invalid_json"
    assert body["signature"] == "Mourad.Soltani"


def test_classify_endpoint_bad_type(client):
    r = client.post("/api/classify", json={"a": "string", "b": {}})
    assert r.status_code == 400
    body = r.get_json()
    assert body["error"] == "invalid_payload"
    assert body["signature"] == "Mourad.Soltani"


def test_deduplicate_endpoint_happy(client):
    payload = {"vendors": [
        {"id": "V1", "name": "Acme Corp"},
        {"id": "V2", "name": "Acme Corporation"},
        {"id": "V3", "name": "Globex"},
    ]}
    r = client.post("/api/deduplicate", json=payload)
    assert r.status_code == 200
    body = r.get_json()
    assert body["signature"] == "Mourad.Soltani"
    result = body["result"]
    assert result["vendor_count"] == 3
    assert result["pair_count"] == 1
    assert result["pairs"][0]["a_id"] == "V1"
    assert result["pairs"][0]["b_id"] == "V2"
    assert result["pairs"][0]["label"] == "EXACT_DUPLICATE"


def test_deduplicate_endpoint_vendors_not_list(client):
    r = client.post("/api/deduplicate", json={"vendors": "no"})
    assert r.status_code == 400
    body = r.get_json()
    assert body["error"] == "invalid_payload"
    assert body["signature"] == "Mourad.Soltani"
