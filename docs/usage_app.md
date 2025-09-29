# **OncoAdvisorPGx – usage API**

The application’s API is built with FastAPI and provides a REST interface to connect the core logic (`engine`) with other systems or external integrations. 

---

## 1. Structure

The main file is:

`home_workspace/backend/api/app.py`

This file defines the FastAPI application and the available endpoints. 

The backend also contains:

- `backend/engine/core.py`: the core PGx logic.
- `backend/db/pgx_app.db`: the SQLite database storing rules and results.

---

## 2. Execution

To start the server:

```bash
uvicorn backend.api.app:app --reload
```

By default, it will be available at:

Application: http://localhost:8000
Interactive documentation (Swagger): http://localhost:8000/docs
Alternative documentation (ReDoc): http://localhost:8000/redoc

---

## 3. Main Endpoints

Currently implemented:

### 3.1 **`/api/analyze`**
- Method: `POST`
- Description: Performs the analysis of a VCF file against the loaded PGx rules.
- Input (multipart/form-data):
  - vcf: patient's VCF file (required).
  - patient_prefix: prefix for patient IDs (optional).

Example response (JSON):
```json
{
  "results": {
    "ONC001": {
      "matches": [
        {
          "variant": "rs1234",
          "gene": "CYP2D6",
          "drug": "tamoxifen",
          "effect": "Reduced metabolism",
          "level_of_evidence": "Level 2",
          "recommendation": "adjust dose"
        }
      ],
      "stats": {
        "total_variants": 5234,
        "with_gt": 5000,
        "without_gt": 234,
        "total_matches": 1
      }
    }
  }
}
```

### 3.2 **`/api/patients`**
- Method: `GET`
- Description: Returns the list of processed patients with their creation date.

### 3.3 **`/api/patients/{patient_id}/pgx-json`**
- Method: `GET`
- Description: Returns the patient’s analysis result in JSON format.

### 3.4 **`/api/patients/{patient_id}/pgx-summary`**
- Method: `GET`
- Description: Returns the patient’s report in plain text format.

---

## 4. Relationship with the rest of the system
The backend (app.py) calls the internal engine (core.py).
It offers the same functionality as the CLI and Streamlit app, but in REST API format.
This enables integration with: clinical services, external pipelines, or hospital platforms via standards.

---

## 5. Quick Test Example
Start the server:
```bash
uvicorn backend.api.app:app --reload
```

Open the Swagger interface in a browser:
http://localhost:8000/docs

Test the `/api/analyze` endpoint by uploading a file from `data/vcf_samples/example.vcf`.

---

## 6. Future Extensions
- Add a /health endpoint to quickly check backend status.
- Implement authentication and authorization.
- Enable direct integration with clinical standards (e.g. FHIR).
- Simplify deployment using Docker (docker-compose.yml).
