#!/usr/bin/env python3
"""
Script to load PGx rules from a CSV file into an SQLite database.
"""

# ==== Standard library imports ====
import sys
import sqlite3
import logging
import os
from pathlib import Path
from typing import Optional

# ==== Third-party imports ====
import pandas as pd

# ---- Configure logging ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def load_rules_to_db(csv_file: str, db_file: Optional[str] = None) -> bool:
    """Load PGx rules from a CSV file into SQLite."""
    if db_file is None:
        base_dir = Path.home() / "home_workspace"
        db_dir = base_dir / "backend" / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_file = db_dir / "pgx_app.db"

    csv_path = Path(csv_file)
    if not csv_path.exists():
        logging.error("CSV file not found: %s", csv_file)
        return False

    try:
        logging.info("Reading rules from %s...", csv_file)
        df = pd.read_csv(csv_file, keep_default_na=False, dtype=str, encoding="utf-8-sig")
        logging.info("%d rules were found", len(df))

        # Normalize headers
        cols_lc_map = {c.lower(): c for c in df.columns}

        # Detect variant or locus column
        if "variant_rsid" not in cols_lc_map and "variant_coor" not in cols_lc_map:
            logging.error(
                "CSV must contain an rsID variant identifier column or genomic coordinate column. Found: %s",
                list(df.columns)
            )
            return False

        # Required columns
        required_cols = {"drug", "gene", "effect", "level_of_evidence", "clinical_guideline", "recommendation"}
        missing_required = required_cols - set(cols_lc_map.keys())
        if missing_required:
            logging.error("Missing required columns: %s", missing_required)
            return False

        # Connect to database and insert rules
        logging.info("Connecting to database %s...", db_file)
        with sqlite3.connect(db_file) as conn:
            logging.info("Inserting rules into 'rules' table...")

            # Ensure the schema matches what app.py expects
            conn.execute("DROP TABLE IF EXISTS rules")
            conn.execute("""
                CREATE TABLE rules (
                    variant_rsid TEXT,
                    variant_coor TEXT,
                    drug TEXT,
                    gene TEXT,
                    effect TEXT,
                    level_of_evidence TEXT,
                    clinical_guideline TEXT,
                    recommendation TEXT
                )
            """)

            df.to_sql("rules", conn, if_exists="append", index=False)

            # Validate insertion
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rules")
            count = cursor.fetchone()[0]
            logging.info("%d rules successfully loaded into the database", count)
            logging.info("Database saved at: %s", db_file)

            # --- Preview first 3 rules in tabular format ---
            cursor.execute("SELECT * FROM rules LIMIT 3")
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            if rows:
                logging.info("First 3 rules loaded from the database:")
                logging.info(" | ".join(columns))  # header
                for row in rows:
                    logging.info(" | ".join(str(item) if item is not None else "" for item in row))

        return True

    except Exception as e:
        logging.exception("Error while loading rules: %s", str(e))
        return False


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 2:
        print("Usage: python load_rules_into_db.py <rules_file.csv>")
        sys.exit(1)     
    csv_file = sys.argv[1]
    db_file = "backend/db/pgx_app.db"

    # Call to the function
    success = load_rules_to_db(csv_file, db_file)

    if success:
        logging.info("Rules successfully loaded and ready to use.")
    else:
        logging.error("Failed to load rules. Check the messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
