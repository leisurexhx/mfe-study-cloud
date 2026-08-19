"""Web process command-line entry point."""

from __future__ import annotations

import uvicorn

from mfe_study_cloud.config import get_settings
from mfe_study_cloud.logging_config import configure_logging


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        "mfe_study_cloud.web.app:create_app",
        factory=True,
        host=settings.web_host,
        port=settings.web_port,
        log_level=settings.log_level.casefold(),
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
