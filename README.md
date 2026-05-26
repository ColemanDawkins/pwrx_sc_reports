# PWRX S&C Reports

Strength & Conditioning performance report platform. Separate from `pitchingwrx-reports` but built with the same stack.

## Stack

| Layer | Tool |
|---|---|
| Database | Supabase (PostgreSQL via psycopg2) |
| Backend API | FastAPI → Railway |
| Frontend | Streamlit → Streamlit Cloud |
| Reports | matplotlib + jinja2 → self-contained HTML |

## File structure

```
sc-reports/
├── sc_db.py                # database layer (mirrors pwrx_db.py)
├── main.py                 # FastAPI endpoints
├── generate_sc_report.py   # HTML report renderer
├── streamlit_app.py        # Streamlit UI
├── requirements.txt        # Railway / FastAPI deps
├── streamlit_requirements.txt
├── Procfile                # Railway start command
└── README.md
```

## Local dev

```bash
# 1. Set DB connection
export DATABASE_URL=postgres://postgres:[password]@db.[ref].supabase.co:5432/postgres

# 2. Create tables
python sc_db.py --init

# 3. Run API
uvicorn main:app --reload --port 8000

# 4. Run Streamlit (separate terminal)
streamlit run streamlit_app.py
```

Before running Streamlit locally, update `API_URL` at the top of `streamlit_app.py` to `http://localhost:8000`.

## Upload order

Always upload in this order:
1. `master_uid` — seeds the athlete identity table (use `master_uid_clean.csv`)
2. Any dataset: `dari_motion`, `vald_performance`, `armcare`, `pushpress`

## Deployment

**Backend (Railway):**
1. Connect GitHub repo to Railway
2. Set `DATABASE_URL` environment variable
3. Railway auto-deploys from `Procfile`

**Frontend (Streamlit Cloud):**
1. Connect GitHub repo at share.streamlit.io
2. Main file: `streamlit_app.py`
3. Requirements file: `streamlit_requirements.txt`
4. Update `API_URL` in `streamlit_app.py` to your Railway URL, then push

## Adding a new data source

1. Add the table schema to the `SCHEMA` string in `sc_db.py`
2. Add column aliases to `COLUMN_ALIASES`
3. Add the table name + columns to `TABLE_COLUMNS` and `TABLE_UNIQUE_KEY`
4. Add the source to `source_options` in `streamlit_app.py`
5. Add a fetch query in `load_athlete_data()` and map to the report DATA dict
