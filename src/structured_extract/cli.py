"""Command line entry point.

Two builders need the upstream docs checkout (``scripts/fetch_source_docs.py``);
the verifiers deliberately do not, so CI and a clean clone can check every
committed artefact with no network and no DuckDB extension downloads.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from structured_extract import arms as arms_mod
from structured_extract import corpus as corpus_mod
from structured_extract import extract as extract_mod
from structured_extract import jsonl, paths
from structured_extract import labels as labels_mod
from structured_extract import score as score_mod
from structured_extract.docs_table import parse_reference_page
from structured_extract.oracle import (
    EXTENSIONS,
    alias_map,
    build_oracle,
    distinct_settings,
)

#: Documents per sampling bucket. 120 total: enough that a 10-point difference
#: between arms is outside the sampling band, small enough that three full grids
#: fit the budget.
#:
#: The split is 55/35/30 across the three strata in the design note, reshaped
#: once the corpus was measured rather than assumed. Two constraints forced it:
#:
#: 1. Only **19 extension pages** contain a section naming a non-distractor
#:    setting. ``extension-signal`` therefore takes all 19 -- it is a census of
#:    that part of the documentation, not a sample, and ``corpus build`` says so.
#: 2. 60% of prose sections that mention a "known setting" mention *only*
#:    ``schema``/``user``/``username``/``password``/``threads``/``secret``.
#:    Left alone, those would have taken 54 of the 90 prose documents and the
#:    benchmark would mostly have measured one narrow false-positive case. They
#:    are now sampled at a fixed 16/120 instead of arriving by accident.
QUOTAS = {
    "narrative-signal": 50,
    "narrative-distractor": 10,
    "extension-signal": 19,
    "extension-distractor": 6,
    "reference": 35,
}

#: Changing this reshuffles the whole corpus and invalidates every published
#: number. It is an argument so the sensitivity can be measured, not tuned.
DEFAULT_SEED = 20260919

#: Sections shorter than this are headings with a stub under them -- not enough
#: prose for "did the model read it?" to mean anything.
MIN_SECTION_CHARS = 120

#: Sections longer than this are generated list dumps, not prose a reader
#: consumes: the time-zone reference list (46 kB), the encodings table (26 kB),
#: the spatial function index (17 kB). Section length is median 255 chars,
#: p95 1.5 kB, p99 3.8 kB, so this cap keeps better than 99% of real sections
#: while bounding the per-document cost and staying inside the context window
#: of every arm -- including the 16 k one. The ``reference`` stratum is exempt
#: because its documents are single table rows by construction.
MAX_SECTION_CHARS = 8000


def _load_oracle_names() -> tuple[set[str], dict[str, str]]:
    rows = jsonl.read_list(paths.SETTINGS_JSONL)
    from structured_extract.oracle import OracleSetting

    settings = [
        OracleSetting(
            name=r["name"],
            description=r["description"],
            input_type=r["input_type"],
            scope=r["scope"],
            aliases=r["aliases"],
            extension=r["extension"],
            duckdb_version=r["duckdb_version"],
        )
        for r in rows
    ]
    aliases = alias_map(settings)
    return {s.name for s in settings} | set(aliases), aliases


# --------------------------------------------------------------------------- oracle


def cmd_oracle_build(args: argparse.Namespace) -> int:
    root = paths.docs_root()
    page = root / paths.CONFIG_REFERENCE_PAGE
    if not page.exists():
        print(
            f"missing {page}\nRun: uv run python scripts/fetch_source_docs.py",
            file=sys.stderr,
        )
        return 2

    settings, observed, counts = build_oracle()
    n_settings = jsonl.write(paths.SETTINGS_JSONL, (s.to_json() for s in settings))
    n_observed = jsonl.write(paths.OBSERVED_VALUES_JSONL, (o.to_json() for o in observed))

    docs = parse_reference_page(page)
    n_docs = jsonl.write(paths.DOCS_REFERENCE_JSONL, (d.to_json() for d in docs))

    print(
        f"settings.jsonl        {n_settings:>4} rows ({len(distinct_settings(settings))} distinct)"
    )
    for ext in ["core", *EXTENSIONS]:
        print(f"  {ext:<12} {counts.get(ext, 0):>4}")
    print(f"observed_values.jsonl {n_observed:>4} rows  (machine-dependent, not ground truth)")
    print(f"docs_reference.jsonl  {n_docs:>4} rows ({sum(len(d.aliases) for d in docs)} aliases)")
    return 0


def cmd_oracle_verify(args: argparse.Namespace) -> int:
    """Check the committed oracle, offline, and report the docs-vs-binary audit."""
    problems: list[str] = []

    settings = jsonl.read_list(paths.SETTINGS_JSONL)
    docs = jsonl.read_list(paths.DOCS_REFERENCE_JSONL)
    observed = jsonl.read_list(paths.OBSERVED_VALUES_JSONL)

    names = [s["name"] for s in settings]
    if len(names) != len(set(names)):
        dupes = [n for n, c in Counter(names).items() if c > 1]
        problems.append(f"duplicate setting names: {dupes}")

    versions = {s["duckdb_version"] for s in settings}
    if len(versions) != 1:
        problems.append(f"settings.jsonl mixes duckdb versions: {sorted(versions)}")

    bad_scope = {s["scope"] for s in settings} - {"GLOBAL", "LOCAL"}
    if bad_scope:
        problems.append(f"unexpected scopes: {sorted(bad_scope)}")

    known_ext = {"core", *EXTENSIONS}
    bad_ext = {s["extension"] for s in settings} - known_ext
    if bad_ext:
        problems.append(f"unexpected extensions: {sorted(bad_ext)}")

    if len(observed) != len(settings):
        problems.append(f"observed_values has {len(observed)} rows, settings has {len(settings)}")
    if any("value" in s for s in settings):
        problems.append("settings.jsonl carries a machine-dependent 'value' column")

    # Alias relation: every alias must also exist as its own row, and agree.
    by_name = {s["name"]: s for s in settings}
    alias_to_canon: dict[str, str] = {}
    for s in settings:
        for a in s["aliases"]:
            if a in alias_to_canon:
                problems.append(f"alias {a!r} claimed by {alias_to_canon[a]!r} and {s['name']!r}")
            alias_to_canon[a] = s["name"]
            twin = by_name.get(a)
            if twin and (twin["input_type"], twin["scope"]) != (s["input_type"], s["scope"]):
                problems.append(f"alias row {a!r} disagrees with canonical {s['name']!r}")

    # The docs table must not invent settings, and must not contradict the binary.
    accepted = set(by_name) | set(alias_to_canon)
    doc_labels = {label for d in docs for label in [d["name"], *d["aliases"]]}
    unknown = sorted(doc_labels - accepted)

    def canon(n: str) -> str:
        return alias_to_canon.get(n, n)

    scope_conflicts, type_conflicts = [], []
    for d in docs:
        binary = by_name.get(canon(d["name"]))
        if binary is None:
            continue
        if binary["scope"] != d["scope"]:
            scope_conflicts.append((d["name"], d["scope"], binary["scope"]))
        if binary["input_type"] != d["type"]:
            type_conflicts.append((d["name"], d["type"], binary["input_type"]))

    documented = {canon(d["name"]) for d in docs}
    core = {canon(s["name"]) for s in settings if s["extension"] == "core"}
    all_canon = {canon(s["name"]) for s in settings}

    version = versions.pop() if versions else "?"
    print(
        f"settings.jsonl        {len(settings)} rows, {len(all_canon)} distinct, duckdb {version}"
    )
    print(f"docs_reference.jsonl  {len(docs)} rows, {len(doc_labels)} distinct labels")
    print()
    print("docs vs binary")
    print(f"  documented names unknown to the binary   {len(unknown)}")
    print(f"  scope disagreements                      {len(scope_conflicts)}")
    print(f"  type disagreements                       {len(type_conflicts)}")
    print(f"  core settings the reference omits        {len(core - documented)}")
    print(f"  reference rows that need an extension    {len(documented - core)}")
    print(f"  settings in no reference table at all    {len(all_canon - documented)}")
    if args.detail:
        print()
        print(f"  omitted from reference: {sorted(core - documented)}")
        if unknown:
            print(f"  unknown to binary: {unknown}")
        for label, got, want in scope_conflicts + type_conflicts:
            print(f"  conflict {label}: docs={got!r} binary={want!r}")

    if unknown:
        problems.append(f"{len(unknown)} documented names are unknown to the binary: {unknown}")
    if scope_conflicts:
        problems.append(f"{len(scope_conflicts)} scope disagreements")
    if type_conflicts:
        problems.append(f"{len(type_conflicts)} type disagreements")

    print()
    if problems:
        for p in problems:
            print(f"FAIL  {p}", file=sys.stderr)
        return 1
    print("oracle OK")
    return 0


# --------------------------------------------------------------------------- corpus


def cmd_corpus_build(args: argparse.Namespace) -> int:
    root = paths.docs_root()
    pages_root = root / paths.DOCS_SUBDIR
    if not pages_root.exists():
        print(
            f"missing {pages_root}\nRun: uv run python scripts/fetch_source_docs.py",
            file=sys.stderr,
        )
        return 2
    if not paths.SETTINGS_JSONL.exists():
        print("build the oracle first: structured-extract oracle build", file=sys.stderr)
        return 2

    names, aliases = _load_oracle_names()

    sections: list[corpus_mod.Section] = []
    for rel, text in corpus_mod.iter_pages(pages_root):
        sections.extend(corpus_mod.split_sections(rel, text))
    sections.extend(
        corpus_mod.reference_sections(
            root / paths.CONFIG_REFERENCE_PAGE,
            paths.CONFIG_REFERENCE_PAGE.removeprefix(paths.DOCS_SUBDIR + "/"),
        )
    )

    buckets: dict[str, list[corpus_mod.Section]] = {}
    eligible = 0
    for section in sections:
        if section.stratum != "reference":
            if not MIN_SECTION_CHARS <= section.n_chars <= MAX_SECTION_CHARS:
                continue
            mentions = corpus_mod.find_mentions(section.text, names, aliases)
            if not mentions:
                continue
        else:
            mentions = corpus_mod.find_mentions(section.text, names, aliases)
        eligible += 1
        buckets.setdefault(corpus_mod.bucket_for(section, mentions), []).append(section)

    print(f"sections: {len(sections)} total, {eligible} eligible")
    for line in corpus_mod.sampling_report(buckets, QUOTAS):
        print(line)

    sampled = corpus_mod.sample_sections(buckets, QUOTAS, args.seed)
    documents = corpus_mod.build_documents(sampled, names, aliases)

    if paths.CORPUS_DOCUMENTS.exists():
        for stale in paths.CORPUS_DOCUMENTS.glob("*.md"):
            stale.unlink()
    paths.CORPUS_DOCUMENTS.mkdir(parents=True, exist_ok=True)
    for section, doc in zip(sampled, documents, strict=True):
        (paths.CORPUS_DOCUMENTS / f"{doc.doc_id}.md").write_text(
            section.text + "\n", encoding="utf-8", newline="\n"
        )

    n = jsonl.write(paths.CORPUS_JSONL, (d.to_json() for d in documents))
    shape = dict(Counter(d.stratum for d in documents))
    print(f"corpus.jsonl {n} documents, seed {args.seed}, {shape}")
    return 0


def cmd_corpus_verify(args: argparse.Namespace) -> int:
    """Re-hash every vendored document against the manifest. Offline."""
    rows = jsonl.read_list(paths.CORPUS_JSONL)
    problems: list[str] = []

    for row in rows:
        path = paths.CORPUS_DOCUMENTS / f"{row['doc_id']}.md"
        if not path.exists():
            problems.append(f"{row['doc_id']}: document file missing")
            continue
        text = path.read_text(encoding="utf-8").rstrip("\n")
        if corpus_mod.sha256_of(text) != row["sha256"]:
            problems.append(f"{row['doc_id']}: sha256 mismatch against the manifest")
        if len(text) != row["n_chars"]:
            problems.append(f"{row['doc_id']}: n_chars {row['n_chars']} but file has {len(text)}")

    orphans = {p.stem for p in paths.CORPUS_DOCUMENTS.glob("*.md")} - {r["doc_id"] for r in rows}
    if orphans:
        problems.append(f"{len(orphans)} document files are not in the manifest: {sorted(orphans)}")

    counts = Counter(
        r["stratum"]
        if r["stratum"] == "reference"
        else f"{r['stratum']}-{'signal' if r['has_signal'] else 'distractor'}"
        for r in rows
    )
    if counts != Counter(QUOTAS):
        problems.append(f"bucket counts {dict(counts)} != quotas {QUOTAS}")

    # Byte-identical documents are not a corruption -- the docs really do
    # publish some sections at two paths -- but they are not two observations
    # either. Their cache keys collide, so both arms of the "pair" get the same
    # response, and any narrative-vs-extension comparison is quietly sharing a
    # document. Reported loudly and never allowed to be silent.
    by_hash: dict[str, list[str]] = {}
    for row in rows:
        by_hash.setdefault(row["sha256"], []).append(row["doc_id"])
    duplicates = {h: ids for h, ids in by_hash.items() if len(ids) > 1}

    print(f"corpus.jsonl {len(rows)} documents {dict(counts)}")
    if duplicates:
        n_extra = sum(len(ids) - 1 for ids in duplicates.values())
        print(
            f"NOTE  {len(rows)} documents but only {len(by_hash)} distinct texts "
            f"({n_extra} duplicate{'s' if n_extra > 1 else ''})"
        )
        for ids in duplicates.values():
            paired = [next(r for r in rows if r["doc_id"] == i) for i in ids]
            print(f"      {' == '.join(ids)}  ({paired[0]['n_chars']} chars, identical)")
            for row in paired:
                print(f"        {row['stratum']:<10} {row['source_path']}")
            if len({r["stratum"] for r in paired}) > 1:
                print("        ^ spans two strata: both are inflated by the same text")
    if problems:
        for p in problems:
            print(f"FAIL  {p}", file=sys.stderr)
        return 1
    print("corpus OK")
    return 0


def cmd_corpus_stats(args: argparse.Namespace) -> int:
    rows = jsonl.read_list(paths.CORPUS_JSONL)
    print(f"{'stratum':<12} {'docs':>5} {'chars/doc':>10} {'mentions/doc':>13} {'distractors':>12}")
    for stratum in corpus_mod.STRATA:
        group = [r for r in rows if r["stratum"] == stratum]
        if not group:
            continue
        chars = sorted(r["n_chars"] for r in group)
        mentions = [len(r["mentioned_names"]) for r in group]
        distractors = sum(any(m["distractor"] for m in r["mentions"]) for r in group)
        print(
            f"{stratum:<12} {len(group):>5} {chars[len(chars) // 2]:>10} "
            f"{sum(mentions) / len(group):>13.2f} {distractors:>12}"
        )

    every = {n for r in rows for n in r["mentioned_names"]}
    zero = sum(1 for r in rows if not r["mentioned_names"])
    print()
    print(f"distinct settings mentioned anywhere in the corpus  {len(every)}")
    print(f"documents mentioning no known setting               {zero}")
    exactly_one = sum(1 for r in rows if len(r["mentioned_names"]) == 1)
    print(f"documents mentioning exactly one                    {exactly_one}")
    top = Counter(n for r in rows for n in r["mentioned_names"]).most_common(8)
    print(f"most-mentioned: {', '.join(f'{n} x{c}' for n, c in top)}")
    return 0


# --------------------------------------------------------------------------- arms


def cmd_arms_verify(args: argparse.Namespace) -> int:
    """Resolve every pinned model id against the public catalogue. No key, no spend."""
    try:
        checks = arms_mod.verify()
    except RuntimeError as exc:
        print(f"FAIL  {exc}", file=sys.stderr)
        return 2

    for check in checks:
        arm = check.arm
        status = "OK  " if check.ok else "FAIL"
        knobs = ",".join(
            [
                "temperature" if check.live_temperature else "-",
                "seed" if check.live_seed else "-",
                "reasoning" if arm.reasoning else "-",
            ]
        )
        print(f"{status} {arm.key}  {arm.model_id}")
        print(
            f"       structured_outputs={check.structured_outputs} "
            f"${check.live_price_in:g}/${check.live_price_out:g} per M  "
            f"ctx={check.context_length:,}  max_out={check.max_completion_tokens}  {knobs}"
        )
        for problem in check.problems:
            print(f"       - {problem}")

    failed = [c for c in checks if not c.ok]
    print()
    if failed:
        print(f"FAIL  {len(failed)} of {len(checks)} arms did not verify", file=sys.stderr)
        return 1
    print(f"arms OK  ({len(checks)} hosted arms resolve, all advertise structured outputs)")
    return 0


def _cost_from_measured(results_path, corpus: list[dict]) -> int:
    """Extrapolate the full grid from what a pilot was actually billed.

    Guessing from pinned prices was wrong by 1.94x overall on the second pilot.
    This uses ``usage.cost`` instead, so the only guess left is whether the
    pilot slice resembles the corpus -- and that is measurable too, so both
    bounds are printed rather than one confident number.
    """
    measured = jsonl.read_list(results_path)
    chars = {row["doc_id"]: row["n_chars"] for row in corpus}
    seen = {row["doc_id"] for row in measured}
    missing = sorted(seen - set(chars))
    if missing:
        print(f"FAIL  {len(missing)} result rows name documents not in the corpus", file=sys.stderr)
        return 2

    required = {"cost_reported", "cost_estimated", "prompt", "arm"}
    absent = sorted(required - set(measured[0])) if measured else sorted(required)
    if absent:
        print(
            f"FAIL  {results_path.name} predates the current results schema "
            f"(no {', '.join(absent)}).\n"
            f"      Re-run to rewrite it from the cache -- free, no network:\n"
            f"      structured-extract extract run --pilot <N>",
            file=sys.stderr,
        )
        return 2

    by_doc = len(chars) / len(seen)
    by_chars = sum(chars.values()) / sum(chars[d] for d in seen)
    billed = sum(r["cost_reported"] for r in measured)
    predicted = sum(r["cost_estimated"] for r in measured)
    prompts = sorted({r["prompt"] for r in measured})
    arms_seen = sorted({r["arm"] for r in measured})

    print(f"measured from {results_path.name}: {len(measured)} calls over {len(seen)} documents")
    print(f"  arms {', '.join(arms_seen)} x prompts {', '.join(prompts)}")
    print(f"  billed     ${billed:.4f}")
    print(f"  predicted  ${predicted:.4f}  ({billed / predicted:.2f}x out)" if predicted else "")
    print()
    print(f"  pilot documents average {sum(chars[d] for d in seen) / len(seen):,.0f} chars,")
    print(f"  the corpus averages {sum(chars.values()) / len(chars):,.0f}")
    print()
    print("full grid, same arms and prompts, extrapolated from the bill:")
    print(f"  by document count  x{by_doc:.1f}   ${billed * by_doc:.2f}")
    print(f"  by total chars     x{by_chars:.2f}  ${billed * by_chars:.2f}")
    print()
    print(
        "Take the higher one. Output tokens do not scale with document length --\n"
        "reasoning does what it likes -- so neither bound is a guarantee."
    )
    return 0


def cmd_arms_cost(args: argparse.Namespace) -> int:
    """Estimated spend for the full grid, from the committed corpus and pinned prices."""
    rows = jsonl.read_list(paths.CORPUS_JSONL)
    if args.measured:
        return _cost_from_measured(args.measured, rows)
    # chars/4 is a rough tokenizer-agnostic estimate and is labelled as one; the
    # published cost figures come from the providers' own reported token counts.
    doc_tokens = sum(r["n_chars"] for r in rows) / 4
    variants = args.prompts if args.prompts else len(extract_mod.PROMPTS)
    prompt_tokens = (doc_tokens + args.overhead * len(rows)) * variants
    completion_tokens = args.completion * len(rows) * variants
    inflate = 1 + args.repair_rate

    print(f"corpus {len(rows)} documents, ~{doc_tokens:,.0f} document tokens (chars/4, estimate)")
    print(f"{variants} prompt variant(s): {', '.join(sorted(extract_mod.PROMPTS))}")
    print(f"assuming {args.overhead} tokens of prompt+schema and {args.completion} out per call,")
    print(f"and a {args.repair_rate:.0%} repair rate\n")

    total = 0.0
    for arm in arms_mod.HOSTED:
        cost = arm.cost(prompt_tokens * inflate, completion_tokens * inflate)
        total += cost
        print(f"  {arm.key}  {arm.model_id:<30} ${cost:7.3f}")
    print(f"  {'':4}  {'full hosted grid':<30} ${total:7.3f}")
    print(
        f"  {'':4}  {'pilot (' + str(args.pilot) + ' documents)':<30} "
        f"${total * args.pilot / len(rows):7.3f}"
    )
    print()
    print(
        "This EXCLUDES reasoning tokens. Reasoning is left at each provider's default\n"
        "(see extract.build_payload) and bills as completion tokens, so four of the five\n"
        "arms can exceed this. How much is exactly what the pilot is for -- the figure\n"
        "published in the README will come from reported token counts, not from here."
    )
    return 0


# --------------------------------------------------------------------------- extract


def _pilot_documents(rows: list[dict], n: int) -> list[dict]:
    """A small, fixed, stratified slice: every bucket represented, no sampling.

    Taking the first document of each bucket in manifest order keeps the pilot
    reproducible and keeps it honest -- it must include a distractor and a
    reference row, or it cannot show that the outcome columns tell them apart.
    """
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        key = (
            row["stratum"]
            if row["stratum"] == "reference"
            else f"{row['stratum']}-{'signal' if row['has_signal'] else 'distractor'}"
        )
        buckets.setdefault(key, []).append(row)

    picked: list[dict] = []
    while len(picked) < n:
        added = False
        for key in QUOTAS:
            pool = buckets.get(key, [])
            index = sum(1 for p in picked if p["doc_id"] in {q["doc_id"] for q in pool})
            if index < len(pool) and len(picked) < n:
                picked.append(pool[index])
                added = True
        if not added:
            break
    return picked


def cmd_extract_run(args: argparse.Namespace) -> int:
    """Run the grid. Replays from the committed cache unless ``--live`` is given."""
    rows = jsonl.read_list(paths.CORPUS_JSONL)
    if args.pilot:
        rows = _pilot_documents(rows, args.pilot)
    if args.doc:
        known = {r["doc_id"] for r in rows}
        unknown = sorted(set(args.doc) - known)
        if unknown:
            print(
                f"FAIL  no such document in this selection: {', '.join(unknown)}", file=sys.stderr
            )
            return 2
        rows = [r for r in rows if r["doc_id"] in set(args.doc)]
    selected = [arms_mod.BY_KEY[k] for k in args.arm] if args.arm else list(arms_mod.HOSTED)
    prompts = args.prompt or list(extract_mod.PROMPTS)

    if args.live and not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "--live needs OPENROUTER_API_KEY in the environment (put it in .env, "
            "never on the command line).",
            file=sys.stderr,
        )
        return 2

    pairs = len(rows) * len(selected) * len(prompts)
    print(f"{len(rows)} documents x {len(selected)} arms x {len(prompts)} prompts = {pairs} pairs")
    print(f"prompts: {', '.join(prompts)}")
    print(f"mode: {'LIVE (this spends money)' if args.live else 'replay from cache'}\n")

    results: list[extract_mod.ExtractionRow] = []
    for prompt in prompts:
        for arm in selected:
            for row in rows:
                path = paths.CORPUS_DOCUMENTS / f"{row['doc_id']}.md"
                document = path.read_text(encoding="utf-8")
                try:
                    result, _ = extract_mod.extract_document(
                        arm,
                        row["doc_id"],
                        document,
                        cache_dir=paths.CACHE_DIR,
                        allow_live=args.live,
                        prompt=prompt,
                    )
                except extract_mod.MissingAPIKey as exc:
                    print(f"FAIL  {exc}", file=sys.stderr)
                    return 2
                results.append(result)
                if args.verbose:
                    print(
                        f"  {prompt:<15} {arm.key} {result.doc_id:<22} "
                        f"{result.outcome:<22} repair={result.repair_used!s:<5} "
                        f"{result.finish_reason:<10} n={result.n_settings:<3} "
                        f"${result.cost_reported:.5f}"
                    )

    # A narrowed run writes a *different* file unless told otherwise. `--arm H5`
    # against the pilot path would replace 80 rows with 16 and destroy the other
    # 64, which is a one-keystroke way to lose a paid experiment.
    if args.out:
        out = args.out
    elif args.arm or args.doc or args.prompt:
        out = paths.RESULTS_JSONL.with_name("probe.jsonl")
        print(f"(narrowed run -> {out.name}, so the full results file is left alone)")
    else:
        out = (
            paths.RESULTS_JSONL if not args.pilot else paths.RESULTS_JSONL.with_name("pilot.jsonl")
        )
    jsonl.write(out, (r.to_json() for r in results))

    print()
    print(f"{'prompt':<15} {'arm':<5} {'outcome':<22} {'n':>4}")
    for prompt in prompts:
        for arm in selected:
            counts = Counter(r.outcome for r in results if r.arm == arm.key and r.prompt == prompt)
            for outcome, n in counts.most_common():
                print(f"{prompt:<15} {arm.key:<5} {outcome:<22} {n:>4}")

    print()
    header = f"{'prompt':<15} {'arm':<5} {'cost':>9} {'repairs':>8} {'tok in':>9} {'tok out':>9}"
    print(f"{header} {'think':>8} {'settings':>9}")
    for prompt in prompts:
        for arm in selected:
            group = [r for r in results if r.arm == arm.key and r.prompt == prompt]
            if not group:
                continue
            print(
                f"{prompt:<15} {arm.key:<5} ${sum(r.cost_reported for r in group):8.4f} "
                f"{sum(r.repair_used for r in group):>8} "
                f"{sum(r.prompt_tokens for r in group):>9,} "
                f"{sum(r.completion_tokens for r in group):>9,} "
                f"{sum(r.reasoning_tokens for r in group):>8,} "
                f"{sum(r.n_settings for r in group):>9}"
            )

    # The whole point of running two prompts: the same arms, the same documents,
    # a different specification of what is being asked for.
    if len(prompts) > 1:
        print()
        print("settings returned, by prompt (the oracle has not scored these yet)")
        for prompt in prompts:
            group = [r for r in results if r.prompt == prompt]
            answered = [r for r in group if not r.error]
            total = sum(r.n_settings for r in group)
            per = total / len(answered) if answered else 0.0
            print(f"  {prompt:<15} {total:>5} across {len(answered):>3} answered  ({per:.2f}/doc)")
    billed = sum(r.cost_reported for r in results)
    estimated = sum(r.cost_estimated for r in results)
    print(f"\ntotal ${billed:.4f} billed  ->  {out}")

    # The second pilot printed $0.0382 and OpenRouter charged $0.0743. Pinned
    # catalogue price x reported tokens does not reconstruct the bill, in either
    # direction -- 2.94x low on H1, 3.8x high on H4 -- because reasoning tokens
    # are not consistently inside completion_tokens and providers round their
    # own way. usage.cost is authoritative; the estimate only cross-checks it,
    # and a run says so out loud rather than leaving it in the JSONL.
    if estimated and abs(billed - estimated) / max(billed, estimated) > 0.05:
        print(
            f"      ${estimated:.4f} was what the pinned prices predicted "
            f"({billed / estimated:.2f}x out). Publish the billed figure."
        )
        for arm in selected:
            group = [r for r in results if r.arm == arm.key]
            b, e = sum(r.cost_reported for r in group), sum(r.cost_estimated for r in group)
            if e and abs(b - e) / max(b, e) > 0.05:
                print(f"        {arm.key}  billed ${b:.5f}  predicted ${e:.5f}  {b / e:.2f}x")

    # A run where nothing was answered must say *why* on the terminal. The first
    # live pilot returned 40 rows of `provider_unavailable` and the reason -- a
    # 402 saying the account had never bought credits -- was only in the JSONL.
    # Distinct messages, not one per row: 40 copies of one error is not a report.
    failed = [r for r in results if r.error]
    if failed:
        print()
        print(f"{len(failed)} of {len(results)} calls returned no answer:")
        for message, group in _group_errors(failed).items():
            arms = ", ".join(sorted({r.arm for r in group}))
            print(f"  [{len(group):>3} rows · arms {arms}] {message}")
        if len(failed) == len(results):
            print("\nNothing was scored. Fix the error above before reading these results.")
            return 1
    return 0


def _group_errors(rows: list[extract_mod.ExtractionRow]) -> dict[str, list]:
    """Collapse identical provider errors, keeping the provider's own wording.

    The message is the useful part -- OpenRouter's 402 body names the remedy and
    the URL -- so it is reproduced rather than replaced with a guess at what it
    meant.
    """
    grouped: dict[str, list] = {}
    for row in rows:
        message = (row.error or "").strip()
        try:  # OpenRouter wraps the real message in a JSON envelope.
            _, _, body = message.partition(": ")
            inner = json.loads(body)["error"]["message"]
            message = f"{message.split(':', 1)[0]}: {inner}"
        except (ValueError, KeyError, TypeError):
            pass
        grouped.setdefault(message, []).append(row)
    return grouped


def cmd_extract_cache(args: argparse.Namespace) -> int:
    """Say what a run would replay and what it would buy, before it buys anything.

    The cache is keyed by a hash of the exact request, so re-running after a
    crash cannot double-charge: a call already answered is found and replayed.
    This command makes that checkable rather than something to take on trust,
    which matters most straight after a run died part-way through.
    """
    rows = jsonl.read_list(paths.CORPUS_JSONL)
    if args.pilot:
        rows = _pilot_documents(rows, args.pilot)
    if args.doc:
        rows = [r for r in rows if r["doc_id"] in set(args.doc)]
    selected = [arms_mod.BY_KEY[k] for k in args.arm] if args.arm else list(arms_mod.HOSTED)
    prompts = args.prompt or list(extract_mod.PROMPTS)

    on_disk = (
        {p.stem for p in paths.CACHE_DIR.rglob("*.json")} if paths.CACHE_DIR.exists() else set()
    )
    planned: dict[str, tuple[str, str, str]] = {}
    for prompt in prompts:
        system = extract_mod.PROMPTS[prompt]
        for arm in selected:
            for row in rows:
                text = (paths.CORPUS_DOCUMENTS / f"{row['doc_id']}.md").read_text(encoding="utf-8")
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ]
                key = extract_mod.cache_key(arm.model_id, extract_mod.build_payload(arm, messages))
                planned[key] = (prompt, arm.key, row["doc_id"])

    cached = sorted(planned[k] for k in planned.keys() & on_disk)
    orphans = on_disk - planned.keys()

    print(
        f"{len(planned)} first-pass calls planned "
        f"({len(rows)} documents x {len(selected)} arms x {len(prompts)} prompts)"
    )
    print(f"  already cached, will replay for $0.00   {len(cached)}")
    print(f"  not cached, will be billed by --live    {len(planned) - len(cached)}")
    for prompt, arm, doc_id in cached:
        print(f"      replay  {prompt:<15} {arm:<4} {doc_id}")
    if orphans:
        print(f"\n  {len(orphans)} cached responses match no planned call.")
        print("  Repair calls look like this, and so does anything left by an older")
        print("  contract. They are inert -- nothing reads them -- but if the schema")
        print("  changed they are dead weight and can be deleted.")
    print("\nA crashed run is safe to repeat: the cache is keyed by the exact request,")
    print("so every call already answered is replayed rather than bought again.")
    return 0


# --------------------------------------------------------------------------- labels


def cmd_labels_init(args: argparse.Namespace) -> int:
    """Generate (or regenerate) the worksheet. Never discards a judgement."""
    corpus = jsonl.read_list(paths.CORPUS_JSONL)
    # Every prose document the pilot reads is pinned into the label set. The
    # pilot is what gets looked at first and argued about; leaving its documents
    # on the proxy means the fastest feedback loop is the least trustworthy one.
    pinned = tuple(
        row["doc_id"]
        for row in _pilot_documents(corpus, args.pin_pilot)
        if row["stratum"] != "reference"
    )
    fresh = labels_mod.build(corpus, n=args.size, seed=args.seed, pin=pinned)
    merged = labels_mod.merge(fresh, labels_mod.load())

    paths.LABELS_DIR.mkdir(parents=True, exist_ok=True)
    labels_mod.save(merged)
    documents = {
        label.doc_id: (paths.CORPUS_DOCUMENTS / f"{label.doc_id}.md").read_text(encoding="utf-8")
        for label in merged
    }
    paths.LABELS_WORKSHEET.write_text(
        labels_mod.worksheet_markdown(merged, documents), encoding="utf-8", newline="\n"
    )

    kept = sum(1 for label in merged if label.labelled)
    chars = sum(label.n_chars for label in merged)
    print(f"{len(merged)} sections, seed {args.seed}, {chars:,} chars to read")
    for bucket, n in sorted(Counter(label.bucket for label in merged).items()):
        print(f"  {bucket:<22} {n:>3}")
    print()
    print(f"already judged {kept}, to do {len(merged) - kept}")
    print(f"  read   {paths.LABELS_WORKSHEET}")
    print(f"  write  {paths.LABELS_JSONL}")
    return 0


def cmd_labels_verify(args: argparse.Namespace) -> int:
    """Check the judgements for the mistakes a labeller can actually make."""
    labels = labels_mod.load()
    if not labels:
        print("no label set yet. Run: structured-extract labels init", file=sys.stderr)
        return 2

    oracle = score_mod.load_oracle()
    problems = labels_mod.validate(labels, oracle.resolve)
    stats = labels_mod.coverage(labels)

    print(f"{stats['labelled']} of {stats['total']} sections judged")
    print(f"  document at least one setting   {stats['documents_something']}")
    print(f"  correctly empty                 {stats['correctly_empty']}")
    print(f"  settings named in total         {stats['settings_labelled']}")
    print(f"  cross-references recorded       {stats['cross_references']}")

    if problems:
        print()
        for problem in problems:
            print(f"FAIL  {problem}", file=sys.stderr)
        return 1
    remaining = stats["total"] - stats["labelled"]
    if remaining:
        print()
        print(f"{remaining} still to judge -- not usable for scoring yet")
        return 0
    print()
    print("labels OK -- complete and consistent with the oracle")
    return 0


# --------------------------------------------------------------------------- score


def _stale_results_reason(results: list[dict]) -> str | None:
    """Why this results file cannot be scored by the current code, in one line.

    Two different kinds of staleness, and they cost different amounts to fix.
    A missing *row* field (``settings``, ``cost_reported``) is free: the request
    was identical, so a replay rebuilds the file from the committed cache. A
    missing *record* field means the request contract itself changed, the cache
    keys no longer match, and the answers have to be bought again.
    """
    if not results:
        return None
    row_fields = {"settings", "cost_reported", "prompt", "arm"}
    absent = sorted(row_fields - set(results[0]))
    if absent:
        return (
            f"predates the current results schema (no {', '.join(absent)}).\n"
            f"      Re-run to rewrite it from the cache -- free, no network:\n"
            f"      structured-extract extract run --pilot <N>"
        )
    record_fields = {"default_kind", "default_value", "default_evidence"}
    for row in results:
        for record in row["settings"]:
            missing = sorted(record_fields - set(record))
            if missing:
                return (
                    f"was produced before the schema gained {', '.join(missing)}.\n"
                    f"      The request contract changed, so the cache cannot answer this --\n"
                    f"      these records have to be bought again:\n"
                    f"      structured-extract extract run --pilot <N> --live"
                )
    return None


def cmd_score_run(args: argparse.Namespace) -> int:
    """Score a results file against the oracle. Offline, free, no API key."""
    results = jsonl.read_list(args.results)
    stale = _stale_results_reason(results)
    if stale:
        print(f"FAIL  {args.results.name} {stale}", file=sys.stderr)
        return 2

    scores = score_mod.score_all(results)
    summaries = score_mod.summarise(scores)

    jsonl.write(paths.SCORES_JSONL, (s.to_json() for s in scores))
    jsonl.write(paths.SUMMARY_JSONL, (s.to_json() for s in summaries))

    print(f"scored {len(scores)} cells from {args.results.name}\n")

    print("what happened  (no_answer is the provider's fault, failed is the model's)")
    head = f"{'prompt':<15} {'arm':<4} {'docs':>5} {'no_ans':>7} {'failed':>7}"
    print(f"{head} {'empty':>6} {'answered':>9}")
    for s in summaries:
        print(
            f"{s.prompt:<15} {s.arm:<4} {s.n_documents:>5} {s.no_answer:>7} "
            f"{s.failed_extraction:>7} {s.answered_empty:>6} {s.answered:>9}"
        )

    print("\nprecision side  (exact: the binary adjudicates, no human involved)")
    head = f"{'prompt':<15} {'arm':<4} {'recs':>5} {'halluc':>7} {'halluc%':>8}"
    print(f"{head} {'type%':>7} {'scope%':>7} {'ground%':>8} {'doc-only':>9}")
    for s in summaries:
        print(
            f"{s.prompt:<15} {s.arm:<4} {s.records_returned:>5} {s.records_hallucinated:>7} "
            f"{s.hallucination_rate:>7.0%} {s.type_accuracy:>7.0%} "
            f"{s.scope_accuracy:>7.0%} {s.grounding_rate:>8.0%} "
            f"{s.records_documented_not_in_binary:>9}"
        )
    if any(s.records_documented_not_in_binary for s in summaries):
        print(
            "  doc-only: returned, documented by DuckDB, absent from duckdb_settings().\n"
            "  The model read the docs correctly and the docs are wrong, so these are\n"
            "  not hallucinations and are not scored. See data/labels/."
        )

    print("\ndefaults  (against the reference table, never against this laptop's values)")
    head = f"{'prompt':<15} {'arm':<4} {'kind n':>7} {'kind%':>7}"
    print(f"{head} {'value n':>8} {'value%':>7} {'mach-dep':>9}")
    for s in summaries:
        print(
            f"{s.prompt:<15} {s.arm:<4} {s.default_scorable:>7} "
            f"{s.default_kind_accuracy:>7.0%} {s.default_value_scorable:>8} "
            f"{s.default_value_accuracy:>7.0%} "
            f"{f'{s.machine_dependent_classified}/{s.machine_dependent_seen}':>9}"
        )

    print("\nrecall  (reference rows and hand labels are exact truth; proxy is not)")
    head = f"{'prompt':<15} {'arm':<4} {'ref':>7} {'ref%':>6} {'labelled':>9} {'lab%':>6}"
    print(f"{head} {'proxy%':>7} {'empty ok':>9} {'empty bad':>10}")
    for s in summaries:
        proxy = f"{s.recall_vs_mentioned:.0%}" if s.mentioned_expected else "-"
        print(
            f"{s.prompt:<15} {s.arm:<4} "
            f"{f'{s.reference_found}/{s.reference_expected}':>7} "
            f"{s.reference_recall:>6.0%} "
            f"{f'{s.labelled_found}/{s.labelled_expected}':>9} "
            f"{s.labelled_recall:>6.0%} {proxy:>7} "
            f"{s.empty_correct:>9} {s.empty_wrong:>10}"
        )
    if all(not s.mentioned_expected for s in summaries):
        print("  proxy column is empty: every prose document here is hand-labelled.")

    print("\ncost  (usage.cost as billed, never reconstructed from token prices)")
    for prompt in dict.fromkeys(s.prompt for s in summaries):
        cell = [s for s in summaries if s.prompt == prompt]
        print(f"  {prompt:<15} ${sum(s.cost_reported for s in cell):.4f}")
    print(f"  {'total':<15} ${sum(s.cost_reported for s in summaries):.4f}")

    if args.detail:
        print("\nhallucinated names, most frequent first")
        bad = Counter(r.name for s in scores for r in s.records if r.hallucinated)
        for name, n in bad.most_common(args.detail):
            where = sorted({s.doc_id for s in scores for r in s.records if r.name == name})
            print(f"  {name:<32} x{n:<4} {', '.join(where[:3])}")

    print(f"\n-> {paths.SCORES_JSONL}\n-> {paths.SUMMARY_JSONL}")
    return 0


# --------------------------------------------------------------------------- report


def _provenance(results: list[dict]) -> None:
    """What the numbers below rest on. Printed first, never derived twice."""
    corpus = jsonl.read_list(paths.CORPUS_JSONL)
    by_hash: dict[str, list[str]] = {}
    for row in corpus:
        by_hash.setdefault(row["sha256"], []).append(row["doc_id"])
    duplicates = {h: sorted(ids) for h, ids in by_hash.items() if len(ids) > 1}

    hand = {label.doc_id for label in labels_mod.load() if label.documents is not None}
    reference = {row["doc_id"] for row in corpus if row["stratum"] == "reference"}
    prose = {row["doc_id"] for row in corpus if row["stratum"] != "reference"}

    print("CORPUS")
    print(f"  document records                 {len(corpus)}")
    print(f"  distinct texts                   {len(by_hash)}")
    for ids in duplicates.values():
        strata = {next(r for r in corpus if r["doc_id"] == i)["stratum"] for i in ids}
        across = " (crosses strata)" if len(strata) > 1 else ""
        print(f"    identical: {' == '.join(ids)}{across}")

    print()
    print("TRUTH COVERAGE")
    print(f"  reference-row (exact)            {len(reference)}")
    print(f"  hand-labelled (exact)            {len(hand & prose)}")
    print(f"  mentioned-proxy (estimate)       {len(prose - hand)}")
    print(f"  documents with real truth        {len(reference) + len(hand & prose)}")

    pilot = paths.RESULTS_JSONL.with_name("pilot.jsonl")
    carried = set()
    if pilot.exists():
        carried = {
            (r["arm"], r["prompt"], r["doc_id"]) for r in jsonl.read_list(pilot) if not r["error"]
        }
    replayed = [r for r in results if (r["arm"], r["prompt"], r["doc_id"]) in carried]
    billed = sum(r["cost_reported"] for r in results)

    print()
    print("PAID EXPERIMENT")
    distinct = len({(r["arm"], r["prompt"], r["doc_id"]) for r in results})
    carried_cost = sum(r["cost_reported"] for r in replayed)
    print(f"  result rows                      {len(results)}")
    print(f"  distinct (arm, prompt, doc)      {distinct}")
    print(f"  carried in from the pilot        {len(replayed)}")
    print(f"  total billed                     ${billed:.4f}")
    print(f"    of which carried in            ${carried_cost:.4f}")
    print(f"    incremental for this run       ${billed - carried_cost:.4f}")
    predicted = sum(r["cost_estimated"] for r in results)
    if predicted:
        print(
            f"  pinned prices predicted          ${predicted:.4f}  ({billed / predicted:.2f}x out)"
        )


def cmd_report(args: argparse.Namespace) -> int:
    """The final report: provenance, headline, and the failures behind them."""
    results = jsonl.read_list(args.results)
    stale = _stale_results_reason(results)
    if stale:
        print(f"FAIL  {args.results.name} {stale}", file=sys.stderr)
        return 2

    scores = score_mod.score_all(results)
    summaries = score_mod.summarise(scores)

    _provenance(results)

    print()
    print("HEADLINE  (recall is reference-row + hand-label only; the proxy is below)")
    head = f"{'prompt':<15} {'arm':<4} {'avail':>6} {'halluc':>7} {'recall':>7} {'n':>7}"
    print(f"{head} {'type':>6} {'scope':>6} {'ground':>7} {'cost':>9}")
    for s in summaries:
        print(
            f"{s.prompt:<15} {s.arm:<4} {s.availability:>6.0%} {s.hallucination_rate:>7.0%} "
            f"{s.recall:>7.0%} {f'{s.real_truth_found}/{s.real_truth_expected}':>7} "
            f"{s.type_accuracy:>6.0%} {s.scope_accuracy:>6.0%} {s.grounding_rate:>7.0%} "
            f"${s.cost_reported:>8.4f}"
        )

    print()
    print("PROMPT EFFECT  (hand-labelled prose only -- where the truth is a judgement)")
    labelled_docs = {s.doc_id for s in scores if s.truth_source == "hand-label"}
    print(f"{'arm':<4} {'v1 halluc':>12} {'v2 halluc':>12}   {'v1 recall':>11} {'v2 recall':>11}")
    for arm in dict.fromkeys(s.arm for s in scores):
        cells = {}
        for prompt in dict.fromkeys(s.prompt for s in scores):
            sub = [
                s
                for s in scores
                if s.arm == arm and s.prompt == prompt and s.doc_id in labelled_docs
            ]
            records = [r for s in sub for r in s.records]
            want = sum(len(s.expected) for s in sub)
            got = sum(len(set(s.expected) & {r.canonical for r in s.records}) for s in sub)
            cells[prompt] = (
                f"{sum(r.hallucinated for r in records)}/{len(records)}" if records else "0/0",
                f"{got}/{want}",
            )
        keys = list(cells)
        a, b = cells[keys[0]], cells[keys[1] if len(keys) > 1 else keys[0]]
        print(f"{arm:<4} {a[0]:>12} {b[0]:>12}   {a[1]:>11} {b[1]:>11}")

    print()
    print("PROXY  (40 unlabelled prose documents -- shown, never in the headline)")
    for s in summaries:
        if s.mentioned_expected:
            print(
                f"  {s.prompt:<15} {s.arm:<4} {s.mentioned_found}/{s.mentioned_expected} "
                f"= {s.recall_vs_mentioned:.0%}  (estimate: cannot tell documented from mentioned)"
            )

    print()
    print("FAILURES")
    truncated = [r for r in results if r["outcome"] == "length_truncated"]
    errored = [r for r in results if r["error"]]
    print(f"  length_truncated   {len(truncated)} of {len(results)}")
    for r in sorted(truncated, key=lambda r: -r["cost_reported"])[: args.detail or 10]:
        print(
            f"    {r['arm']} {r['prompt']:<15} {r['doc_id']:<16} "
            f"out={r['completion_tokens']:>6} think={r['reasoning_tokens']:>6} "
            f"${r['cost_reported']:.5f} {r['latency_s']:>6.0f}s"
        )
    if truncated:
        share = sum(r["cost_reported"] for r in truncated) / max(
            sum(r["cost_reported"] for r in results), 1e-9
        )
        print(f"    they are {share:.0%} of total spend")

    print(f"  provider errors    {len(errored)} of {len(results)}")
    for message, group in _group_errors(errored).items():
        arms = ", ".join(sorted({r["arm"] for r in group}))
        print(f"    [{len(group):>4} rows · arms {arms}] {message[:120]}")

    print(f"\n-> {paths.SCORES_JSONL}\n-> {paths.SUMMARY_JSONL}")
    jsonl.write(paths.SCORES_JSONL, (s.to_json() for s in scores))
    jsonl.write(paths.SUMMARY_JSONL, (s.to_json() for s in summaries))
    return 0


# --------------------------------------------------------------------------- wiring


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="structured-extract", description=__doc__)
    sub = parser.add_subparsers(dest="group", required=True)

    oracle = sub.add_parser("oracle", help="ground truth from duckdb_settings() and the docs")
    osub = oracle.add_subparsers(dest="cmd", required=True)
    osub.add_parser("build", help="rebuild the oracle (needs the docs checkout)").set_defaults(
        func=cmd_oracle_build
    )
    verify = osub.add_parser("verify", help="check the committed oracle (offline)")
    verify.add_argument("--detail", action="store_true", help="list every disagreement")
    verify.set_defaults(func=cmd_oracle_verify)

    corpus = sub.add_parser("corpus", help="the sampled extraction corpus")
    csub = corpus.add_subparsers(dest="cmd", required=True)
    build = csub.add_parser("build", help="resample the corpus (needs the docs checkout)")
    build.add_argument("--seed", type=int, default=DEFAULT_SEED)
    build.set_defaults(func=cmd_corpus_build)
    csub.add_parser("verify", help="re-hash documents against the manifest (offline)").set_defaults(
        func=cmd_corpus_verify
    )
    csub.add_parser("stats", help="corpus shape").set_defaults(func=cmd_corpus_stats)

    arms = sub.add_parser("arms", help="the models under test")
    asub = arms.add_subparsers(dest="cmd", required=True)
    asub.add_parser(
        "verify", help="resolve every pinned model id (public endpoint, no key, no spend)"
    ).set_defaults(func=cmd_arms_verify)
    cost = asub.add_parser("cost", help="estimated spend for the grid")
    # Measured, not guessed: the wire schema is ~664 tokens and the longer of
    # the two system prompts ~512, plus the request envelope. It was 780 before
    # the record gained the three default fields.
    cost.add_argument("--overhead", type=int, default=1240, help="prompt+schema tokens per call")
    cost.add_argument("--completion", type=int, default=350, help="output tokens per call")
    cost.add_argument("--repair-rate", type=float, default=0.20)
    cost.add_argument("--pilot", type=int, default=8)
    cost.add_argument(
        "--prompts", type=int, default=0, help="how many prompt variants (default: all of them)"
    )
    cost.add_argument(
        "--measured",
        type=Path,
        metavar="RESULTS.JSONL",
        help="extrapolate from what a pilot was actually billed, not from pinned prices",
    )
    cost.set_defaults(func=cmd_arms_cost)

    extract = sub.add_parser("extract", help="run the extraction grid")
    esub = extract.add_subparsers(dest="cmd", required=True)
    run = esub.add_parser("run", help="replay from the committed cache, or --live to spend")
    run.add_argument("--arm", action="append", choices=sorted(arms_mod.BY_KEY), help="repeatable")
    run.add_argument("--pilot", type=int, metavar="N", help="a fixed stratified slice of N docs")
    run.add_argument(
        "--prompt",
        action="append",
        choices=sorted(extract_mod.PROMPTS),
        help="prompt variant, repeatable; default is every variant",
    )
    run.add_argument(
        "--live",
        action="store_true",
        help="issue real, billed requests for anything not already cached",
    )
    run.add_argument(
        "--doc", action="append", metavar="DOC_ID", help="only these documents, repeatable"
    )
    run.add_argument("--out", type=Path, help="write results here instead of the default file")
    run.add_argument("-v", "--verbose", action="store_true", help="one line per document")
    run.set_defaults(func=cmd_extract_run)

    cache = esub.add_parser(
        "cache", help="what a run would replay vs buy (offline, spends nothing)"
    )
    cache.add_argument("--arm", action="append", choices=sorted(arms_mod.BY_KEY))
    cache.add_argument("--pilot", type=int, metavar="N")
    cache.add_argument("--prompt", action="append", choices=sorted(extract_mod.PROMPTS))
    cache.add_argument("--doc", action="append", metavar="DOC_ID")
    cache.set_defaults(func=cmd_extract_cache)

    labels = sub.add_parser("labels", help="the hand-labelled recall set")
    lsub = labels.add_subparsers(dest="cmd", required=True)
    linit = lsub.add_parser("init", help="generate the worksheet (keeps existing judgements)")
    linit.add_argument("--size", type=int, default=labels_mod.LABEL_SET_SIZE)
    linit.add_argument("--seed", type=int, default=labels_mod.DEFAULT_LABEL_SEED)
    linit.add_argument(
        "--pin-pilot",
        type=int,
        default=8,
        metavar="N",
        help="always include the prose documents of the N-document pilot (0 to disable)",
    )
    linit.set_defaults(func=cmd_labels_init)
    lsub.add_parser("verify", help="check the judgements (offline)").set_defaults(
        func=cmd_labels_verify
    )

    score = sub.add_parser("score", help="score extractions against the oracle")
    ssub = score.add_subparsers(dest="cmd", required=True)
    srun = ssub.add_parser("run", help="score a results file (offline, no key)")
    srun.add_argument(
        "results",
        type=Path,
        nargs="?",
        default=paths.RESULTS_JSONL,
        help="results JSONL from `extract run` (default: the full-grid file)",
    )
    srun.add_argument(
        "--detail",
        type=int,
        nargs="?",
        const=20,
        default=0,
        metavar="N",
        help="also list the N most frequent hallucinated names",
    )
    srun.set_defaults(func=cmd_score_run)

    report = sub.add_parser("report", help="the final report: provenance, headline, failures")
    report.add_argument("results", type=Path, nargs="?", default=paths.RESULTS_JSONL)
    report.add_argument("--detail", type=int, default=10, help="failure rows to list")
    report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
