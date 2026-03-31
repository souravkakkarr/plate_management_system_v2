# Plate Management App

A ready-to-run FastAPI web app for plate management with seeded demo data.

## What is included
- Role-based login
- Dashboard with rack visualization
- Plate Set Master creation
- Replacement Plate Master creation
- Show Record panel
- Usage Log panel
- Scrap request workflow
- Owner-only scrap approval
- Database control page for owner and technical team
- Seeded users, seeded locations, and dummy records

## Important implementation note
This version uses local email/password login for immediate use and testing. Google OAuth was part of the product plan, but it requires your own Google OAuth client credentials, so it is not hard-coded here. The app structure is ready for that upgrade later.

## Seeded demo users
- owner: `souravkakkar2k3@gmail.com` / `owner123`
- technical team: `souravkakkarr@gmail.com` / `tech123`
- designer: `Designer_of_company@gmail.com` / `designer123`
- plate manager: `Plate_manager_of_company@gmail.com` / `plate123`

## Tech stack
- FastAPI
- SQLAlchemy
- Jinja2 templates
- SQLite by default
- PostgreSQL-ready via `DATABASE_URL`

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open:
`http://127.0.0.1:8000`

## Database
By default the app uses:
- `sqlite:///./plate_management.db`

To use PostgreSQL later, set:
```bash
export DATABASE_URL=postgresql+psycopg2://user:password@host:5432/dbname
```

## Core business rules implemented
- Job ID is unique.
- Plate Set ID is unique.
- One location can hold one active plate set.
- First vacant location is auto-assigned.
- Location is non-editable in plate set creation.
- New plate set creation auto-creates an `IN` usage log entry.
- Replacement plate uses same location as plate set.
- Replacement plate does not affect movement logic.
- If no usage exists, the UI shows `No usage found` for usage summary fields.
- No deletion rights exist anywhere in the app.
- Scrapping is status-based.

## Folder structure
```text
app/
  main.py
  models.py
  database.py
  auth.py
  services.py
  templates/
  static/
requirements.txt
README.md
```
