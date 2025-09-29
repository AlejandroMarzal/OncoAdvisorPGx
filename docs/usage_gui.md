# **OncoAdvisorPGx – Web Interface (Streamlit)**

The Streamlit-based web interface is part of the PGx Cancer App frontend. It is designed for clinicians and non-technical users, providing a simple way to upload VCF files and review pharmacogenomic analysis results.

---

## 1. Execution

The system requires two processes: backend (API) and frontend (Streamlit).

### **First: Start the backend (FastAPI)**

```bash
uvicorn backend.api.app:app --reload
```

This launches the API service at http://localhost:8000.

### **Second: Start the frontend (Streamlit)**
```bash
streamlit run frontend/gui.py --server.enableCORS false
```

This launches the web interface in your browser (default: http://localhost:8501).

---

## 2. Usage

1. Enter your API Key (default: **devkey**).
2. Obligatory provide a patient prefix (e.g. ONC_).
3. Upload a genetic data file (VCF or VCF.gz).
4. Click Analyze to run the PGx analysis.

---

## 3. Results

Analysis results are displayed in a table (interactive dataframe).
Each row represents a pharmacogenomic match (variant → drug → effect).
You can download TXT and JSON file per patient.

---

## 4. Columns include:

- **patient**
- **variant**
- **drug**
- **gene**
- **effect**
- **level_of_evidence**
- **clinical_guideline**
- **recommendation**

If no rules match, a warning message will appear.

---

## 5. Backend Outputs

Even though clinicians use the web UI, the backend generates structured results that can be reused by other systems:

- JSON objects containing analysis metadata and matches.
- Optional summary text reports (if used in batch/CLI mode).

---

## 6. Notes
- PGx rules are automatically loaded from the SQLite database (data/db/pgx_app.db).
- No CSV upload is required for clinicians.
- A working backend connection is required; the Streamlit frontend alone will not function.

