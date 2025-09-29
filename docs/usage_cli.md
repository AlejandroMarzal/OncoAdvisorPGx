# **OncoAdvisorPGx – Command Line Interface (CLI)**

The Command-Line Interface (CLI) is part of the OncoAdvisorPGx frontend. It allows running pharmacogenomic (PGx) analyses directly from the terminal, making it suitable for bioinformaticians or pipeline integration.

---

## 1. Execution

```bash
python3 -m frontend/cli.py [options]
```

## 2. Key Options

```bash
--vcf <path>
```
*Analyze a single VCF/VCF.gz file.


```bash
--batch_dir <dir>
```
*Analyze all VCF/VCF.gz files in a directory.


```bash
--patient_prefix <prefix>
```
*Prefix to prepend to sample IDs when in batch or multi-sample mode.

```bash
--verbose / -v
```
*Enable detailed logging output.

---

## 3. Usage Examples
Single VCF with default SQLite rules:
```bash
python3 -m frontend/cli.py --vcf data/vcf_samples/sample.vcf --patient_prefix ONC001
```
Batch Processing (multiple files):
```bash
python3 -m frontend/cli.py --batch_dir data/vcf_samples/ --patient_prefix BATCH_
```
---

## 4. Outputs

All output files are written to the results/ directory:

- **JSON report** → result_<patient>.json → Structured output, useful for programmatic consumption or APIs.

- **Text summary** → summary_<patient>.txt →
Human-readable report for quick clinical review.

- **Logs** → logs/pgx_cli.log → Detailed execution log with timestamps and processing history.

---

## 5. Notes

- PGx rules should be loaded from data/db/pgx_app.db (SQLite database).
- Patient IDs will be derived from sample names unless overridden with  --patient_prefix.

