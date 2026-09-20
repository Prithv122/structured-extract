"""Score extractions against the oracle. This is where counts become results.

The pilot made the case for this module better than any argument could. On
``narrative-0001`` -- a table headed ``COPY ... TO`` Options -- four of five
arms returned 14 records that were schema-valid and verbatim-grounded, and not
one of the 14 is a setting DuckDB has. ``n_settings=14`` and ``n_settings=14``
looked identical in the run summary whether the model had found fourteen real
settings or invented fourteen. Only the oracle separates them.

Four outcomes that must never be conflated
------------------------------------------
``no_answer``
    The provider errored. Nothing was produced, so the row appears in no
    accuracy denominator at all. Counting it as a zero would punish an arm for
    its host being down.
``failed_extraction``
    The model answered, and the answer never validated -- unparseable,
    schema-violating, ungrounded, or truncated. Also excluded from accuracy,
    but it is the arm's own fault and is reported separately.
``answered_empty``
    A validated empty list. On a document that documents nothing this is the
    **correct** answer and scores as such; on one that does, it is a miss.
``answered``
    Records to score, one by one.

What can and cannot be measured yet
-----------------------------------
Everything on the precision side is exact and needs no human: a returned name
either resolves to something ``duckdb_settings()`` knows or it does not, and
its type and scope either match the binary or they do not.

**Recall does not exist yet** for the prose strata, and this module does not
pretend otherwise. The corpus manifest's ``mentioned_names`` says a name
*appears* in the text, which is not the same as the section documenting it --
that distinction is the whole reason the 40-section hand-label set is on the
plan. Anything computed against it is named ``*_vs_mentioned`` and is a proxy
with a known bias: it cannot go above the truth, so it understates recall.

The ``reference`` stratum is the exception. Each of those 35 documents is a
single row of the generated configuration reference table, so the set of
settings it documents is exactly one, and it is recoverable from the row
itself. Those documents are scored for real precision *and* real recall.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import StrEnum

from structured_extract import jsonl, paths
from structured_extract import labels as labels_mod
from structured_extract import schema as S
from structured_extract.corpus import DISTRACTOR_NAMES
from structured_extract.extract import NO_ANSWER, Outcome

#: Outcomes where the model answered but nothing validated. Its own failure,
#: unlike NO_ANSWER, and kept apart from it in every report.
FAILED = frozenset({Outcome.INVALID_AFTER_REPAIR, Outcome.UNPARSEABLE, Outcome.LENGTH_TRUNCATED})

#: Settings whose documented default is a property of the machine, not of
#: DuckDB. ``threads`` is the host's core count, ``max_memory`` a fraction of
#: its RAM, ``TimeZone`` and ``Calendar`` the host locale. The reference table
#: documents the *rule* ("80% of RAM"), so no extracted literal can be scored
#: against it and these are excluded from default accuracy rather than counted
#: wrong. Curated deliberately: a regex over the default column also matches
#: ``custom_profiling_settings``, whose default merely contains the word
#: SYSTEM_PEAK_BUFFER_MEMORY, and that one is a perfectly fixed JSON blob.
MACHINE_DEPENDENT = frozenset(
    {
        "Calendar",
        "TimeZone",
        "max_memory",
        "memory_limit",
        "max_temp_directory_size",
        "threads",
    }
)

#: First cell of a markdown table row: ``| `access_mode` | ...``.
_FIRST_CELL = re.compile(r"^\|\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s*\|")

#: Decoration the reference table puts around a default that carries no meaning:
#: ``` `automatic` ``` and ``automatic`` are the same default.
_DEFAULT_NOISE = "`\"'" + " \t"


def normalise_default(value: str) -> str:
    """Compare defaults on their content, not their markdown.

    The reference table writes defaults inside backticks; a model may or may not
    copy them. Casefolded because ``NULLS LAST`` and ``nulls last`` are the same
    default and marking the second wrong would be a typography complaint.
    Nothing else is touched -- ``512.0 MiB`` does not become ``512MB``, because
    those really are different strings and the docs chose one of them.
    """
    return value.strip().strip(_DEFAULT_NOISE).strip().casefold()


class Status(StrEnum):
    """Which of the four outcomes this (document, arm, prompt) had."""

    NO_ANSWER = "no_answer"
    FAILED_EXTRACTION = "failed_extraction"
    ANSWERED_EMPTY = "answered_empty"
    ANSWERED = "answered"


@dataclass(frozen=True)
class Oracle:
    """``duckdb_settings()`` and the reference table, indexed for scoring."""

    #: lowercased label (name or alias) -> canonical setting name
    canonical: dict[str, str]
    #: canonical name -> the binary's row
    settings: dict[str, dict]
    #: canonical name -> the reference table's row, where one exists
    documented: dict[str, dict]

    def resolve(self, name: str) -> str | None:
        """Canonical name for an extracted label, or ``None`` if the binary has none.

        Matching is case-insensitive because DuckDB itself is: ``SET timezone``
        and ``SET TimeZone`` are the same setting, and only two of the 274 names
        (``Calendar``, ``TimeZone``) are not already lowercase. Treating a case
        difference as a hallucination would be a spelling complaint dressed up
        as a correctness measurement.
        """
        return self.canonical.get(name.strip().lower())

    def is_machine_dependent(self, canonical: str) -> bool:
        return canonical in MACHINE_DEPENDENT


def load_oracle() -> Oracle:
    settings = {row["name"]: row for row in jsonl.read_list(paths.SETTINGS_JSONL)}
    canonical: dict[str, str] = {}
    for name, row in settings.items():
        canonical.setdefault(name.lower(), name)
        for alias in row["aliases"]:
            canonical.setdefault(alias.lower(), name)

    documented: dict[str, dict] = {}
    for row in jsonl.read_list(paths.DOCS_REFERENCE_JSONL):
        target = canonical.get(row["name"].lower())
        if target is not None:
            documented.setdefault(target, row)
    return Oracle(canonical=canonical, settings=settings, documented=documented)


@dataclass
class RecordScore:
    """One extracted record, judged."""

    name: str
    canonical: str | None
    #: The binary has no setting by this name or any alias of it, **and** no
    #: labeller has confirmed the document documents it anyway.
    hallucinated: bool
    #: ``None`` when hallucinated -- there is nothing to compare against.
    input_type_correct: bool | None
    scope_correct: bool | None
    #: Re-checked here rather than trusted: a row can reach the scorer having
    #: failed validation, and the failure analysis wants to know which part.
    evidence_grounded: bool
    #: What the model said the default was, and of what sort.
    default_kind: str
    default_value: str | None
    #: ``None`` when unscorable: a hallucinated name, or a real setting the
    #: reference table does not document (105 of the 274 are in no table).
    #: For a machine-dependent setting the *value* is never compared, only the
    #: classification -- "80% of RAM" has no literal to be right about.
    default_kind_correct: bool | None
    default_value_correct: bool | None
    #: True when the reference table documents this setting's default as a rule.
    default_is_machine_dependent: bool
    #: The binary has no such setting, but a labeller read this section and
    #: confirmed it documents one. The model read the documentation correctly
    #: and the documentation is wrong -- neither a hallucination nor a scorable
    #: record. Three exist: mysql_enable_filter_pushdown (renamed in the binary
    #: to mysql_experimental_filter_pushdown) and two iceberg_* settings with no
    #: equivalent at all.
    documented_not_in_binary: bool = False

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class DocumentScore:
    """One (document, arm, prompt) cell."""

    doc_id: str
    arm: str
    prompt: str
    stratum: str
    status: str
    outcome: str
    records: list[RecordScore] = field(default_factory=list)
    #: Exact ground truth, available only for the reference stratum.
    expected: list[str] = field(default_factory=list)
    #: Proxy ground truth for the prose strata: non-distractor names that appear
    #: in the text. An upper bound on what the section might document.
    mentioned: list[str] = field(default_factory=list)
    #: Where ``expected`` came from. ``"reference-row"`` and ``"hand-label"`` are
    #: real ground truth; ``"mentioned-proxy"`` is not, and is reported apart
    #: from them everywhere rather than averaged in.
    truth_source: str = "mentioned-proxy"
    #: ``True``/``False`` only for an empty answer; ``None`` otherwise.
    empty_was_correct: bool | None = None
    cost_reported: float = 0.0

    @property
    def scored(self) -> bool:
        return self.status in (Status.ANSWERED, Status.ANSWERED_EMPTY)

    @property
    def n_returned(self) -> int:
        return len(self.records)

    @property
    def n_hallucinated(self) -> int:
        return sum(r.hallucinated for r in self.records)

    @property
    def n_real(self) -> int:
        return sum(not r.hallucinated for r in self.records)

    def to_json(self) -> dict:
        row = asdict(self)
        row["records"] = [r.to_json() for r in self.records]
        row["n_returned"] = self.n_returned
        row["n_hallucinated"] = self.n_hallucinated
        row["n_real"] = self.n_real
        return row


def reference_target(text: str) -> str | None:
    """The single setting a ``reference`` document documents.

    Those documents are a heading, the table header, the separator and exactly
    one data row copied verbatim, so the documented setting is the row's first
    cell. This is real ground truth, not a proxy: 35 of the 120 documents can
    be scored for recall today, without waiting for the hand labels.
    """
    for line in reversed(text.strip().splitlines()):
        match = _FIRST_CELL.match(line.strip())
        if match and not set(line.replace("|", "").strip()) <= {"-", ":", " "}:
            return match.group(1)
    return None


def score_default(record: dict, canonical: str | None, oracle: Oracle):
    """Judge the default against the reference table.

    Returns ``(kind_correct, value_correct, is_machine_dependent)``, with
    ``None`` wherever there is nothing to compare against. Three cases are
    deliberately not scored as wrong:

    * a hallucinated setting -- no truth exists;
    * a real setting in no reference table -- 105 of the 274 are in none, and
      the binary does not carry a documented default;
    * the *value* of a machine-dependent default -- "80% of RAM" is a rule, so
      only the classification is scored. Marking a literal comparison wrong
      there would punish a model for the docs' phrasing.

    ``duckdb_settings().value`` is never used. It is this laptop's core count
    and this laptop's RAM, and scoring against it would grade every model on
    one machine.
    """
    if canonical is None:
        return None, None, False
    documented = oracle.documented.get(canonical)
    if documented is None:
        return None, None, False

    machine_dependent = oracle.is_machine_dependent(canonical)
    if machine_dependent:
        expected_kind = "machine_dependent"
    elif documented["default_is_empty_cell"]:
        expected_kind = "absent"
    else:
        expected_kind = "literal"

    kind_correct = record["default_kind"] == expected_kind
    if machine_dependent or expected_kind == "absent":
        return kind_correct, None, machine_dependent

    got = record["default_value"]
    value_correct = got is not None and normalise_default(got) == normalise_default(
        documented["default_value"]
    )
    return kind_correct, value_correct, False


def score_record(
    record: dict,
    document: str,
    oracle: Oracle,
    documented_absent: frozenset[str] = frozenset(),
) -> RecordScore:
    canonical = oracle.resolve(record["name"])
    absent = canonical is None and record["name"].strip().lower() in documented_absent
    truth = oracle.settings.get(canonical) if canonical else None
    grounded = S.normalise_whitespace(record["evidence"]) in S.normalise_whitespace(document)
    kind_ok, value_ok, machine_dependent = score_default(record, canonical, oracle)
    return RecordScore(
        name=record["name"],
        canonical=canonical,
        hallucinated=canonical is None and not absent,
        documented_not_in_binary=absent,
        input_type_correct=None if truth is None else record["input_type"] == truth["input_type"],
        scope_correct=None if truth is None else record["scope"] == truth["scope"],
        evidence_grounded=grounded,
        default_kind=record["default_kind"],
        default_value=record["default_value"],
        default_kind_correct=kind_ok,
        default_value_correct=value_ok,
        default_is_machine_dependent=machine_dependent,
    )


def score_row(
    row: dict,
    corpus: dict[str, dict],
    documents: dict[str, str],
    oracle: Oracle,
    hand_labels: dict[str, list[str]] | None = None,
    absent_labels: dict[str, list[str]] | None = None,
):
    """Score one results row. ``corpus`` and ``documents`` are keyed by doc_id.

    ``hand_labels`` maps doc_id to the settings a human judged that section to
    document. Absent, the prose strata fall back to the proxy and say so.
    """
    hand_labels = hand_labels or {}
    documented_absent = frozenset(
        name.lower() for name in (absent_labels or {}).get(row["doc_id"], [])
    )
    meta = corpus[row["doc_id"]]
    text = documents[row["doc_id"]]
    outcome = row["outcome"]

    if outcome in {o.value for o in NO_ANSWER}:
        status = Status.NO_ANSWER
    elif outcome in {o.value for o in FAILED}:
        status = Status.FAILED_EXTRACTION
    elif not row["settings"]:
        status = Status.ANSWERED_EMPTY
    else:
        status = Status.ANSWERED

    # Ground truth, best available first. A hand label beats the proxy on the
    # prose strata because the proxy cannot tell a documented setting from a
    # cross-referenced one -- on narrative-0001 it gets that exactly backwards.
    expected: list[str] = []
    truth_source = "mentioned-proxy"
    if meta["stratum"] == "reference":
        target = reference_target(text)
        resolved = oracle.resolve(target) if target else None
        if resolved:
            expected, truth_source = [resolved], "reference-row"
    elif (hand := hand_labels.get(row["doc_id"])) is not None:
        expected = sorted({c for name in hand if (c := oracle.resolve(name))})
        truth_source = "hand-label"

    # Distractors are excluded: a document whose only "known" name is `schema`
    # is exactly the case where an empty answer is right, and counting those as
    # things to find would invert the distractor strata's purpose.
    mentioned = sorted(
        {
            c
            for name in meta["mentioned_names"]
            if name not in DISTRACTOR_NAMES and (c := oracle.resolve(name))
        }
    )

    score = DocumentScore(
        doc_id=row["doc_id"],
        arm=row["arm"],
        prompt=row["prompt"],
        stratum=meta["stratum"],
        status=status.value,
        outcome=outcome,
        records=[score_record(r, text, oracle, documented_absent) for r in row["settings"]],
        expected=expected,
        mentioned=mentioned,
        truth_source=truth_source,
        cost_reported=row["cost_reported"],
    )
    if status is Status.ANSWERED_EMPTY:
        # Empty is right when there was nothing to find. For a reference
        # document that is never true; for prose, the proxy is the best
        # available answer until the hand labels exist.
        target_set = mentioned if truth_source == "mentioned-proxy" else expected
        score.empty_was_correct = not target_set
    return score


def score_all(results: list[dict]) -> list[DocumentScore]:
    oracle = load_oracle()
    loaded = labels_mod.load()
    hand = {label.doc_id: label.documents for label in loaded if label.documents is not None}
    absent = {
        label.doc_id: label.documented_not_in_binary
        for label in loaded
        if label.documented_not_in_binary
    }
    corpus = {row["doc_id"]: row for row in jsonl.read_list(paths.CORPUS_JSONL)}
    documents = {
        doc_id: (paths.CORPUS_DOCUMENTS / f"{doc_id}.md").read_text(encoding="utf-8")
        for doc_id in {row["doc_id"] for row in results}
    }
    return [score_row(row, corpus, documents, oracle, hand, absent) for row in results]


@dataclass
class Summary:
    """Aggregate for one (arm, prompt) cell. Every rate names its denominator."""

    arm: str
    prompt: str
    n_documents: int
    no_answer: int
    failed_extraction: int
    answered_empty: int
    answered: int
    records_returned: int
    records_hallucinated: int
    #: Returned, real in the docs, absent from the binary. Not a hallucination
    #: and not scorable -- a finding about DuckDB's documentation.
    records_documented_not_in_binary: int
    records_grounded: int
    type_correct: int
    scope_correct: int
    #: Denominator for type/scope: records that resolved to a real setting.
    records_real: int
    #: Records whose setting the reference table documents, so the default
    #: classification can be judged at all.
    default_scorable: int
    default_kind_correct: int
    #: Narrower still: of the scorable ones, those with a literal default,
    #: where the value itself can be compared.
    default_value_scorable: int
    default_value_correct: int
    #: The four settings the docs describe as a rule. Scored on whether the
    #: model said so, never on a literal it could not know.
    machine_dependent_seen: int
    machine_dependent_classified: int
    empty_correct: int
    empty_wrong: int
    #: Reference stratum only, where ground truth is exact.
    reference_expected: int
    reference_found: int
    #: Prose strata with a hand label: real recall, no proxy involved.
    labelled_expected: int
    labelled_found: int
    #: Prose strata still unlabelled. Shrinks to zero as labelling proceeds.
    mentioned_expected: int
    mentioned_found: int
    cost_reported: float

    @property
    def availability(self) -> float:
        """Share of documents that produced a validated answer of any kind."""
        return (self.answered + self.answered_empty) / self.n_documents if self.n_documents else 0.0

    @property
    def hallucination_rate(self) -> float:
        """Share of returned records the binary has never heard of."""
        return self.records_hallucinated / self.records_returned if self.records_returned else 0.0

    @property
    def type_accuracy(self) -> float:
        return self.type_correct / self.records_real if self.records_real else 0.0

    @property
    def scope_accuracy(self) -> float:
        return self.scope_correct / self.records_real if self.records_real else 0.0

    @property
    def grounding_rate(self) -> float:
        return self.records_grounded / self.records_returned if self.records_returned else 0.0

    @property
    def default_kind_accuracy(self) -> float:
        return self.default_kind_correct / self.default_scorable if self.default_scorable else 0.0

    @property
    def default_value_accuracy(self) -> float:
        n = self.default_value_scorable
        return self.default_value_correct / n if n else 0.0

    @property
    def reference_recall(self) -> float:
        """Real recall. 35 documents, exact ground truth, no human needed."""
        return self.reference_found / self.reference_expected if self.reference_expected else 0.0

    @property
    def labelled_recall(self) -> float:
        """Real recall on the prose strata, against a human judgement."""
        n = self.labelled_expected
        return self.labelled_found / n if n else 0.0

    @property
    def real_truth_expected(self) -> int:
        """Settings to find across documents whose ground truth is not a guess."""
        return self.reference_expected + self.labelled_expected

    @property
    def real_truth_found(self) -> int:
        return self.reference_found + self.labelled_found

    @property
    def recall(self) -> float:
        """**The headline recall.** Reference rows and hand labels only.

        The proxy is excluded by construction rather than by convention, so no
        report can accidentally average an estimate into a measurement. On the
        120-document grid this covers 80 documents: 35 whose answer is a table
        row and 45 a person read. The other 40 are reported beside it, never
        inside it.
        """
        n = self.real_truth_expected
        return self.real_truth_found / n if n else 0.0

    @property
    def recall_vs_mentioned(self) -> float:
        """A proxy, and biased low. See the module docstring before quoting it."""
        return self.mentioned_found / self.mentioned_expected if self.mentioned_expected else 0.0

    def to_json(self) -> dict:
        row = asdict(self)
        row.update(
            availability=round(self.availability, 4),
            hallucination_rate=round(self.hallucination_rate, 4),
            type_accuracy=round(self.type_accuracy, 4),
            scope_accuracy=round(self.scope_accuracy, 4),
            grounding_rate=round(self.grounding_rate, 4),
            default_kind_accuracy=round(self.default_kind_accuracy, 4),
            default_value_accuracy=round(self.default_value_accuracy, 4),
            recall=round(self.recall, 4),
            real_truth_expected=self.real_truth_expected,
            real_truth_found=self.real_truth_found,
            reference_recall=round(self.reference_recall, 4),
            labelled_recall=round(self.labelled_recall, 4),
            recall_vs_mentioned=round(self.recall_vs_mentioned, 4),
        )
        return row


def summarise(scores: list[DocumentScore]) -> list[Summary]:
    """One row per (arm, prompt), in the order the arms were run."""
    out: list[Summary] = []
    for arm, prompt in dict.fromkeys((s.arm, s.prompt) for s in scores):
        cell = [s for s in scores if s.arm == arm and s.prompt == prompt]
        counts = Counter(s.status for s in cell)
        records = [r for s in cell for r in s.records]
        real = [r for r in records if not r.hallucinated]

        found_reference = sum(
            1
            for s in cell
            if s.stratum == "reference"
            and s.expected
            and s.expected[0] in {r.canonical for r in s.records}
        )
        expected_reference = sum(1 for s in cell if s.stratum == "reference" and s.expected)

        # Recall over the prose strata, from the best truth each document has.
        # A hand-labelled document is scored against what a human said it
        # documents; only an unlabelled one falls back to the proxy. Averaging
        # the two would hide which is which, so they are separate denominators
        # and the proxy one shrinks to zero as labelling progresses.
        prose = [s for s in cell if s.stratum != "reference"]
        labelled = [s for s in prose if s.truth_source == "hand-label"]
        unlabelled = [s for s in prose if s.truth_source == "mentioned-proxy"]

        def found(scores, target):
            return sum(
                len(set(target(s)) & {r.canonical for r in s.records if r.canonical})
                for s in scores
            )

        labelled_expected = sum(len(s.expected) for s in labelled)
        labelled_found = found(labelled, lambda s: s.expected)
        mentioned_expected = sum(len(s.mentioned) for s in unlabelled)
        mentioned_found = found(unlabelled, lambda s: s.mentioned)

        out.append(
            Summary(
                arm=arm,
                prompt=prompt,
                n_documents=len(cell),
                no_answer=counts.get(Status.NO_ANSWER.value, 0),
                failed_extraction=counts.get(Status.FAILED_EXTRACTION.value, 0),
                answered_empty=counts.get(Status.ANSWERED_EMPTY.value, 0),
                answered=counts.get(Status.ANSWERED.value, 0),
                records_returned=len(records),
                records_hallucinated=sum(r.hallucinated for r in records),
                records_documented_not_in_binary=sum(r.documented_not_in_binary for r in records),
                records_grounded=sum(r.evidence_grounded for r in records),
                type_correct=sum(bool(r.input_type_correct) for r in real),
                scope_correct=sum(bool(r.scope_correct) for r in real),
                records_real=len(real),
                default_scorable=sum(r.default_kind_correct is not None for r in records),
                default_kind_correct=sum(r.default_kind_correct is True for r in records),
                default_value_scorable=sum(r.default_value_correct is not None for r in records),
                default_value_correct=sum(r.default_value_correct is True for r in records),
                machine_dependent_seen=sum(r.default_is_machine_dependent for r in records),
                machine_dependent_classified=sum(
                    r.default_is_machine_dependent and r.default_kind == "machine_dependent"
                    for r in records
                ),
                empty_correct=sum(1 for s in cell if s.empty_was_correct is True),
                empty_wrong=sum(1 for s in cell if s.empty_was_correct is False),
                reference_expected=expected_reference,
                reference_found=found_reference,
                labelled_expected=labelled_expected,
                labelled_found=labelled_found,
                mentioned_expected=mentioned_expected,
                mentioned_found=mentioned_found,
                cost_reported=round(sum(s.cost_reported for s in cell), 6),
            )
        )
    return out
