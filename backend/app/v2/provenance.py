"""Allowlisted worker identity, without connection URLs, credentials or user edits."""

import hashlib
import os
import platform
import subprocess
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version, distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def runtime_identity():
    packages = {}
    for package in (
        "paddlepaddle",
        "paddleocr",
        "paddlex",
        "pypdfium2",
        "numpy",
        "Pillow",
        "celery",
        "SQLAlchemy",
    ):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    source = hashlib.sha256()
    for folder in ("ai", "backend/app/v2", "schemas"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.suffix in (".py", ".json"):
                source.update(str(path.relative_to(ROOT)).encode())
                source.update(path.read_bytes())
    commit = os.getenv("VIETRECEIPT_COMMIT") or None
    dirty = None
    if (ROOT / ".git").exists():
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
            dirty = bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=ROOT, text=True
                ).strip()
            )
        except (OSError, subprocess.CalledProcessError):
            pass
    return dict(
        commit=commit,
        git_dirty=dirty,
        source_sha256=source.hexdigest(),
        python=platform.python_version(),
        platform=platform.platform(),
        architecture=platform.machine(),
        packages=packages,
        resolved_packages={
            dist.metadata["Name"]: dist.version
            for dist in distributions()
            if dist.metadata.get("Name")
        },
    )


def processing_config():
    from ai.document_reader import ReaderConfig
    from ai.kie.v2.config import CONFIGURATION, EXTRACTOR
    from dataclasses import asdict
    from .providers import DEFAULT_PROVIDERS

    return dict(
        providers={
            key: os.getenv(key, default) for key, default in DEFAULT_PROVIDERS.items()
        },
        reader=asdict(ReaderConfig()),
        reader_isolation=os.getenv("V2_READER_ISOLATION", "subprocess"),
        reader_timeout_seconds=os.getenv("V2_READER_TIMEOUT_SECONDS", "780"),
        kie_extractor=EXTRACTOR,
        kie_configuration=CONFIGURATION,
    )


def model_artifacts():
    """Hash cached model bytes after inference; absent cache is explicit, not invented."""
    root = (
        Path(os.getenv("PADDLE_PDX_CACHE_HOME", str(ROOT / ".paddlex-cache")))
        / "official_models"
    )
    hashes = {}
    for model in (
        "PP-LCNet_x1_0_doc_ori",
        "PP-OCRv3_mobile_det",
        "latin_PP-OCRv3_mobile_rec",
    ):
        for path in sorted((root / model).rglob("*")):
            if path.is_file() and path.suffix in (
                ".pdmodel",
                ".pdiparams",
                ".json",
                ".yml",
                ".yaml",
            ):
                try:
                    hashes[str(path.relative_to(root))] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                except OSError:
                    hashes[str(path.relative_to(root))] = None
    return hashes


def callable_identity(provider):
    return (
        getattr(provider, "__module__", type(provider).__module__)
        + ":"
        + getattr(provider, "__qualname__", type(provider).__qualname__)
    )
