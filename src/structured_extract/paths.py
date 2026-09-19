"""Repo-relative paths.

Everything downstream reads committed JSONL under ``data/``; only the two
*builders* need the upstream documentation checkout, which is fetched (not
committed) by ``scripts/fetch_source_docs.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA = REPO_ROOT / "data"
ORACLE_DIR = DATA / "oracle"
CORPUS_DIR = DATA / "corpus"
SOURCE_DIR = DATA / "source"

SETTINGS_JSONL = ORACLE_DIR / "settings.jsonl"
DOCS_REFERENCE_JSONL = ORACLE_DIR / "docs_reference.jsonl"
OBSERVED_VALUES_JSONL = ORACLE_DIR / "observed_values.jsonl"

CORPUS_JSONL = CORPUS_DIR / "corpus.jsonl"
CORPUS_DOCUMENTS = CORPUS_DIR / "documents"

#: Upstream docs checkout, pinned in ``scripts/fetch_source_docs.py``.
DEFAULT_DOCS_ROOT = SOURCE_DIR / "duckdb-web"

#: Path of the generated configuration reference page, relative to the docs root.
CONFIG_REFERENCE_PAGE = "docs/current/configuration/overview.md"

#: Where the markdown pages live, relative to the docs root.
DOCS_SUBDIR = "docs/current"


def docs_root() -> Path:
    """Resolve the upstream docs checkout, honouring ``DUCKDB_WEB_ROOT``."""
    env = os.environ.get("DUCKDB_WEB_ROOT")
    return Path(env).expanduser().resolve() if env else DEFAULT_DOCS_ROOT
