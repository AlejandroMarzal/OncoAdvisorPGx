#!/usr/bin/env python3
"""
Command-line interface (CLI) for pharmacogenomic (PGx) analysis.This CLI is part
of the OncoAdvisorPGx frontend, providing a command-line
interface for bioinformaticians and pipeline integration.

Features:
- Supports single or batch VCF processing (multi-sample enabled).
- Loads PGx rules from SQLite.
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

from backend.engine import load_rules_from_db, process_multi_sample, assemble_result, write_outputs

# ---------------------------------------------------------------------
# Global settings
# ---------------------------------------------------------------------
# Set up directories
BASE_DIR = Path.home() / "home_workspace"
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = RESULTS_DIR / "logs"
DB_PATH = BASE_DIR / "backend" / "db" / "pgx_app.db"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Root logger
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

    # Initialize patient-specific logger
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_path)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

        # No duplicate
        logger.propagate = False

    return logger

# ---------------------------------------------------------------------
# Process VCF and write outputs
# ---------------------------------------------------------------------
def process_and_write(vcf_path: Path, prefix: str, rules: dict, rules_meta: dict) -> None:
    """
    t takes a VCF and a set of rules, analyzes the genotypes of each sample, identifies
    relevant variants according to the PGx rules, logs all information per patient,
    and generates JSON and TXT output files for each patient.
    """
    # Validate VCF file
    if not vcf_path.is_file():
        root_logger.error("VCF not found: %s", vcf_path)
        raise FileNotFoundError(f"VCF file not found: {vcf_path}")

    # Initial message
    root_logger.info("Processing VCF: %s", vcf_path)

    # Processing by sample
    per_sample = process_multi_sample(vcf_path, rules)
    if not per_sample:
        msg = f"No genotype/sample columns detected in {vcf_path}. PGx matching not possible."
        root_logger.warning(msg)
        return

    results_by_patient: Dict[str, dict] = {}

    # Iteration by sample
    for sample, obj in per_sample.items():
        patient_id = f"{prefix}_{sample}" if prefix else sample
        patient_logger = get_patient_logger(patient_id)

        # Produce summary of matches
        matches = obj.get("matches", [])
        stats = obj.get("stats", {})
        summary = f"[RESULTS] Sample: {sample} | Patient: {patient_id} | Matches: {stats.get('total_matches', 0)}"
        root_logger.info(summary)
        patient_logger.info(summary)

        # Assamble of results
        result_obj = assemble_result(
            patient_id=patient_id,
            sample=sample,
            vcf_path=vcf_path,
            matches=matches,
            stats=stats,
            rules_meta=rules_meta,
        )
        results_by_patient[patient_id] = result_obj

    # Write outputs
    written = write_outputs(results_by_patient)

    # Assamble of results
    for pid, paths in written.items():
        info_msg = f"Saved JSON: {paths['json_path']} | Summary: {paths['summary_path']} | Log: {LOGS_DIR / f'{pid}.log'}"
        root_logger.info(info_msg)
        get_patient_logger(pid).info(info_msg)

# ---------------------------------------------------------------------
# CLI main
# ---------------------------------------------------------------------
def main() -> None:
    # Argument parser setup
    parser = argparse.ArgumentParser(
        description="OncoAdvisorPGx - CLI", formatter_class=argparse.RawDescriptionHelpFormatter
        )

    # Mutually exclusive arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--vcf", help="Path to a single VCF/VCF.gz file")
    group.add_argument("--batch_dir", help="Directory with multiple VCF/VCF.gz files")

    # Other arguments
    parser.add_argument("--patient_prefix", required=True, help="Prefix for patient_id in multi-sample/batch mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging output")

    # Argument parsing
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initial messages
    root_logger.info("------ PGx CLI started ------")
    root_logger.info("Arguments: %s", vars(args))
    print("-" * 60)
    print("OncoAdvisorPGx - Command Line Interface")
    print("-" * 60)

    # Loading PGx rules
    try:
        rules, rules_meta = load_rules_from_db(DB_PATH)
        root_logger.info("Loaded %d rules from SQLite", len(rules))
    except Exception as e:
        root_logger.error("Failed to load rules: %s", e)
        sys.exit(1)

    # Processing VCF(s)
    try:
        if args.vcf:
            process_and_write(Path(args.vcf), args.patient_prefix, rules, rules_meta)
        else:
            batch_dir = Path(args.batch_dir)
            if not batch_dir.is_dir():
                raise NotADirectoryError(f"Batch directory not found: {batch_dir}")
            vcfs = sorted(list(batch_dir.glob("*.vcf")) + list(batch_dir.glob("*.vcf.gz")))
            if not vcfs:
                root_logger.warning("No VCF files found in %s", batch_dir)
            else:
                root_logger.info("Batch processing %d files", len(vcfs))
                for i, v in enumerate(vcfs, 1):
                    print(f"\nProcessing file {i}/{len(vcfs)}")
                    process_and_write(v, args.patient_prefix, rules, rules_meta)

    # Error and interruption handling
    except KeyboardInterrupt:
        root_logger.info("CLI interrupted by user")
        sys.exit(0)
    except Exception as e:
        root_logger.exception("Unexpected error: %s", e)
        sys.exit(1)

    # Final messages
    root_logger.info("------ PGx CLI finished ------")
    root_logger.info("PGx analysis finished successfully!")
    root_logger.info(f"Check results in: {RESULTS_DIR}")

if __name__ == "__main__":
    main()
