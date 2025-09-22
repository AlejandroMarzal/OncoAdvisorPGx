#!/usr/bin/env python3
"""
OncoAdvisorPGx GUI Frontend using Streamlit. Simple web interface for
pharmacogenomic analysis:
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
backend_url = "http://localhost:8000"
analyze_url = f"{backend_url}/api/analyze"


# ---------------------------------------------------------------------
# Directories for auto-save
# ---------------------------------------------------------------------
BASE_DIR = Path.home() / "home_workspace"
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
# Initial validations
if st.button("Analyze"):
    if not patient_prefix:
        st.error("Patient prefix is required. Please enter a value.")
        st.stop()  # Stops execution until some value is enetered
    if not vcf_file or not api_key:
        st.error("VCF file and API key are required.")
        st.stop()  # Stops execution until a VCF file and the correct API key are enetered

    # Prepare data to send to the backendd
    files = {"vcf": (vcf_file.name, vcf_file.getvalue())}
    data = {"patient_prefix": patient_prefix}
    headers = {"API-password": api_key}

    # Send HTTP request to backend with a spinner
    with st.spinner("Processing analysis..."):
        try:
            response = requests.post(
                analyze_url,
                files=files,
                data=data,
                headers=headers,
                timeout=300
            )
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")
            st.stop()

    # Check the response status
    if response.status_code != 200:
        st.error(f"API Error {response.status_code}: {response.text}")
    # Parse the JSON response
    else:
        try:
            payload = response.json()
        except Exception:
            st.error(f"Backend did not return valid JSON. Raw response:\n\n{response.text[:500]}")
            st.stop()

        # Build the results table
        results = payload.get("results", {})
        rows = []
        for patient_id, result_obj in results.items():
            # Prepare table rows
            for match in result_obj.get("matches", []):
                rows.append({
                    "patient": patient_id,
                    "Variant match": match.get("variant_match", ""),
                    "rsID": match.get("variant_rsid", ""),
                    "Genomic coordinate": match.get("variant_coor", ""),
                    "Gene": match.get("gene", ""),
                    "Drug": match.get("drug", ""),
                    "Effect": match.get("effect", ""),
                    "Level of evidence": match.get("level_of_evidence", ""),
                    "Clinical guideline": match.get("clinical_guideline", ""),
                    "Recommendation": match.get("recommendation", "")
                })

            # JSON request
            json_resp = requests.get(
                f"{backend_url}/api/patients/{patient_id}/pgx-json", 
                headers=headers
                )
            
            # TXT request
            txt_resp = requests.get(
                f"{backend_url}/api/patients/{patient_id}/pgx-summary",
                headers=headers
            )
            
            # Download buttons (JSON and TXT)
            st.download_button(
                f"Download JSON for {patient_id}",
                data=json_resp.content,
                file_name=f"{patient_id}.json",
                mime="application/json"
            )

            st.download_button(
                f"Download TXT for {patient_id}",
                data=txt_resp.text,
                file_name=f"{patient_id}.txt",
                mime="text/plain"
            )


        # Display the table in Streamlit
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
