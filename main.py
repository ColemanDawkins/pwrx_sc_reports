"""
main.py
--------------------------------------------------------------------------------
PWRX Strength & Conditioning -- FastAPI Backend

Endpoints:
    GET  /health
    GET  /roster
    GET  /athlete_sessions?athlete=name
    GET  /athletes/search?q=name
    POST /athletes/create
    POST /athletes/create_from_import
    POST /backfill
    POST /ingest
    POST /generate_report
"""

import os
import io
import tempfile
import traceback

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="PWRX S&C Reports API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_TABLES = ["master_uid", "pushpress", "dari_motion", "armcare", "vald_performance", "inbody"]


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateAthleteRequest(BaseModel):
    first_name:   str
    last_name:    str
    dari_id:      Optional[str] = None
    armcare_id:   Optional[str] = None
    vald_id:      Optional[str] = None
    pushpress_id: Optional[str] = None


class CreateFromImportRequest(BaseModel):
    table:      str
    first_name: str
    last_name:  str


# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────

@app.get("/roster")
def roster():
    """Return all athletes with session counts per data source."""
    try:
        from sc_db import get_roster, get_unlinked_counts
        rows    = get_roster()
        unlinked = get_unlinked_counts()
        result  = []
        for r in rows:
            result.append({
                "master_uid":        str(r["master_uid"]),
                "full_name":         str(r["full_name"]),
                "dari_sessions":     int(r["dari_sessions"]    or 0),
                "vald_sessions":     int(r["vald_sessions"]    or 0),
                "armcare_sessions":  int(r["armcare_sessions"] or 0),
                "pushpress_records": int(r["pushpress_records"] or 0),
                "inbody_records":     int(r["inbody_records"]  or 0),
                "last_dari":         str(r["last_dari"])    if r["last_dari"]    else None,
                "last_vald":         str(r["last_vald"])    if r["last_vald"]    else None,
                "last_armcare":      str(r["last_armcare"]) if r["last_armcare"] else None,
                "last_inbody":       str(r["last_inbody"])  if r.get("last_inbody") else None,
            })
        return {"roster": result, "unlinked_counts": unlinked}
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

@app.get("/athletes/search")
def athlete_search(q: str = Query(..., min_length=2)):
    """Search athletes by partial name. Returns list of matches."""
    try:
        from sc_db import search_athletes
        results = search_athletes(q)
        return {"results": results}
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────

@app.post("/athletes/create")
def athlete_create(req: CreateAthleteRequest):
    """
    Create a new athlete in master_uid with an auto-generated PWRX ID.
    Returns created record or duplicate warning.
    """
    try:
        from sc_db import create_athlete
        result = create_athlete(
            first_name=req.first_name,
            last_name=req.last_name,
            dari_id=req.dari_id,
            armcare_id=req.armcare_id,
            vald_id=req.vald_id,
            pushpress_id=req.pushpress_id,
        )
        if result["status"] == "duplicate":
            return JSONResponse(result, status_code=409)
        return result
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────

@app.post("/athletes/create_from_import")
def athlete_create_from_import(req: CreateFromImportRequest):
    """
    Create a master_uid record for an athlete found during a file import,
    then immediately back-fill their rows in the source table.
    """
    try:
        from sc_db import create_athlete, backfill_links
        result = create_athlete(req.first_name, req.last_name)
        if result["status"] == "duplicate":
            return JSONResponse(result, status_code=409)
        # Back-fill this athlete's rows in the source table
        bf = backfill_links(table=req.table)
        result["rows_linked"] = bf.get(req.table, 0)
        return result
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────

@app.post("/backfill")
def backfill(table: Optional[str] = None):
    """
    Sweep source tables and link rows to master_uid by name matching.
    Pass ?table=dari_motion to run on one table only.
    """
    try:
        from sc_db import backfill_links
        results = backfill_links(table=table)
        total   = sum(results.values())
        return {"status": "ok", "linked": results, "total_linked": total}
    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)


# ─────────────────────────────────────────────────────────────────────────────

@app.post("/ingest")
async def ingest(
    file:  UploadFile = File(...),
    table: str        = Form(...),
):
    """Upload a CSV or XLSX file and ingest it into the specified table."""
    if table not in VALID_TABLES:
        return JSONResponse(
            {"error": f"Invalid table '{table}'. Must be one of: {VALID_TABLES}"},
            status_code=400
        )

    suffix   = ".xlsx" if file.filename.endswith((".xlsx", ".xls")) else ".csv"
    tmp_path = None

    try:
        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        from sc_db import ingest_file, get_unlinked_names
        result       = ingest_file(tmp_path, table, verbose=False)
        unlinked     = get_unlinked_names(table) if table != "master_uid" else []

        return {
            "status":          "success",
            "table":           table,
            "inserted":        int(result["inserted"]),
            "skipped":         int(result["skipped"]),
            "flagged":         int(result["flagged"]),
            "warnings":        result["warnings"],
            "unlinked_names":  unlinked,
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
    """Generate a self-contained HTML S&C report for the given athlete."""
    tmp_path = None
    try:
        from sc_db import load_athlete_data
        from generate_sc_report import render_report

        data     = load_athlete_data(athlete_name)
        out      = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
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


# ─────────────────────────────────────────────────────────────────────────────

@app.post("/sync_phones")
async def sync_phones(file: UploadFile = File(...)):
    """
    Accept a CSV with columns: name, phone
    Reconciles against pushpress table:
      - Names not found are logged
      - Missing phones are added
      - Mismatched phones are updated
    Returns a log of every change and every missing name.
    """
    suffix   = ".xlsx" if file.filename.endswith((".xlsx", ".xls")) else ".csv"
    tmp_path = None
    try:
        import pandas as pd
        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        if suffix == ".xlsx":
            df = pd.read_excel(tmp_path, dtype=str)
        else:
            df = pd.read_csv(tmp_path, dtype=str)

        df.columns = [c.strip().lower() for c in df.columns]
        if "name" not in df.columns or "phone" not in df.columns:
            return JSONResponse(
                {"error": "File must have columns: name, phone"},
                status_code=400
            )

        records = df[["name", "phone"]].fillna("").to_dict(orient="records")

        from sc_db import sync_inbody_phones
        log = sync_inbody_phones(records)

        return {
            "status":         "ok",
            "not_found_count":     len(log["not_found"]),
            "phone_added_count":   len(log["phone_added"]),
            "phone_updated_count": len(log["phone_updated"]),
            "not_found":     log["not_found"],
            "phone_added":   log["phone_added"],
            "phone_updated": log["phone_updated"],
        }

    except Exception as exc:
        traceback.print_exc()
        return JSONResponse({"error": str(exc)}, status_code=500)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
