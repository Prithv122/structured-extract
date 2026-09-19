"""Fetch the upstream DuckDB documentation at the pinned commit.

Only the two *builders* (``oracle build``, ``corpus build``) need this. Everything
downstream -- extraction, scoring, the published tables -- runs from the committed
JSONL and the vendored documents under ``data/corpus/``, so a clean clone can
reproduce every number with no network access.

The commit is pinned rather than tracking ``main`` because the docs and the
oracle have to describe the same release: this checkout's ``_config.yml`` says
``current_duckdb_version: "1.5.5"``, which is exactly the ``duckdb`` version
pinned in ``pyproject.toml``. Fetching a later commit would silently reintroduce
the confound the pin exists to remove.

    uv run python scripts/fetch_source_docs.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/duckdb/duckdb-web.git"
COMMIT = "6f6cd1659f0e2ddd1965b1d3f1833e7fc512e7ac"
EXPECTED_DUCKDB_VERSION = "1.5.5"

DEST = Path(__file__).resolve().parents[1] / "data" / "source" / "duckdb-web"


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()


def assert_version_pin(root: Path) -> None:
    """Fail loudly if the checkout does not document the duckdb version we pin."""
    config = (root / "_config.yml").read_text(encoding="utf-8")
    needle = f'current_duckdb_version: "{EXPECTED_DUCKDB_VERSION}"'
    if needle not in config:
        raise SystemExit(
            f"_config.yml does not contain {needle!r}. The docs checkout and the "
            "installed duckdb describe different releases; fix the pin before building."
        )


def main() -> int:
    if (DEST / ".git").exists():
        head = run("git", "-C", str(DEST), "rev-parse", "HEAD")
        if head == COMMIT:
            assert_version_pin(DEST)
            print(f"already at {COMMIT[:12]} ({EXPECTED_DUCKDB_VERSION}) -> {DEST}")
            return 0
        print(f"checkout is at {head[:12]}, want {COMMIT[:12]}; fetching")
    else:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        run("git", "init", "-q", str(DEST))
        run("git", "-C", str(DEST), "remote", "add", "origin", REPO)

    # A single-commit fetch: the full history is ~100 MB and nothing here reads it.
    run("git", "-C", str(DEST), "fetch", "--depth", "1", "--filter=blob:none", "origin", COMMIT)
    run("git", "-C", str(DEST), "checkout", "-q", "--detach", "FETCH_HEAD")

    head = run("git", "-C", str(DEST), "rev-parse", "HEAD")
    if head != COMMIT:
        raise SystemExit(f"checked out {head}, expected {COMMIT}")
    assert_version_pin(DEST)

    pages = len(list((DEST / "docs").rglob("*.md")))
    print(f"fetched {COMMIT[:12]} ({EXPECTED_DUCKDB_VERSION}), {pages} markdown pages -> {DEST}")
    print(f"licence: {(DEST / 'LICENSE').read_text(encoding='utf-8').splitlines()[0].strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
