#!/usr/bin/env python3
"""
OncoAdvisorPGx Backend using FastAPI and SQLite. Provides a REST API for
pharmacogenomics (PGx) analysis:
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

from backend.engine import load_rules_from_db, process_multi_sample, assemble_result, write_outputs

# ---------------------------------------------------------------------
# Global configuration
# ---------------------------------------------------------------------
# Set up password
API_KEY = "devkey"  # antes era API_KEY = os.environ.get("PGX_API_KEY", "devkey")

# Set up directories
BASE_DIR = Path.home() / "home_workspace"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = BASE_DIR / "backend" / "db" / "pgx_app.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Initialize FastAPI app
app = FastAPI(title="OncoAdvisorPGx", version="1.0.0")

# ---------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------
def init_db() -> None:
    """Initialize SQLite database with tables if they do not exist"""
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

    # Create the patients table if it does not exist
    cur.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create the results table if it does not exist
    cur.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT,
        variant_match TEXT,
        gene TEXT,
        drug TEXT,
        effect TEXT,
        level_of_evidence TEXT,
        clinical_guideline TEXT,
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
    x_api_key_hdr: Optional[str] = Header(default=None, alias="API-password"),
) -> JSONResponse:
    """ Analysis of VCF files and packaging into JSON/TXT/DB results """

    # Check password
    check_api_key(x_api_key_hdr)

    # Temporaly file
    suffix = "".join(Path(vcf.filename).suffixes) or ".vcf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(vcf.file, tmp)
        tmp_vcf = Path(tmp.name)

    try:
        # Load PGx rules from database
        rules_dict, rules_meta = load_rules_from_db(DB_PATH)

        # Verify if rules are available
        if not rules_dict:
            raise HTTPException(400, "No PGx rules found in database")

        # VCF process
        per_sample = process_multi_sample(tmp_vcf, rules_dict)
        if not per_sample:  # Verify if there are samples
            return JSONResponse(content={
                "results": {},
                "note": "No sample columns found in VCF file."
            })

        # Dictionary to store results per patient
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
                rules_meta=rules_meta,
            )
            results[patient_id] = assembled

            # Insert patient info if not already in the DB
            cur.execute("INSERT OR IGNORE INTO patients (patient_id) VALUES (?)", (patient_id,))

            # Insert each PGx match for this patient into the results table
            for match in obj["matches"]:
                cur.execute("""
                    INSERT INTO results (patient_id, variant_match, gene, drug,
                    effect, level_of_evidence, clinical_guideline, recommendation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    patient_id,
                    match.get("variant_match"),
                    match.get("gene"),
                    match.get("drug"),
                    match.get("effect"),
                    match.get("level_of_evidence"),
                    match.get("clinical_guideline"),
                    match.get("recommendation"),
                ))

        conn.commit()
        conn.close()
        write_outputs(results)
        return JSONResponse(content={"results": results})

    finally:
        # Clean up the temporary file even if there was an error
        try:
            tmp_vcf.unlink(missing_ok=True)
        except Exception:
            pass

@app.get("/api/patients")
def list_patients(x_api_key_hdr: Optional[str] = Header(default=None, alias="API-password")) -> dict:
    """ Retrieval of patient list """
    check_api_key(x_api_key_hdr)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT patient_id, created_at FROM patients ORDER BY created_at DESC")
    patients = [{"id": row[0], "created_at": f"{row[1]} UTC"} for row in cur.fetchall()]
    conn.close()
    return {"patients": patients}

@app.get("/api/patients/{patient_id}/pgx-json")
def get_patient_json(patient_id: str, x_api_key_hdr: Optional[str] = Header(default=None, alias="API-password")) -> FileResponse:
    """ Retrieval of pharmacogenetic analysis results in JSON format """
    check_api_key(x_api_key_hdr)
    json_file = RESULTS_DIR / "json" / f"{patient_id}.json"
    if not json_file.is_file():
        raise HTTPException(404, "JSON analysis file not found")
    return FileResponse(json_file)

@app.get("/api/patients/{patient_id}/pgx-summary")
def get_patient_summary(patient_id: str, x_api_key_hdr: Optional[str] = Header(default=None, alias="API-password")) -> PlainTextResponse:
    """ Retrieval of pharmacogenetic analysis results in TXT format """
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

