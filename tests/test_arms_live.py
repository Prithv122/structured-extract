"""The one test that touches the network: do the pinned model ids still exist?

Marked ``live`` and deselected by default, so the fast suite stays offline and
a clean clone with no network still goes green. Run it deliberately:

    uv run pytest -m live

It reads only the **public** catalogue -- no API key, no spend. It is the
automated form of ``structured-extract arms verify``, and it exists because a
pinned id that quietly disappears is exactly how project 24 published a table
with an arm that had never executed.
"""

from __future__ import annotations

import pytest

from structured_extract import arms as A

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def catalogue() -> dict[str, dict]:
    try:
        return A.fetch_catalogue()
    except RuntimeError as exc:
        pytest.skip(f"offline: {exc}")


def test_every_pinned_arm_still_resolves_and_still_costs_what_we_published(catalogue):
    failures = [
        f"{c.arm.key} {c.arm.model_id}: {'; '.join(c.problems)}"
        for c in A.verify(catalogue=catalogue)
        if not c.ok
    ]
    assert not failures, "\n".join(failures)


def test_every_arm_can_hold_the_largest_document_and_the_reply(catalogue):
    """A context window smaller than the corpus would produce provider errors
    that look like model failures. The cap in ``cli.MAX_SECTION_CHARS`` exists
    to keep this true; this asserts the two have not drifted apart."""
    from structured_extract import extract, jsonl, paths
    from structured_extract.cli import MAX_SECTION_CHARS

    rows = jsonl.read_list(paths.CORPUS_JSONL)
    largest = max(r["n_chars"] for r in rows)
    assert largest <= MAX_SECTION_CHARS

    # chars/4 for the document, plus prompt and schema, plus the output budget.
    needed = largest // 4 + 1_000 + extract.MAX_OUTPUT_TOKENS
    for check in A.verify(catalogue=catalogue):
        assert check.context_length > needed, f"{check.arm.key} context {check.context_length}"
        assert (check.max_completion_tokens or 0) >= extract.MAX_OUTPUT_TOKENS
