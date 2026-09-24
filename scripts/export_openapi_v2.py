"""Generate the checked-in V2 contract from the actual router models."""

from pathlib import Path

import yaml
from fastapi import FastAPI

from backend.app.v2.api import router


def document():
    app = FastAPI(title="VietReceipt Invoice API", version="2.0.0")
    app.include_router(router)
    return app.openapi()


if __name__ == "__main__":
    Path("openapi/openapi-v2.yaml").write_text(
        yaml.safe_dump(document(), allow_unicode=True, sort_keys=False)
    )
