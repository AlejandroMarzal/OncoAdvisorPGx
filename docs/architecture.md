# **OncoAdvisorPGx – Architecture Documentation**

## 1. Overview
- **Project Name**: OncoAdvisorPGx 1.0.0 
- **Purpose**: 
  Application designed as a proof of concept (MVP) to support precision medicine in oncology through pharmacogenomics. 
  It allows: 
  - Processing VCF files (single-sample or multi-sample, compressed or not). 
  - Comparing variants against pharmacogenomic rules stored in a SQLite database. 
  - Generating reproducible and auditable reports in JSON, TXT, and LOG formats. 

- **Scope**: 
  Project developed as part of a Master’s Thesis (VIU). 

---

## 2. System Context
The system receives as input: 
- Genomic files in VCF format. 
- A database with pharmacogenomic rules loaded from CSV. 

It produces as output: 
- Human-readable clinical reports (TXT). 
- Structured results for computational systems (JSON). 
- Traceability logs (LOG). 

Main users: 
- Researchers and clinicians interested in pharmacogenomic analysis. 

---

## 3. High-Level Architecture
The application is organized into three layers:

1. **Frontend** 
   - CLI (`cli.py`) 
   - GUI (`gui.py`) with Streamlit 

2. **Backend** 
   - REST API (`app.py`) with FastAPI 
   - Core/Engine: `core.py`, contains the main analysis logic 
   - `__init__.py`: exports key functions 
   - SQLite database with pharmacogenomic rules 

---

## 4. Components

### 4.1 Frontend
- **CLI**: runs analyses from the terminal with arguments (`--vcf`, `--batch_dir`, `--patient_prefix`). 
- **GUI**: Streamlit interface that allows file uploads, credential input, and downloading results (JSON and TXT). 

### 4.2 Backend
- Implemented with **FastAPI** in `app.py`. 
- Main endpoints: 
  - `/api/analyze`: process a VCF file. 
  - `/api/patients`: list patients. 
  - `/api/patients/{id}/pgx-json`: retrieve JSON. 
  - `/api/patients/{id}/pgx-summary`: retrieve TXT. 

### 4.3 Core Engine
- **Main functions in `core.py`**: 
  - `is_carrier()`, `load_rules_from_db()`, `process_multi_sample()`, `assemble_results()`, `write_outputs()`. 
- Handles VCF reading, rule comparison, and report generation. 

### 4.4 Database
- SQLite chosen for simplicity and portability. 
- Rules loaded from CSV using the `load_rules_into_db.py` script. 

---

## 5. Deployment
- **CLI and GUI**: executable locally or in cloud environments (e.g., AWS CloudShell). 
- **API**: executed with `uvicorn app:app --reload` on port 8000. 

---

## 6. Constraints
- Academic project, not validated with real clinical data. 
- Optimized for small or simulated VCFs. 
- Does not include haplotype detection, only SNPs. 

---

## 7. Future Work
- Expand support and validation with real clinical datasets. 
- Incorporate haplotype analysis. 
- Extend the API to expose logs and additional endpoints. 
- Facilitate deployment through containerization (Docker). 
