# Local Fintech Conference Intelligence (Frontend + Backend)

This is a local-only implementation of the same B2B fintech conference intelligence idea.
Both frontend and backend run from this repository using Flask and JSON persistence.

## What It Includes

- Public event browsing (`/`, `/events`, `/events/<slug>`)
- Local login/session auth (`/login`, `/logout`, `/me`)
- Attendance state + privacy controls (public, verified-only, private)
- Permission-aware attendee visibility and limits
- Admin event management with local forms:
  - Create event (`/admin/events/new`)
  - Edit event (`/admin/events/<slug>/edit`)
  - Delete event (`/admin/events/<slug>/delete`)
- Local JSON data store in `data/events.json`

## Seeded Local Users

All users use password `AUTH_CREDENTIALS_SEED_PASSWORD` (default `devpassword`).

- `admin@local.dev` (ADMIN)
- `alice@stripe.com` (verified domain)
- `bob@gmail.com` (free/unverified)
- `pro@local.dev` (PRO)

## Project Structure

- `src/` backend app and storage logic
- `templates/` server-rendered HTML
- `static/` CSS
- `data/events.json` local system-of-record data
- `tests/` pytest tests

## Setup

```bash
cd /Users/heatherlassiter/Desktop/project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

App URL: `http://127.0.0.1:5000`

## Run Tests

```bash
pytest
```

## Notes

- All data is local in this repo.
- No cloud services or external databases are required.
