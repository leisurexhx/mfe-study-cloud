from __future__ import annotations

import json
import logging

from mfe_study_cloud.logging_config import JsonFormatter


def test_json_logs_include_only_allowlisted_context_and_exception_type() -> None:
    record = logging.LogRecord(
        name="mfe.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=10,
        msg="analysis_failed",
        args=(),
        exc_info=None,
    )
    record.job_id = "safe-job-id"
    record.openai_api_key = "must-not-appear"
    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "analysis_failed"
    assert payload["job_id"] == "safe-job-id"
    assert "openai_api_key" not in payload
    assert "must-not-appear" not in json.dumps(payload)
