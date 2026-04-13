#!/usr/bin/env python3
"""Emit FastAPI OpenAPI 3 schema to docs/openapi.json (no server required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "openapi.json"


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from app.main import create_app

    spec = create_app().openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
