#!/usr/bin/env python3
"""
OncoAdvisorPGx GUI Frontend using Streamlit.

Simple web interface for pharmacogenomic analysis:
- Upload VCF files for processing via the backend API.
- PGx rules are loaded from SQLite.
- Displays analysis results in a structured table format.
"""

from __future__ import annotations
import os
import streamlit as st
import requests
import pandas as pd
import json
from pathlib import Path

# ---------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------
st.set_page_config(page_title="OncoAdvisorPGx", layout="centered")
st.title("OncoAdvisorPGx")

st.markdown(
    "Upload a VCF/VCF.gz file for pharmacogenomic analysis. "
    "PGx rules are automatically loaded from the database."
)

# ---------------------------------------------------------------------
# Backend URL configuration
# ---------------------------------------------------------------------
backend_url = "http://localhost:8000/api/analyze"


# ---------------------------------------------------------------------
# Directories for auto-save
# ---------------------------------------------------------------------
BASE_DIR = Path(os.getcwd())
RESULTS_DIR = BASE_DIR / "results"
JSON_DIR = RESULTS_DIR / "json"
TXT_DIR = RESULTS_DIR / "txt"
JSON_DIR.mkdir(parents=True, exist_ok=True)
TXT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------
# User inputs
# ---------------------------------------------------------------------
api_key = st.text_input("API Key", value="", type="password")
patient_prefix = st.text_input(
    "Patient prefix (required)",
    value="",
    help="Prefix added to sample names for patient identification"
)
vcf_file = st.file_uploader(
    "Upload VCF/VCF.gz file",
    type=["vcf", "gz"],
    help="Select a VCF or compressed VCF.gz file containing genetic variants"
)

# ---------------------------------------------------------------------
# Run analysis
# ---------------------------------------------------------------------
if st.button("Analyze"):
    if not patient_prefix:
        st.error("Patient prefix is required. Please enter a value.")
        st.stop()  # Detiene ejecución hasta que se ingrese un valor
    if not vcf_file or not api_key:
        st.error("VCF file and API key are required.")
        st.stop()

    files = {"vcf": (vcf_file.name, vcf_file.getvalue())}
    data = {"patient_prefix": patient_prefix}
    headers = {"X-API-Key": api_key}

    with st.spinner("Processing analysis..."):
        try:
            response = requests.post(
                backend_url,
                files=files,
                data=data,
                headers=headers,
                timeout=300
            )
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")
            st.stop()

    if response.status_code != 200:
        st.error(f"API Error {response.status_code}: {response.text}")
    else:
        try:
            payload = response.json()
        except Exception:
            st.error(f"Backend did not return valid JSON. Raw response:\n\n{response.text[:500]}")
            st.stop()

        results = payload.get("results", {})
        rows = []
        for patient_id, result_obj in results.items():
            # Prepare table rows
            for match in result_obj.get("matches", []):
                rows.append({
                    "patient": patient_id,
                    "variant": match.get("variant", ""),
                    "gene": match.get("gene", ""),
                    "drug": match.get("drug", ""),
                    "effect": match.get("effect", ""),
                    "level_of_evidence": match.get("level_of_evidence", ""),
                    "recommendation": match.get("recommendation", ""),
                    "clinical_guideline": match.get("clinical_guideline", "")
                })


            # Auto-save JSON
            json_path = JSON_DIR / f"{patient_id}.json"
            with open(json_path, "w") as f:
                json.dump(result_obj, f, indent=2)

            # Auto-save TXT summary
            txt_path = TXT_DIR / f"{patient_id}.txt"
            with open(txt_path, "w") as f:
                f.write(f"Patient {patient_id} processed.\n")
                for match in result_obj.get("matches", []):
                    f.write(f"Variant: {match.get('variant','')} | Drug: {match.get('drug','')} | "
                            f"Effect: {match.get('effect','')} | Level: {match.get('level_of_evidence','')} | "
                            f"Recommendation: {match.get('recommendation','')}\n")
                f.write(f"\nJSON written to: {json_path}\nTXT written to: {txt_path}\n")

            # Download buttons
            st.download_button(f"Download JSON for {patient_id}", data=json.dumps(result_obj, indent=2),
                               file_name=f"{patient_id}.json", mime="application/json")
            st.download_button(f"Download TXT for {patient_id}", data=open(txt_path).read(),
                               file_name=f"{patient_id}.txt", mime="text/plain")

        if rows:
            df = pd.DataFrame(rows)
            st.success(f"Analysis completed. Total matches: {len(df)}")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No pharmacogenomic matches found for this patient.")

# ---------------------------------------------------------------------
# Info
# ---------------------------------------------------------------------
st.markdown("---")
st.markdown("Note: PGx rules are automatically loaded from the database. No CSV upload required.")
