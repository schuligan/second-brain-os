#!/usr/bin/env python3
"""Thin launcher so you can run `python brain.py ...` or `./brain.py ...`.

Equivalent to `python -m brain.cli`. Provided for convenience; the package
entrypoint is `brain.cli:main`.
"""

from brain.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
