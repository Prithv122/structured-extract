"""Command line entry point.

Two builders need the upstream docs checkout (``scripts/fetch_source_docs.py``);
the verifiers deliberately do not, so CI and a clean clone can check every
committed artefact with no network and no DuckDB extension downloads.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

from structured_extract import arms as arms_mod
from structured_extract import corpus as corpus_mod
from structured_extract import extract as extract_mod
from structured_extract import jsonl, paths
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

    print(f"corpus.jsonl {len(rows)} documents {dict(counts)}")
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


def cmd_arms_cost(args: argparse.Namespace) -> int:
    """Estimated spend for the full grid, from the committed corpus and pinned prices."""
    rows = jsonl.read_list(paths.CORPUS_JSONL)
    # chars/4 is a rough tokenizer-agnostic estimate and is labelled as one; the
    # published cost figures come from the providers' own reported token counts.
    doc_tokens = sum(r["n_chars"] for r in rows) / 4
    prompt_tokens = doc_tokens + args.overhead * len(rows)
    completion_tokens = args.completion * len(rows)
    inflate = 1 + args.repair_rate

    print(f"corpus {len(rows)} documents, ~{doc_tokens:,.0f} document tokens (chars/4, estimate)")
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
    selected = [arms_mod.BY_KEY[k] for k in args.arm] if args.arm else list(arms_mod.HOSTED)

    if args.live and not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "--live needs OPENROUTER_API_KEY in the environment (put it in .env, "
            "never on the command line).",
            file=sys.stderr,
        )
        return 2

    print(f"{len(rows)} documents x {len(selected)} arms = {len(rows) * len(selected)} pairs")
    print(f"mode: {'LIVE (this spends money)' if args.live else 'replay from cache'}\n")

    results: list[extract_mod.ExtractionRow] = []
    for arm in selected:
        for row in rows:
            document = (paths.CORPUS_DOCUMENTS / f"{row['doc_id']}.md").read_text(encoding="utf-8")
            try:
                result, _ = extract_mod.extract_document(
                    arm,
                    row["doc_id"],
                    document,
                    cache_dir=paths.CACHE_DIR,
                    allow_live=args.live,
                )
            except extract_mod.MissingAPIKey as exc:
                print(f"FAIL  {exc}", file=sys.stderr)
                return 2
            results.append(result)
            if args.verbose:
                print(
                    f"  {arm.key} {result.doc_id:<22} {result.outcome:<22} "
                    f"repair={result.repair_used!s:<5} {result.finish_reason:<10} "
                    f"${result.cost_usd:.5f}"
                )

    out = paths.RESULTS_JSONL if not args.pilot else paths.RESULTS_JSONL.with_name("pilot.jsonl")
    jsonl.write(out, (r.to_json() for r in results))

    print()
    print(f"{'arm':<5} {'outcome':<22} {'n':>4}")
    for arm in selected:
        counts = Counter(r.outcome for r in results if r.arm == arm.key)
        for outcome, n in counts.most_common():
            print(f"{arm.key:<5} {outcome:<22} {n:>4}")
    print()
    print(f"{'arm':<5} {'cost':>9} {'repairs':>8} {'tok in':>9} {'tok out':>9}")
    for arm in selected:
        group = [r for r in results if r.arm == arm.key]
        print(
            f"{arm.key:<5} ${sum(r.cost_usd for r in group):8.4f} "
            f"{sum(r.repair_used for r in group):>8} "
            f"{sum(r.prompt_tokens for r in group):>9,} "
            f"{sum(r.completion_tokens for r in group):>9,}"
        )
    print(f"\ntotal ${sum(r.cost_usd for r in results):.4f}  ->  {out}")
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
    cost.add_argument("--overhead", type=int, default=780, help="prompt+schema tokens per call")
    cost.add_argument("--completion", type=int, default=350, help="output tokens per call")
    cost.add_argument("--repair-rate", type=float, default=0.20)
    cost.add_argument("--pilot", type=int, default=8)
    cost.set_defaults(func=cmd_arms_cost)

    extract = sub.add_parser("extract", help="run the extraction grid")
    esub = extract.add_subparsers(dest="cmd", required=True)
    run = esub.add_parser("run", help="replay from the committed cache, or --live to spend")
    run.add_argument("--arm", action="append", choices=sorted(arms_mod.BY_KEY), help="repeatable")
    run.add_argument("--pilot", type=int, metavar="N", help="a fixed stratified slice of N docs")
    run.add_argument(
        "--live",
        action="store_true",
        help="issue real, billed requests for anything not already cached",
    )
    run.add_argument("-v", "--verbose", action="store_true", help="one line per document")
    run.set_defaults(func=cmd_extract_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
