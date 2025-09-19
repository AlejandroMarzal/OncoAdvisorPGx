#!/usr/bin/env python3
"""
PGx Cancer App Backend using FastAPI and SQLite.

Provides a REST API for pharmacogenomics (PGx) analysis:
- Accepts VCF uploads and processes variants using PGx rules from SQLite.
- Stores results in both JSON/TXT files and the database.
- Offers endpoints to list patients and retrieve their results.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, RedirectResponse

from backend.engine.core import process_multi_sample, assemble_result, write_outputs

# ---------------------------------------------------------------------
# Helper: Get base directory (portable)
# ---------------------------------------------------------------------
def get_base_dir() -> Path:
    env_base = os.environ.get("PGX_BASE_DIR")
    if env_base:
        return Path(env_base).resolve()
    return Path(__file__).resolve().parents[2]
    

# ---------------------------------------------------------------------
# Global configuration
# ---------------------------------------------------------------------
API_KEY = os.environ.get("PGX_API_KEY", "devkey")  # Default key for development

BASE_DIR = get_base_dir()
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = BASE_DIR / "backend" / "db" / "pgx_app.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # Ensure db dir exists

app = FastAPI(title="OncoAdvisorPGx", version="1.0.0")


# ---------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------
def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variant_rsid TEXT,
        variant_coor TEXT,
        drug TEXT,
        gene TEXT,
        effect TEXT,
        level_of_evidence TEXT,
        clinical_guideline TEXT,
        recommendation TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT,
        variant TEXT,
        drug TEXT,
        effect TEXT,
        level_of_evidence TEXT,
        recommendation TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
    )
    """)

    conn.commit()
    conn.close()

init_db()


# ---------------------------------------------------------------------
# Authentication utilities
# ---------------------------------------------------------------------
def check_api_key(header_key: Optional[str]) -> None:
    if header_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ---------------------------------------------------------------------
# Rule loading utilities
# ---------------------------------------------------------------------
def load_rules_from_db() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT variant_rsid, variant_coor, drug, gene, effect, level_of_evidence, clinical_guideline, recommendation
        FROM rules
    """)
    rules = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rules


# ---------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


# ---------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------
@app.post("/api/analyze")
async def analyze_vcf(
    vcf: UploadFile = File(...),
    patient_prefix: str = Form(default=""),
    x_api_key_hdr: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> JSONResponse:
    check_api_key(x_api_key_hdr)

    suffix = "".join(Path(vcf.filename).suffixes) or ".vcf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(vcf.file, tmp)
        tmp_vcf = Path(tmp.name)

    try:
        rules_list = load_rules_from_db()
        if not rules_list:
            raise HTTPException(400, "No PGx rules found in database")

        # -----------------------------
        # Map rules to dictionary for core processing
        # -----------------------------
        rules_dict = {}
        for rule in rules_list:
            # First try variant_rsid
            if rule.get("variant_rsid"):
                rules_dict[rule["variant_rsid"]] = rule
            # If no rsid, fallback to variant_coor
            elif rule.get("variant_coor"):
                rules_dict[rule["variant_coor"]] = rule
        # -----------------------------

        per_sample = process_multi_sample(tmp_vcf, rules_dict)
        if not per_sample:
            return JSONResponse(content={
                "results": {},
                "note": "No sample columns found in VCF file."
            })

        results: dict[str, dict] = {}
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        for sample, obj in per_sample.items():
            patient_id = f"{patient_prefix}_{sample}" if patient_prefix else sample
            assembled = assemble_result(
                patient_id=patient_id,
                sample=sample,
                vcf_path=tmp_vcf,
                matches=obj["matches"],
                stats=obj["stats"],
                rules_meta={"source": "SQLite", "total_rules": len(rules_list)},
            )
            results[patient_id] = assembled

            cur.execute("INSERT OR IGNORE INTO patients (patient_id) VALUES (?)", (patient_id,))
            for match in obj["matches"]:
                cur.execute("""
                    INSERT INTO results (patient_id, variant, drug, effect, level_of_evidence, recommendation)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    patient_id,
                    match.get("variant"),
                    match.get("drug"),
                    match.get("effect"),
                    match.get("level_of_evidence"),
                    match.get("recommendation"),
                ))

        conn.commit()
        conn.close()
        write_outputs(RESULTS_DIR, results)
        return JSONResponse(content={"results": results})

    finally:
        try:
            tmp_vcf.unlink(missing_ok=True)
        except Exception:
            pass


@app.get("/api/patients")
def list_patients(x_api_key_hdr: Optional[str] = Header(default=None, alias="X-API-Key")) -> dict:
    check_api_key(x_api_key_hdr)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT patient_id, created_at FROM patients ORDER BY created_at DESC")
    patients = [{"id": row[0], "created_at": row[1]} for row in cur.fetchall()]
    conn.close()
    return {"patients": patients}


@app.get("/api/patients/{patient_id}/pgx-json")
def get_patient_json(patient_id: str, x_api_key_hdr: Optional[str] = Header(default=None, alias="X-API-Key")) -> FileResponse:
    check_api_key(x_api_key_hdr)
    json_file = RESULTS_DIR / "json" / f"{patient_id}.json" 
    if not json_file.is_file():
        raise HTTPException(404, "JSON analysis file not found")
    return FileResponse(json_file)

@app.get("/api/patients/{patient_id}/pgx-summary")
def get_patient_summary(patient_id: str, x_api_key_hdr: Optional[str] = Header(default=None, alias="X-API-Key")) -> PlainTextResponse:
    check_api_key(x_api_key_hdr)
    summary_file = RESULTS_DIR / "txt" / f"{patient_id}.txt"  
    if not summary_file.is_file():
        raise HTTPException(404, "Summary file not found")
    return PlainTextResponse(summary_file.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
