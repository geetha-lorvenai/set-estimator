# Set Construction Estimator

A backend service (FastAPI) that turns a plain-English set construction request into a structured,
costed estimate, stores it in a database, and serves it over a REST API. Includes a Next.js UI.

**Parsing and computation are 100% rule-based.** No LLM or external API is called anywhere.

```
POST /estimates   "Build a moderate complexity living room set with 10 sheets of drywall, ..."
  -> parse (regex rules) -> price (catalogue rules) -> save (SQLite/PostgreSQL) -> JSON estimate
```

## What's included

| Requirement | Where |
|---|---|
| `POST /estimates`, `GET /estimates/{id}`, `GET /estimates` | `backend/app/api/routes.py` |
| Material, labor, surcharge, bulk discount, breakdown (rule-based) | `backend/app/calculator.py` |
| Plain-English parsing (rule-based) | `backend/app/parser.py` |
| Unit tests (78) | `backend/tests/` |
| Bonus 1: database persistence (raw input + structured output) | `backend/app/db.py` (SQLite default, PostgreSQL via `DATABASE_URL`) |
| Bonus 2: Next.js UI | `frontend/` |
| Claude chat export | `chat-history/` |

## Run locally

Prerequisites: Python 3.10+ and Node.js 18.18+ (for the UI).

### 1. Backend (port 8000)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

That's it. It uses a local SQLite file (`backend/estimates.db`), created automatically.
Interactive API docs: http://localhost:8000/docs

**Use PostgreSQL instead** (optional):

```bash
docker run -d --name estimator-db -p 5432:5432 \
  -e POSTGRES_USER=estimator -e POSTGRES_PASSWORD=estimator -e POSTGRES_DB=estimator postgres:16-alpine
export DATABASE_URL=postgresql://estimator:estimator@localhost:5432/estimator   # Windows: set DATABASE_URL=...
uvicorn app.main:app --port 8000
```

The table is created on startup.

### 2. Run the tests

```bash
cd backend
pytest
```

### 3. Frontend (port 3000)

In a second terminal, with the backend running:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. To point at a different API, set `NEXT_PUBLIC_API_URL` (see `frontend/.env.example`).

### Whole stack with Docker (optional)

```bash
docker compose up --build
```

UI on :3000, API on :8000, PostgreSQL on :5432.

## API

### `POST /estimates`

Accepts either JSON or a raw plain-text body:

```bash
curl -X POST http://localhost:8000/estimates \
  -H "Content-Type: application/json" \
  -d '{"text": "Build a moderate complexity living room set with 10 sheets of drywall, 20 litres of paint, 30sqm of flooring, 2 scenic backdrops, and 2 days of carpenter and painter labor"}'

curl -X POST http://localhost:8000/estimates -H "Content-Type: text/plain" \
  --data "Complex kitchen set, drywall x 12, 2 carpenters for 3 days"
```

Response `201` (abridged):

```json
{
  "id": "c093910f-...",
  "created_at": "2026-09-17T06:48:03Z",
  "raw_input": "Build a moderate complexity living room set ...",
  "set_name": "Living Room",
  "complexity": "moderate",
  "complexity_detected": true,
  "materials": [
    {"material": "drywall", "category": "structural", "unit": "per_sheet", "quantity": 10, "unit_price": 30, "line_total": 300},
    {"material": "paint", "category": "finish", "unit": "per_litre", "quantity": 20, "unit_price": 25, "line_total": 500},
    {"material": "flooring", "category": "finish", "unit": "per_sqm", "quantity": 30, "unit_price": 60, "line_total": 1800},
    {"material": "scenic_backdrop", "category": "scenic", "unit": "per_panel", "quantity": 2, "unit_price": 200, "line_total": 400}
  ],
  "labor": [
    {"role": "carpenter", "workers": 1, "days": 2, "person_days": 2, "daily_rate": 180, "line_total": 360},
    {"role": "painter", "workers": 1, "days": 2, "person_days": 2, "daily_rate": 120, "line_total": 240}
  ],
  "material_cost_by_category": {"structural": 300, "finish": 2300, "scenic": 400},
  "labor_cost_by_role": {"carpenter": 360, "painter": 240},
  "summary": {
    "material_cost": 3000, "complexity": "moderate",
    "complexity_surcharge_rate": 0.15, "complexity_surcharge": 450,
    "bulk_discount_threshold": 5000, "bulk_discount_rate": 0.08,
    "bulk_discount_applied": false, "bulk_discount": 0,
    "adjusted_material_cost": 3450, "labor_cost": 600, "total": 4050
  },
  "warnings": []
}
```

Errors: `422` if nothing priceable was found (with the parser's warnings) or the input is invalid
(empty, over 2000 characters), `415` for other content types, `400` for non-UTF-8 bodies.
Requests that cannot be priced are not saved.

### `GET /estimates/{estimate_id}`
Returns one saved estimate. `404` if it does not exist, `422` if the id is not a UUID.

### `GET /estimates?limit=50&offset=0`
Returns `{items, total, limit, offset}`, newest first. `limit` is 1–200.

### Extras
`GET /health` and `GET /catalog` (the pricing rules in use).

## Pricing rules

All values come from `backend/app/catalog.py` (copied verbatim from the brief).

```
material_cost      = Σ quantity × unit_price
labor_cost         = Σ workers × days × daily_rate
surcharge          = material_cost × complexity rate          (0 / 15% / 30%)
bulk_discount      = material_cost × 8%   only if material_cost > 5000
total              = material_cost + surcharge − bulk_discount + labor_cost
```

Assumptions, stated so they can be checked:

- The surcharge and the discount are both calculated on the **undiscounted material cost**, so their order doesn't matter. Neither applies to labor.
- "Exceeds" means strictly greater: exactly 5000.00 gets no discount.
- If no complexity is stated, `simple` is used and a warning says so.
- Money uses `Decimal`, rounded half-up to cents. No currency is assumed.
- Sheets, rolls, points, panels and pieces are whole units: `2.5 backdrops` is rounded up to 3, with a warning.

Worked check (sample input): materials 3000 + surcharge 450 − discount 0 + labor 600 = **4050.00**.

## How parsing handles different wording

`backend/app/parser.py`, deterministic, no LLM:

1. **Normalise:** lower-case; number words to digits (`twenty five`, `a dozen`, `a couple of`, `half a day`);
   units unified (`sq m`, `m2`, `square metres` → sqm; `L`, `liters` → litres); `1,200` → 1200; `30sqm` → `30 sqm`.
2. **Labor**, in several phrasings:
   `2 days of carpenter and painter labor` · `2 carpenters for 3 days` · `a carpenter and 2 painters for 4 days` ·
   `3 painter days` · `electrician: 1 day` · `scenic artist x 2 days`.
   Roles listed without their own days use an overall duration (`Crew: carpenter, painter. Build over 3 days.`).
   Synonyms: carpentry/joiner, painting, gaffer/sparks, scenic painter.
3. **Materials:** the quantity is taken right before the item (`10 sheets of drywall`) or right after it
   (`drywall x 10`, `paint: 20L`), never across a comma/"and"/another item, so numbers can't leak between items.
   Synonyms: plywood/MDF → timber, plasterboard/sheetrock → drywall, carpet/laminate → flooring,
   power points/outlets/sockets → electrical fit, backcloth/cyclorama → scenic backdrop, props/furniture → prop furniture.
4. **Complexity:** `moderate complexity`, `moderately complex`, `high complexity`, `complexity: simple`, `elaborate`, etc.
5. **Set name:** the words before "set" (`western saloon set` → "Western Saloon").
6. **Nothing is dropped silently.** Unknown items (`5 chandeliers`), items with no quantity, crew with no days,
   unit mismatches (`10 rolls of drywall`), rounding and merged duplicate roles all come back in `warnings`.

## Project layout

```
backend/
  app/
    catalog.py       pricing constants from the brief
    parser.py        plain English -> items (rules)
    calculator.py    items -> costs (rules, Decimal)
    service.py       parse -> calculate -> persist
    repository.py    database access
    db.py            SQLAlchemy model + engine (SQLite / PostgreSQL)
    schemas.py       API request/response models
    api/routes.py    HTTP endpoints
    main.py          app factory, CORS, error handlers
    config.py        environment settings
  tests/             parser, calculator and API tests
frontend/            Next.js 15 (App Router) UI
docker-compose.yml   optional full stack with PostgreSQL
chat-history/        Claude chat export
```

## Configuration

| Variable | Default | |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./estimates.db` | `postgresql://user:pass@host:5432/db` also works |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | comma-separated |
| `LOG_LEVEL` | `INFO` | |
| `MAX_INPUT_CHARS` | `2000` | |
| `NEXT_PUBLIC_API_URL` (frontend) | `http://localhost:8000` | |

## Next steps for production

Alembic migrations instead of `create_all`, authentication, rate limiting, and moving the catalogue into the
database so rates can change without a deploy.
