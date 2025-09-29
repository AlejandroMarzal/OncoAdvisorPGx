#  **OncoAdvisorPGx — Load Rules Script**
User guide for the load_rules_into_db.py script. Explains the expected CSV format, required columns, handling of missing fields, and CLI options.

---

## 1. Recommended header (example)
```csv
variant_rsid,variant_coor,drug,gene,effect,level_of_evidence,clinical_guideline,recommendation
```

## 2. Required columns (header and per-row)
- **drug**
- **gene**
- **effect**
- **level_of_evidence**
- **recommendation**
- Additionally, each row must include at least one variant identifier: **variant_rsid** (internally mapped to variant) or **variant_coor** (internally mapped to locus). Both may coexist in the same row.

---

## 3. Handling missing vaules
- All required columns must have values. If any row is missing data in a required column, the load will fail.
- Each row must have at least one of `variant_rsid` or `variant_coor`. If both are missing, the load will fail.
- The script does not automatically interpret "NaN" as empty — if "NaN" is present, it will be stored literally in the database.

---

# 4. Technical requirements
-	Encoding: UTF-8 (use utf-8-sig if CSVs come from Excel).
-	Separator: comma (,). 
- Headers: normalized by lowercasing (Drug or DRUG -> drug)

---

# 5. Execution directory
Run the command from the project root directory (`home_workspace`). The script uses relative default paths (for example `backend/db/pgx_app.db`).

# 6. CLI / Options
The script will always replace the rules table in the database.
example usage:
```bash
python3 load_rules_into_db.py path/to/pgx_rules.csv
```
---

# 7. CSV examples
Minimal valid example:
```csv
variant_rsid,drug,gene,effect,level_of_evidence,clinical_guideline,recommendation
rs12345,DrugA,GENE1,Increased toxicity,Level 2,Guideline X,Reduce dose by 50%
```
Valid example with multiple variant identifiers:
```csv
variant_rsid,variant_coor,drug,gene,effect,level_of_evidence,clinical_guideline,recommendation
rs98765,chr1:12345,DrugB,GENE2,Reduced metabolism,Level 3,Guideline Y,Adjust dose
```

