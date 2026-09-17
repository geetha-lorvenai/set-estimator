import uuid

SAMPLE = (
    "Build a moderate complexity living room set with 10 sheets of drywall, 20 litres of paint, "
    "30sqm of flooring, 2 scenic backdrops, and 2 days of carpenter and painter labor"
)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_catalog_exposes_pricing_rules(client):
    body = client.get("/catalog").json()
    assert body["materials"]["timber"]["unit_price"] == 50.0
    assert body["bulk_discount"]["threshold"] == 5000.0


def test_create_estimate_from_json(client):
    response = client.post("/estimates", json={"text": SAMPLE})
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["raw_input"] == SAMPLE
    assert body["set_name"] == "Living Room"
    assert body["complexity"] == "moderate"
    assert [m["material"] for m in body["materials"]] == ["drywall", "paint", "flooring", "scenic_backdrop"]
    assert {line["role"]: line["line_total"] for line in body["labor"]} == {"carpenter": 360.0, "painter": 240.0}
    assert body["summary"] == {
        "material_cost": 3000.0,
        "complexity": "moderate",
        "complexity_surcharge_rate": 0.15,
        "complexity_surcharge": 450.0,
        "bulk_discount_threshold": 5000.0,
        "bulk_discount_rate": 0.08,
        "bulk_discount_applied": False,
        "bulk_discount": 0.0,
        "adjusted_material_cost": 3450.0,
        "labor_cost": 600.0,
        "total": 4050.0,
    }


def test_create_estimate_from_plain_text_body(client):
    response = client.post("/estimates", content=SAMPLE, headers={"Content-Type": "text/plain; charset=utf-8"})
    assert response.status_code == 201
    assert response.json()["summary"]["total"] == 4050.0


def test_bulk_discount_through_api(client):
    body = client.post("/estimates", json={"text": "complex set with 101 sheets of timber"}).json()
    assert body["summary"]["bulk_discount_applied"] is True
    assert body["summary"]["total"] == 6161.0


def test_get_estimate_round_trip(client):
    created = client.post("/estimates", json={"text": SAMPLE}).json()
    fetched = client.get(f"/estimates/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_get_missing_estimate_returns_404(client):
    response = client.get(f"/estimates/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_malformed_id_returns_422(client):
    assert client.get("/estimates/not-a-uuid").status_code == 422


def test_list_estimates_newest_first_with_pagination(client):
    ids = [client.post("/estimates", json={"text": f"{n} sheets of timber"}).json()["id"] for n in (1, 2, 3)]
    body = client.get("/estimates").json()
    assert body["total"] == 3
    assert [item["id"] for item in body["items"]] == list(reversed(ids))

    page = client.get("/estimates", params={"limit": 1, "offset": 1}).json()
    assert [item["id"] for item in page["items"]] == [ids[1]]
    assert (page["limit"], page["offset"]) == (1, 1)


def test_list_empty(client):
    assert client.get("/estimates").json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_rejects_bad_pagination(client):
    assert client.get("/estimates", params={"limit": 0}).status_code == 422
    assert client.get("/estimates", params={"limit": 500}).status_code == 422


def test_unparseable_request_returns_422_and_is_not_stored(client):
    response = client.post("/estimates", json={"text": "make it look amazing"})
    assert response.status_code == 422
    assert "No priceable" in response.json()["detail"]["message"]
    assert client.get("/estimates").json()["total"] == 0


def test_warnings_are_returned(client):
    body = client.post("/estimates", json={"text": "3 sheets of timber and 4 chandeliers"}).json()
    assert any("4 chandeliers" in w for w in body["warnings"])


def test_validation_errors(client):
    assert client.post("/estimates", json={}).status_code == 422
    assert client.post("/estimates", json={"text": "  "}).status_code == 422
    assert client.post("/estimates", json={"text": "x" * 2001}).status_code == 422
    assert client.post("/estimates", content="{bad json", headers={"Content-Type": "application/json"}).status_code == 422


def test_unsupported_media_type(client):
    response = client.post("/estimates", content=b"<x/>", headers={"Content-Type": "application/xml"})
    assert response.status_code == 415


def test_invalid_utf8_body(client):
    response = client.post("/estimates", content=b"\xff\xfe\xfa", headers={"Content-Type": "text/plain"})
    assert response.status_code == 400
