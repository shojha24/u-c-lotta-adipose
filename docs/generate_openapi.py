"""Export FastAPI's OpenAPI schema and generate a Markdown reference page."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "ucla-dining-api"
DOCS_DIR = ROOT / "docs"

sys.path.insert(0, str(API_DIR))
os.environ.setdefault("S3_BUCKET_NAME", "u-c-lotta-adipose-v2")

from src.main import app  # noqa: E402

PROD_SERVER = {
    "url": "https://ddy58mflxj.execute-api.us-west-2.amazonaws.com/prod",
    "description": "Production AWS API Gateway",
}


def build_openapi() -> dict:
    schema = app.openapi()
    schema["servers"] = [PROD_SERVER]
    schema.setdefault("info", {})["description"] = (
        "REST API for UCLA dining hall menus, operating hours, food truck schedules, "
        "recreation center hours & live occupancy, and nutrition calculation."
    )
    return schema


def build_reference_markdown(schema: dict) -> str:
    lines = [
        "# OpenAPI Reference",
        "",
        "This page is auto-generated from FastAPI's OpenAPI schema (`ucla-dining-api/src/main.py`).",
        "",
        "- **Interactive Explorer**: [Open Swagger UI](api-explorer.html)",
        "- **Raw Schema**: [openapi.json](openapi.json)",
        "",
        "## Endpoint Summary",
        "",
        "| Method | Path | Parameters | Summary |",
        "|---|---|---|---|",
    ]

    for path, methods in schema.get("paths", {}).items():
        for method, spec in methods.items():
            params = spec.get("parameters", [])
            param_str = ", ".join(
                f"`{p['name']}` ({p['in']}{'*' if p.get('required') else ''})"
                for p in params
            ) or "—"
            summary = spec.get("summary") or spec.get("operationId", "")
            lines.append(
                f"| `{method.upper()}` | `{path}` | {param_str} | {summary} |"
            )

    lines.extend([
        "",
        "!!! tip \"Try it live\"",
        "    Use the [Interactive Swagger UI](api-explorer.html) to inspect schemas and test endpoints directly against the production API.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    schema = build_openapi()
    (DOCS_DIR / "openapi.json").write_text(json.dumps(schema, indent=2) + "\n")
    (DOCS_DIR / "reference.md").write_text(build_reference_markdown(schema))
    print(f"Generated {DOCS_DIR / 'openapi.json'} and {DOCS_DIR / 'reference.md'}")


if __name__ == "__main__":
    main()
