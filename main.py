"""
main.py
--------------------------------------------------------------------------------
PWRX Strength & Conditioning -- FastAPI Backend

Mirrors the structure of pitchingwrx-reports/main.py.
Deploys to Railway via Procfile: web: uvicorn main:app --host 0.0.0.0 --port $PORT

Endpoints:
    GET  /health
    GET  /roster
    GET  /athlete_sessions?athlete=name
    POST /ingest          -- upload CSV/XLSX for any data source
    POST /generate_report -- athlete name -> HTML report (streamed)
"""

import os
import io
import tempfile
import traceback

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI(title="PWRX S&C Reports API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_TABLES = ["master_uid", "pushpress", "dari_motion", "armcare", "vald_performance"]


# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────

@app.get("/roster")
def roster():
    """Return all athletes with session counts per data source."""
    try:
        from sc_db import get_roster
        rows = get_roster()
        result = []
        for r in rows:
            result.append({
                "master_uid":        str(r["master_uid"]),
                "full_name":         str(r["full_name"]),
                "dari_sessions":     int(r["dari_sessions"]   or 0),
                "vald_sessions":     int(r["vald_sessions"]   or 0),
                "armcare_sessions":  int(r["armcare_sessions"] or 0),
                "pushpress_records": int(r["pushpress_records"] or 0),
                "last_dari":         str(r["last_dari"])   if r["last_dari"]   else None,
                "last_vald":         str(r["last_vald"])   if r["last_vald"]   else None,
                "last_armcare":      str(r["last_armcare"]) if r["last_armcare"] else None,
            })
        return {"roster": result}
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────

@app.get("/athlete_sessions")
def athlete_sessions(athlete: str):
    """Return session counts + latest dates for one athlete."""
    try:
        from sc_db import load_athlete_data
        data = load_athlete_data(athlete)
        return {
            "athlete_name":  data["athlete_name"],
            "master_uid":    data["master_uid"],
            "data_coverage": data["data_coverage"],
        }
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────

@app.post("/ingest")
async def ingest(
    file:  UploadFile = File(...),
    table: str        = Form(...),
):
    """
    Upload a CSV or XLSX file and ingest it into the specified table.
    table must be one of: master_uid | pushpress | dari_motion | armcare | vald_performance
    """
    if table not in VALID_TABLES:
        return JSONResponse(
            {"error": f"Invalid table '{table}'. Must be one of: {VALID_TABLES}"},
            status_code=400
        )

    suffix = ".xlsx" if file.filename.endswith((".xlsx", ".xls")) else ".csv"
    tmp_path = None

    try:
        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        from sc_db import ingest_file
        result = ingest_file(tmp_path, table, verbose=False)

        return {
            "status":   "success",
            "table":    table,
            "inserted": int(result["inserted"]),
            "skipped":  int(result["skipped"]),
            "flagged":  int(result["flagged"]),
            "warnings": result["warnings"],
        }

    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────────────────────

@app.post("/generate_report")
async def generate_report(athlete_name: str = Form(...)):
    """
    Generate a self-contained HTML S&C report for the given athlete.
    Returns the HTML file as a download (same pattern as /generate in pitching app).
    """
    tmp_path = None
    try:
        from sc_db import load_athlete_data
        from generate_sc_report import render_report

        data = load_athlete_data(athlete_name)

        out = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
        out.close()
        tmp_path = out.name

        render_report(data, tmp_path)

        with open(tmp_path, "rb") as f:
            html_bytes = f.read()

        safe_name = athlete_name.replace(" ", "_")
        return StreamingResponse(
            io.BytesIO(html_bytes),
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}_sc_report.html"'},
        )

    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
