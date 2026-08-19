"""Regenerate the checked-in provider JSON Schema from the Pydantic contract."""

from __future__ import annotations

import json
from pathlib import Path

from mfe_study_cloud.analysis.models import SCHEMA_VERSION, BatchAnalysisOutput


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / "src" / "mfe_study_cloud" / "schemas" / "page_analysis_v1.json"
    schema = BatchAnalysisOutput.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://example.invalid/mfe-study-cloud/schemas/{SCHEMA_VERSION}.json"
    schema["title"] = "MFE Study Cloud page analysis v1"
    target.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
