#!/usr/bin/env python3
"""
Command-line interface (CLI) for pharmacogenomic (PGx) analysis.

This CLI is part of the OncoAdvisorPGx frontend, providing a command-line
interface for bioinformaticians and pipeline integration.

Features:
- Supports single or batch VCF processing (multi-sample enabled).
- Loads PGx rules from SQLite by default, or optionally from CSV.
- Requires patient prefix for multi-sample/batch mode.
- Logs activity per patient (one log file per patient).
- Writes outputs in JSON/TXT using core.write_outputs.
"""

from __future__ import annotations
import argparse
import logging
import sqlite3
import os
import sys
from pathlib import Path
from typing import Dict, Tuple

# Add backend engine to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "engine"))
from core import load_rules, process_multi_sample, assemble_result, write_outputs

# ---------------------------------------------------------------------
# Helper: Get base directory (portable)
# ---------------------------------------------------------------------
def get_base_dir() -> Path:
    env_base = os.environ.get("PGX_BASE_DIR")
    if env_base:
        return Path(env_base).resolve()
    return Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------
# Global settings (paths)
# ---------------------------------------------------------------------
BASE_DIR = get_base_dir()
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = RESULTS_DIR / "logs"
DB_PATH = BASE_DIR / "backend" / "db" / "pgx_app.db"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Root logger (console only)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
root_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------
# Per-patient logger
# ---------------------------------------------------------------------
def get_patient_logger(patient_id: str) -> logging.Logger:
    """Return a logger that writes to results/logs/{patient_id}.log"""
    log_path = LOGS_DIR / f"{patient_id}.log"
    logger = logging.getLogger(f"pgx.{patient_id}")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_path)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
        # Optional: also stream to console
        logger.addHandler(logging.StreamHandler())
    return logger

# ---------------------------------------------------------------------
# Load rules from SQLite
# ---------------------------------------------------------------------
def load_rules_from_db() -> Tuple[Dict[str, dict], dict]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found: {DB_PATH}")

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(rules)")
        available_columns = [col[1] for col in cur.fetchall()]

        base_columns = ["variant_rsid", "drug", "effect"]
        optional_columns = ["level_of_evidence", "recommendation", "variant_coor", "gene", "clinical_guideline"]

        select_columns = [col for col in base_columns + optional_columns if col in available_columns]
        query = f"SELECT {', '.join(select_columns)} FROM rules"
        cur.execute(query)
        rules_list = [dict(row) for row in cur.fetchall()]
        conn.close()

        if not rules_list:
            raise ValueError("No PGx rules found in database")

        rules_dict = {}
        for rule in rules_list:
            key = rule.get("variant_rsid") or rule.get("variant_coor")
            if key:
                rules_dict[key] = rule

        meta = {
            "source": "SQLite",
            "db_path": str(DB_PATH),
            "total_rules": len(rules_list),
            "columns_detected": select_columns,
        }

        root_logger.info("Loaded %d rules from SQLite database", len(rules_dict))
        return rules_dict, meta

    except Exception as e:
        root_logger.error("Error loading rules from database: %s", e)
        raise

# ---------------------------------------------------------------------
# Process VCF(s) and write outputs
# ---------------------------------------------------------------------
def process_and_write(vcf_path: Path, prefix: str, rules: dict, rules_meta: dict) -> None:
    if not vcf_path.is_file():
        root_logger.error("VCF not found: %s", vcf_path)
        raise FileNotFoundError(f"VCF file not found: {vcf_path}")

    root_logger.info("Processing VCF: %s", vcf_path)
    print(f"\n[INFO] Processing VCF: {vcf_path}")

    per_sample = process_multi_sample(vcf_path, rules)
    if not per_sample:
        msg = f"No genotype/sample columns detected in {vcf_path}. PGx matching not possible."
        root_logger.warning(msg)
        print(f"[WARNING] {msg}")
        return

    results_by_patient: Dict[str, dict] = {}

    for sample, obj in per_sample.items():
        patient_id = f"{prefix}_{sample}" if prefix else sample
        patient_logger = get_patient_logger(patient_id)

        matches = obj.get("matches", [])
        stats = obj.get("stats", {})

        summary = f"[RESULTS] Sample: {sample} | Patient: {patient_id} | Matches: {stats.get('total_matches', 0)}"
        print(summary)
        patient_logger.info(summary)

        for m in matches:
            extra = []
            if m.get("level_of_evidence"):
                extra.append(f"Level: {m['level_of_evidence']}")
            if m.get("recommendation"):
                extra.append(f"Recommendation: {m['recommendation']}")
            extra_str = " | ".join(extra)

            variant_key = m.get('variant_rsid') or m.get('variant_coor', '')
            msg = (f"Variant: {variant_key} | Gene: {m.get('gene','')} | Drug: {m.get('drug','')} "
                   f"| Effect: {m.get('effect','')}{' | ' + extra_str if extra_str else ''}")
            print(f"  - {msg}")
            patient_logger.info(msg)

        result_obj = assemble_result(
            patient_id=patient_id,
            sample=sample,
            vcf_path=vcf_path,
            matches=matches,
            stats=stats,
            rules_meta=rules_meta,
        )
        results_by_patient[patient_id] = result_obj

    written = write_outputs(RESULTS_DIR, results_by_patient)
    for pid, paths in written.items():
        info_msg = f"Saved JSON: {paths['json_path']} | Summary: {paths['summary_path']} | Log: {LOGS_DIR / f'{pid}.log'}"
        print(f"[INFO] {info_msg}")
        get_patient_logger(pid).info(info_msg)

# ---------------------------------------------------------------------
# CLI main
# ---------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="OncoAdvisorPGx - CLI: Process VCF files with PGx rules (multi-sample supported).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--vcf", help="Path to a single VCF/VCF.gz file")
    group.add_argument("--batch_dir", help="Directory with multiple VCF/VCF.gz files")

    parser.add_argument("--rules", required=False, default=None, help="Optional PGx rules CSV file")
    parser.add_argument("--patient_prefix", required=True, help="Prefix for patient_id in multi-sample/batch mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging output")

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    root_logger.info("=== PGx CLI started ===")
    root_logger.info("Arguments: %s", vars(args))
    print("=" * 60)
    print("OncoAdvisorPGx - Command Line Interface")
    print("=" * 60)

    try:
        if args.rules:
            rules_path = Path(args.rules)
            if not rules_path.is_file():
                raise FileNotFoundError(f"Rules CSV not found: {rules_path}")
            rules, rules_meta = load_rules(rules_path)
            root_logger.info("Loaded %d rules from CSV", len(rules))
        else:
            rules, rules_meta = load_rules_from_db()
            root_logger.info("Loaded %d rules from SQLite", len(rules))
    except Exception as e:
        root_logger.error("Failed to load rules: %s", e)
        print(f"[ERROR] Failed to load rules: {e}")
        sys.exit(1)

    try:
        if args.vcf:
            process_and_write(Path(args.vcf), args.patient_prefix, rules, rules_meta)
        else:
            batch_dir = Path(args.batch_dir)
            if not batch_dir.is_dir():
                raise NotADirectoryError(f"Batch directory not found: {batch_dir}")
            vcfs = sorted(list(batch_dir.glob("*.vcf")) + list(batch_dir.glob("*.vcf.gz")))
            if not vcfs:
                print(f"[WARNING] No VCF files found in {batch_dir}")
                root_logger.warning("No VCF files found in %s", batch_dir)
            else:
                root_logger.info("Batch processing %d files", len(vcfs))
                for i, v in enumerate(vcfs, 1):
                    print(f"\n--- Processing file {i}/{len(vcfs)} ---")
                    process_and_write(v, args.patient_prefix, rules, rules_meta)
    except KeyboardInterrupt:
        root_logger.info("CLI interrupted by user")
        print("\n[INFO] Processing interrupted by user")
        sys.exit(0)
    except Exception as e:
        root_logger.exception("Unexpected error: %s", e)
        print(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)

    root_logger.info("=== PGx CLI finished ===")
    print("\n[COMPLETED] PGx analysis finished successfully!")
    print(f"Check results in: {RESULTS_DIR}")

if __name__ == "__main__":
    main()
