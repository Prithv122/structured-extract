"""Record the calls the provider never answered, so a clean clone replays them.

The response cache stores response bodies. A call that exhausted its retries on
an HTTP 429 has no body, so 20 of the full grid's 1,200 rows had nothing to
cache -- and `extract run` on a fresh clone aborted on the first of them instead
of reproducing the run. `call()` now writes a `.failed.json` beside the
responses when it gives up. This script writes the ones that predate that
change.

**These records are reconstructed from `data/results/extractions.jsonl`, not
captured from the wire**, because the wire produced nothing to capture. That is
why every one carries `"_backfilled": true`: a reader can tell a replayed
failure from an observed one without taking this docstring on trust.

Idempotent. Never overwrites an existing file, and never touches a row that
succeeded.

    uv run python scripts/backfill_exhausted_cache.py
"""

from __future__ import annotations

import json
from pathlib import Path

from structured_extract import jsonl, paths
from structured_extract.arms import BY_KEY
from structured_extract.extract import PROMPTS, build_payload, cache_key


def main() -> int:
    rows = jsonl.read_list(paths.RESULTS_JSONL)
    failed = [r for r in rows if r["error"]]
    print(f"{len(failed)} of {len(rows)} rows carry an error")

    written, present = 0, 0
    for row in failed:
        arm = BY_KEY[row["arm"]]
        document = (paths.CORPUS_DOCUMENTS / f"{row['doc_id']}.md").read_text(encoding="utf-8")
        messages = [
            {"role": "system", "content": PROMPTS[row["prompt"]]},
            {"role": "user", "content": document},
        ]
        key = cache_key(arm.model_id, build_payload(arm, messages))
        path: Path = paths.CACHE_DIR / arm.key / f"{key}.failed.json"

        # A row can carry an error *and* a cached body -- a repair that failed
        # after a successful first call. Those replay already; leave them alone.
        if (paths.CACHE_DIR / arm.key / f"{key}.json").exists():
            present += 1
            continue
        if path.exists():
            present += 1
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "_failure": True,
                    "_backfilled": True,
                    "error": row["error"],
                    "unavailable": row["outcome"] == "provider_unavailable",
                    "attempts": None,
                    "latency_s": row["latency_s"],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
            newline="\n",
        )
        written += 1
        print(f"  wrote {arm.key}/{key[:12]}...  {row['prompt']:<15} {row['doc_id']}")

    print(f"\n{written} written, {present} already replayable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
