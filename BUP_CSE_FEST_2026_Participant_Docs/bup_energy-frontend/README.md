# BUP Energy — Frontend

React + Vite (JavaScript) dashboard for the BUP Energy optimizer. It POSTs
JSON to Django's `POST /optimize-energy` and renders the 24-hour plan,
summary stats, and the parsed operator directives.

The Django backend is **not modified** — development cross-origin is
sidestepped by Vite's dev-server proxy (`/api` → `http://localhost:8000`).

## Run

In two terminals, from the repo root:

```powershell
# 1) Django (already on your machine, leave it running)
python manage.py runserver

# 2) React dev server
cd bup_energy-frontend
npm install
npm run dev
```

Open the printed Vite URL (default `http://localhost:5173`).

## How the request is shaped

`src/api/optimize.js` posts this JSON to `/api/optimize-energy` (the
`/api` prefix is rewritten away by `vite.config.js`):

```json
{
  "scenario_id": "demo-scenario-01",
  "hours": [
    { "demand_kwh": 0, "solar_kwh": 0, "tariff_bdt_per_kwh": 12 },
    "…23 more…"
  ],
  "battery": {
    "capacity_kwh": 100,
    "initial_energy_kwh": 50,
    "minimum_energy_kwh": 0,
    "max_charge_kwh_per_hour": 25,
    "max_discharge_kwh_per_hour": 25
  },
  "operator_notes": [
    "reduce solar to 50% between 10am and 2pm"
  ]
}
```

The backend response (`server`, `directive_interpretation`, `hourly_plan`,
`summary`) drives the right-hand panel.

## Smoke test (no UI)

```powershell
curl -X POST http://localhost:8000/optimize-energy `
  -H "Content-Type: application/json" `
  -d '{"scenario_id":"smoke","hours":[],"battery":{},"operator_notes":[]}'
```

Expect HTTP 200 with a populated `hourly_plan` (24 rows, all defaulted).
