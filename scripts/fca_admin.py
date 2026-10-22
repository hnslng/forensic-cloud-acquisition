#!/usr/bin/env python3
"""Separate installation, update, diagnosis and backup commands; no secret output."""
from pathlib import Path
import sys
# Installed release bytes are verified; never create unsigned Python caches there.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infrastructure.installer.manager import main

if __name__ == '__main__':
    main()
