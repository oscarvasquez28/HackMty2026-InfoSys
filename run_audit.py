#!/usr/bin/env python3
"""
Root entrypoint script for executing the Polar Forensic AML Auditor.

Usage:
    python run_audit.py --estate /path/to/estate.db [--seed 42] [--output-dir ./output]
"""

import sys
from backend.cli import main

if __name__ == "__main__":
    main()

