#!/usr/bin/env python3
"""
Core module for pharmacogenomic (PGx) analysis. Provides reusable functions to:
- Load PGx rules from CSV (variant or locus based).
- Process single or multi-sample VCF files and detect carrier status.
- Match variants against PGx rules and compile results.
- Generate structured outputs (JSON for APIs, TXT for reports and LOG for trazability).

Used by the backend API and the frontend CLI and GUI.
"""

from __future__ import annotations

import gzip
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------
# Timezone settings
# ---------------------------------------------------------------------
EU_TZ = ZoneInfo("Europe/Madrid")

# ---------------------------------------------------------------------
# Genotype utilities
# ---------------------------------------------------------------------
def is_carrier(gt: str | None) -> bool:
    """Check if genotype string indicates a carrier of a non-reference allele."""
    if not gt:
        return False
    gt = gt.replace("|", "/") # Normalize separators
    alleles = gt.split("/")
    return any(a not in ("0", ".") for a in alleles)

# ---------------------------------------------------------------------
# Load rules from SQLite
# ---------------------------------------------------------------------
def load_rules_from_db(db_path: Path) -> Tuple[Dict[str, dict], dict]:
    """Load PGx rules from SQLite database into a dictionary + metadata."""

    # Create an empty dictionary
    rules: Dict[str, dict] = {}

    # Connect to the database and select rules
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT variant_rsid, variant_coor, gene, drug, effect, "
                   "level_of_evidence, clinical_guideline, recommendation FROM rules")

    # Fetch all rules from the database
    rows = cursor.fetchall()
    for row in rows:
        variant_rsid, variant_coor, gene, drug, effect, loe, guideline, recommendation = row
        variants = variant_rsid or variant_coor
        if not variants:
            continue
        rules[variants] = {
            "variant_rsid": variant_rsid or "",
            "variant_coor": variant_coor or "",
            "gene": gene or "",
            "drug": drug or "",
            "effect": effect or "",
            "level_of_evidence": loe or "",
            "clinical_guideline": guideline or "",
            "recommendation": recommendation or "",
        }

    # Create a dictionary containing metadata about the rules
    meta = {
        "rules_source": str(db_path),
        "total_rules": len(rules),
        "has_rsid": any(r["variant_rsid"] for r in rules.values()),
        "has_coor": any(r["variant_coor"] for r in rules.values()),
    }

     # Close the database connection and return the dictionaries
    conn.close()
    return rules, meta

# ---------------------------------------------------------------------
# VCF processing
# ---------------------------------------------------------------------
def process_multi_sample(vcf_path: Path, rules: Dict[str, dict]) -> Dict[str, dict]:
    """
    Process a single- or multi-sample VCF file line by line.
    Matches variants by rsID first, then by genomic coordinate.
    """
    open_fn = gzip.open if vcf_path.suffix == ".gz" else open

    sample_names: List[str] = []
    per_sample_matches: Dict[str, List[dict]] = {}
    per_sample_stats: Dict[str, dict] = {}

    with open_fn(vcf_path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                parts = line.strip().split()
                if len(parts) > 9:
                    sample_names = parts[9:]
                    per_sample_matches = {s: [] for s in sample_names}
                    per_sample_stats = {
                        s: {"total_variants": 0, "total_matches": 0}
                        for s in sample_names
                    }
                continue

            if not line.strip():
                continue
            fields = line.strip().split()
            if len(fields) < 5:
                continue

            chrom, pos, vid, ref, alt = fields[0], fields[1], fields[2], fields[3], fields[4]
            locus = f"{chrom}:{pos}:{ref}:{alt}"

            gt_idx = None
            if len(fields) > 8:
                format_cols = fields[8].split(":")
                if "GT" in format_cols:
                    gt_idx = format_cols.index("GT")

            for i, sample in enumerate(sample_names, start=9):
                stats = per_sample_stats[sample]
                stats["total_variants"] += 1

                gt = None
                if len(fields) > i and gt_idx is not None:
                    sample_cols = fields[i].split(":")
                    if gt_idx < len(sample_cols):
                        gt = sample_cols[gt_idx]

                if is_carrier(gt):
                    rule = rules.get(vid) or rules.get(locus)
                    if rule:
                        per_sample_matches[sample].append({
                            "variant_match": rule.get("variant_rsid") or rule.get("variant_coor") or vid,
                            "variant_rsid": rule.get("variant_rsid"),
                            "variant_coor": rule.get("variant_coor"),
                            "gene": rule.get("gene", ""),
                            "drug": rule.get("drug", ""),
                            "effect": rule.get("effect", ""),
                            "level_of_evidence": rule.get("level_of_evidence", ""),
                            "recommendation": rule.get("recommendation", ""),
                            "clinical_guideline": rule.get("clinical_guideline", ""),
                        })

    if sample_names:
        for s in sample_names:
            per_sample_stats[s]["total_matches"] = len(per_sample_matches[s])
        return {s: {"matches": per_sample_matches[s], "stats": per_sample_stats[s]} for s in sample_names}
    return {}

# ---------------------------------------------------------------------
# Result assembly
# ---------------------------------------------------------------------
def assemble_result(patient_id: str, sample: str, vcf_path: Path, matches: List[dict], stats: dict, rules_meta: dict | None = None) -> dict:
    dt_utc = datetime.now(timezone.utc)
    dt_local = dt_utc.astimezone(EU_TZ)
    result = {
        "patient": patient_id,
        "sample": sample,
        "analysis_timestamp_utc": dt_utc.isoformat(),
        "analysis_timestamp_local": dt_local.isoformat(),
        "timezone": str(EU_TZ.key),
        "vcf_path": str(vcf_path),
        "stats": stats,
        "matches": matches,
    }
    if rules_meta:
        result["rules_meta"] = rules_meta
    return result

# ---------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------
def write_outputs(results_dir: Path, results_by_patient: Dict[str, dict]) -> Dict[str, dict]:
    json_dir = results_dir / "json"
    txt_dir = results_dir / "txt"
    log_dir = results_dir / "logs"
    for d in [json_dir, txt_dir, log_dir]:
        d.mkdir(parents=True, exist_ok=True)

    out: Dict[str, dict] = {}
    for patient_id, obj in results_by_patient.items():
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in patient_id)

        json_path = json_dir / f"{safe_id}.json"
        with json_path.open("w", encoding="utf-8") as jf:
            json.dump(obj, jf, indent=2, ensure_ascii=False)

        summary_path = txt_dir / f"{safe_id}.txt"
        with summary_path.open("w", encoding="utf-8") as sf:
            sf.write(f"PHARMACOGENOMIC REPORT - PATIENT {patient_id}\n")
            if "sample" in obj and obj["sample"]:
                sf.write(f"Sample: {obj['sample']}\n")
            ts_local = obj.get("analysis_timestamp_local", "")
            tz = obj.get("timezone", "UTC")
            sf.write(f"Analysis date (Local): {ts_local} {tz}\n")
            sf.write(f"VCF: {obj.get('vcf_path','')}\n")

            stats = obj.get("stats", {})
            sf.write(f"Total variants read: {stats.get('total_variants', 0)}\n")
            sf.write(f"Variants with GT: {stats.get('with_gt', 0)}\n")
            sf.write(f"Variants without GT: {stats.get('without_gt', 0)}\n")
            sf.write(f"Total PGx matches: {stats.get('total_matches', 0)}\n\n")

            matches = obj.get("matches", [])
            if matches:
                sf.write("MATCHES FOUND:\n")
                sf.write("-" * 50 + "\n")
                for i, m in enumerate(matches, 1):
                    sf.write(f"{i}. Variant: {m.get('variant','')}\n")
                    if m.get("variant_rsid"):
                        sf.write(f"   RSID: {m['variant_rsid']}\n")
                    if m.get("variant_coor"):
                        sf.write(f"   Genomic coordinate: {m['variant_coor']}\n")
                    sf.write(f"   Gene: {m.get('gene','')}\n")
                    sf.write(f"   Drug: {m.get('drug','')}\n")
                    sf.write(f"   Effect: {m.get('effect','')}\n")
                    if m.get("level_of_evidence"):
                        sf.write(f"   Level of evidence: {m['level_of_evidence']}\n")
                    if m.get("recommendation"):
                        sf.write(f"   Recommendation: {m['recommendation']}\n")
                    if m.get("clinical_guideline"):
                        sf.write(f"   Clinical guideline: {m['clinical_guideline']}\n")
                    sf.write("\n")
            else:
                sf.write("No pharmacogenomically relevant variants found.\n")

        log_path = log_dir / f"{safe_id}.log"
        with log_path.open("w", encoding="utf-8") as lf:
            lf.write(f"Patient {patient_id} processed.\n")
            lf.write(f"JSON written to: {json_path}\n")
            lf.write(f"TXT written to: {summary_path}\n")

        out[patient_id] = {
            "json_path": str(json_path),
            "summary_path": str(summary_path),
            "log_path": str(log_path)
        }

    return out
