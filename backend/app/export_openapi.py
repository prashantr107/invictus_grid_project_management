"""Write the generated OpenAPI schema to `docs/openapi.json`.

The JSON file is committed as a stable API-contract artifact so reviewers can
diff the surface between changes without running the server. Regenerate with
`npm run backend:openapi` (or `python -m app.export_openapi`)."""

import json
from pathlib import Path

from app.main import app

_TARGET = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def main() -> None:
    _TARGET.parent.mkdir(parents=True, exist_ok=True)
    _TARGET.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {_TARGET}")


if __name__ == "__main__":
    main()
