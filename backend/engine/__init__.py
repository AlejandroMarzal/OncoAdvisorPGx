"""
PGx Core Package

This package contains the core pharmacogenomic analysis functionality
for the PGx Cancer App. It provides functions for loading PGx rules,
processing VCF files, and generating structured results.

Main functions:
- load_rules: Load pharmacogenomic rules from CSV files
- process_multi_sample: Process VCF files against PGx rules
- assemble_result: Structure analysis results for output
- write_outputs: Write results to JSON and text files
"""

from .core import (
    load_rules,
    process_multi_sample,
    assemble_result,
    write_outputs,
)

# Define public API - what gets imported with 'from pgx_core import *'
__all__ = [
    "load_rules",
    "process_multi_sample",
    "assemble_result",
    "write_outputs",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "Alejandro Marzal (VIU - Valencian International University)"
__coauthors__ = "Pablo Marin"
__description__ = "Core pharmacogenomic analysis engine for PGx Cancer App (TFM Project)"
