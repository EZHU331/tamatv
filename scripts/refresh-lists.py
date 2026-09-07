#!/usr/bin/env python3
"""Backward-compatible entry. Use scripts/pipeline.py."""

from pipeline import main

if __name__ == "__main__":
    raise SystemExit(main())
