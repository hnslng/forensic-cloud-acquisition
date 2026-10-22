#!/usr/bin/env python3
"""Separate installation, update, diagnosis and backup commands; no secret output."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infrastructure.installer.manager import main

if __name__ == '__main__':
    main()
