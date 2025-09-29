# **OncoAdvsiorPGX - Pharmacogenomics in Oncology**

## 1. Overview
OncoAdvisorPGx is a prototype pharmacogenomics application in oncology, designed as a **Minimum Viable Product (MVP)** for academic purposes.

It allows: 
- Processing patient genomic variants from VCF/VCF.gz files (single or multi-sample).
- Comparing variants with clinical pharmacogenomic (PGx) rules stored in an SQLite database.
- Generating auditable and reproducible reports in JSON, TXT, and LOG formats. 
- Accessing functionalities via **CLI**, **REST API**, and a **Streamlit-based web frontend**. 

## 2. Architecture
The project is organized into modular components (see [`architecture.md`](docs/architecture.md) for details): 

- `backend/` → REST API using FastAPI (`app.py`), SQLite database (`pgx_app.db`) 
- `frontend/` → CLI (`cli.py`) and web frontend (`gui.py` with Streamlit) 
- `pgx_core/` → Core analysis logic (`core.py`) 
- `data/` → Pharmacogenomic rules (CSV), SQLite DB, and example VCFs 
- `results/` → Generated outputs (JSON, TXT, LOG) 
- `scripts/` → Utilities such as `load_rules_into_db.py` 
- `docs/` → Documentation files: [`usage_cli.md`](docs/usage_cli.md), [`usage_app.md`](docs/usage_app.md), [`usage_api.md`](docs/usage_api.md), [`validation.md`](docs/validation.md) 

---

---

## 3. Installation
### 3.1 Clone the repository:

```bash
git clone https://github.com/AlejandroMarzal/OncoAdvisorPGx
cd home_workspace
```

### 3.2 Create a virtual environment and install dependencies (backend and frontend):

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
```

### 3.3 Load pharmacogenomic rules into the SQLite database:

By default, execute:

```bash
python3 scripts/load_rules_into_db.py data/rules/pgx_rules.csv
```
**NOTE:** The first argument is always the path to the script itself (`scripts/load_rules_into_db.py`).
The second argument is the path to the CSV file containing the pharmacogenomic rules you want to load. For more detailed see `docs/usage_load_rules.md`.

---

### 4. Usage Documentation

- Script to load PGx rules: [`docs/usage_load_rules.md`](docs/usage_load_rules.md)
- CLI: [`docs/usage_cli.md`](docs/usage_cli.md)
- Web frontend: [`docs/usage_gui.md`](docs/usage_gui.md)
- REST API: [`docs/usage_app.md`](docs/usage_app.md)
- Validation and examples: [`docs/validation.md`](docs/validation.md)

**Note:** For instructions on how to run the application, process VCF files, and generate results, please consult these documentation files. Detailed usage instructions are not included here to avoid redundancy.

---

## 5. Results Structure

- JSON: `results/json/result_<patient_id>.json`
- TXT summary: `results/reports/summary_<patient_id>.txt`
- CLI logs: `results/logs/pgx_cli.log`

---

## 6. Notes

- Project designed as an academic prototype/TFM; not for direct clinical use.
- Supports multi-sample VCFs and batch processing.
- Compatible with VCF and VCF.gz files.
- For detailed usage instructions, see: [`docs/usage_cli.md`](docs/usage_cli.md), [`docs/usage_app.md`](docs/usage_app.md), [`docs/usage_gui.md`](docs/usage_gui.md)

---

## 7. Contact

- **Author:** Alejandro Marzal García-Astillero
- **Email:** [amarzalgarciaastillero@student.universidadviu.com](mailto:amarzalgarciaastillero@student.universidadviu.com)
- **Tutor:** Pablo Marin García
- **University:** Valencian International University, Faculty of Health Science



