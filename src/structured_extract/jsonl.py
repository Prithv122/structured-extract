"""Deterministic JSONL read/write.

Every committed data file is written through here so a rebuild on another
machine produces a byte-identical diff or a real one -- never a diff made of
key reordering, ``\\r\\n`` or escaped non-ASCII.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path


def write(path: Path, rows: Iterable[dict]) -> int:
    """Write ``rows`` as JSONL. Returns the number of rows written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def read(path: Path) -> Iterator[dict]:
    """Read JSONL, reporting the line number on a malformed row."""
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{lineno}: {exc}") from exc


def read_list(path: Path) -> list[dict]:
    return list(read(path))
