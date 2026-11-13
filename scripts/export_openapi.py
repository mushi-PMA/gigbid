"""Write the FastAPI OpenAPI schema to apps/api/openapi.json (source of the generated TypeScript client)."""
from __future__ import annotations

import json

from common.config import ROOT

PATH = ROOT / "apps" / "api" / "openapi.json"


def current() -> str:
    from apps.api.main import app

    return json.dumps(app.openapi(), indent=1, sort_keys=True) + "\n"


def main() -> None:
    PATH.write_text(current(), encoding="utf-8")
    print(f"wrote {PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
