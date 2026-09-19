"""The extraction schema, and the two things it deliberately does not constrain.

``model_json_schema()`` here is the single source of truth: it is what goes into
OpenRouter's ``response_format`` as a JSON Schema, and it is what
``ValidationError`` is raised against afterwards. There is no second, hand-kept
copy of the shape to drift out of sync.

What is constrained
-------------------
``input_type`` and ``scope`` are closed enums, because the binary's vocabulary
for them is closed: ``duckdb_settings()`` reports exactly nine input types and
exactly two scopes across all 280 rows. A model that answers ``"string"`` or
``"session"`` has made a format error, and it should be caught by the decoder
rather than silently scored as a wrong answer.

``name`` is constrained only to *look* like an identifier
(``^[A-Za-z_][A-Za-z0-9_]*$``). That rejects the extremely common
``` `memory_limit` ``` with backticks still attached, which is a real
formatting failure and is counted as one rather than normalised away -- silently
stripping the backticks would inflate ``valid_first_pass`` for every arm.

What is NOT constrained, on purpose
-----------------------------------
**``name`` is not an enum of the 274 known settings.** It would be trivial to
paste the oracle into the schema and make hallucination impossible by
construction. That would also delete the benchmark's primary measurement. The
oracle scores the output; it never reaches the model, the schema or the repair
prompt.

**Grounding is not in the JSON Schema.** ``evidence`` must be a verbatim span of
the source document, which no JSON Schema can express, so it is enforced by a
Pydantic validator reading the document from the validation context. This is the
deliberate split: the decoder enforces *shape*, the validator enforces
*grounding*, and a model can therefore produce output that is perfectly
schema-valid and still fails because it quoted something the document does not
say. Those are separate columns in the results for exactly that reason.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

#: Key under which the source document is passed to ``model_validate(context=...)``.
DOCUMENT_KEY = "document"

#: A quote shorter than this is a word, not evidence.
MIN_EVIDENCE_CHARS = 12

#: DuckDB setting names are SQL identifiers. Backticks, quotes, dots and
#: trailing punctuation all fail here, which is the point.
NAME_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"

_WHITESPACE = re.compile(r"\s+")


def normalise_whitespace(text: str) -> str:
    """Collapse whitespace runs so a re-wrapped quote still matches verbatim.

    Documents are markdown with hard line breaks; a model quoting a sentence
    that spans two source lines will usually join them with a single space. That
    is the same text, so it is accepted. Nothing else is normalised -- casing,
    punctuation, backticks and word order must match the document exactly.
    """
    return _WHITESPACE.sub(" ", text).strip()


class SettingType(StrEnum):
    """Every ``input_type`` ``duckdb_settings()`` reports in 1.5.5, and no others."""

    BOOLEAN = "BOOLEAN"
    VARCHAR = "VARCHAR"
    UBIGINT = "UBIGINT"
    BIGINT = "BIGINT"
    DOUBLE = "DOUBLE"
    FLOAT = "FLOAT"
    INTEGER = "INTEGER"
    UINTEGER = "UINTEGER"
    VARCHAR_ARRAY = "VARCHAR[]"


class Scope(StrEnum):
    """``duckdb_settings().scope``. Two values across all 280 rows."""

    GLOBAL = "GLOBAL"
    LOCAL = "LOCAL"


class SettingRecord(BaseModel):
    """One configuration setting the document documents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        pattern=NAME_PATTERN,
        description=(
            "The configuration setting's name exactly as DuckDB spells it, with no "
            "backticks, quotes or surrounding punctuation. For example: memory_limit"
        ),
    )
    input_type: SettingType = Field(
        description="The SQL type the setting accepts, as DuckDB's own type name."
    )
    scope: Scope = Field(
        description=(
            "GLOBAL if the setting applies to the whole database instance, "
            "LOCAL if it can differ per connection."
        )
    )
    evidence: str = Field(
        description=(
            "A verbatim span copied from the document that shows this setting is "
            "being documented here. Copy the characters exactly; do not paraphrase, "
            "summarise or repair the text."
        ),
    )

    @field_validator("evidence")
    @classmethod
    def evidence_is_verbatim(cls, value: str, info: ValidationInfo) -> str:
        """Reject a quote the document does not contain.

        This is the grounding check, and it is free and exact in the same way the
        oracle is: no judgement, no second model, no human. When the document is
        not supplied in the context the check is skipped, so the schema stays
        usable for a plain shape test.
        """
        if len(normalise_whitespace(value)) < MIN_EVIDENCE_CHARS:
            raise ValueError(
                f"evidence must be at least {MIN_EVIDENCE_CHARS} characters of "
                f"text copied from the document; got {value!r}"
            )
        document = (info.context or {}).get(DOCUMENT_KEY)
        if document is None:
            return value
        if normalise_whitespace(value) not in normalise_whitespace(document):
            raise ValueError(
                "evidence is not a verbatim span of the document: copy the exact "
                "characters from the document instead of paraphrasing"
            )
        return value


class DocumentExtraction(BaseModel):
    """Everything one document says about DuckDB configuration settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    settings: list[SettingRecord] = Field(
        description=(
            "Every configuration setting this document documents. Return an empty "
            "list if the document does not document any -- a document that merely "
            "mentions a word which happens to be a setting name is not documenting "
            "that setting."
        )
    )

    @field_validator("settings")
    @classmethod
    def names_are_unique(cls, value: list[SettingRecord]) -> list[SettingRecord]:
        seen: set[str] = set()
        for record in value:
            if record.name in seen:
                raise ValueError(f"setting {record.name!r} appears more than once")
            seen.add(record.name)
        return value


def _strictify(node: object) -> object:
    """Make Pydantic's JSON Schema satisfy OpenAI-style strict structured outputs.

    Strict mode requires every object to forbid extra properties and to list
    *every* property as required. Pydantic already emits ``required`` for fields
    without defaults and ``additionalProperties: false`` for ``extra="forbid"``,
    so this is belt and braces -- but the strict validator rejects the whole
    request rather than ignoring a stray schema, and a rejected request is an
    arm that silently produces no data. See ``arms.py`` for why that matters.
    """
    if isinstance(node, list):
        return [_strictify(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {key: _strictify(value) for key, value in node.items()}
    if out.get("type") == "object":
        out["additionalProperties"] = False
        if "properties" in out:
            out["required"] = list(out["properties"])
    return out


def _inline_refs(node: object, defs: dict) -> object:
    """Resolve every ``$ref`` in place and drop ``$defs``.

    Pydantic factors enums out into ``$defs`` and refers to them with a ``$ref``
    that sits next to a sibling ``description``. Providers disagree about that:
    some merge the siblings, some ignore them, and some reject the request
    outright. A rejected request is an arm that quietly produces no data, which
    is the exact failure this project already shipped once, so the schema is
    flattened to plain inline objects that all four arms read the same way.
    """
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        target = defs[node["$ref"].rsplit("/", 1)[-1]]
        merged = {**_inline_refs(target, defs)}
        merged.update({k: v for k, v in node.items() if k != "$ref"})
        return merged
    return {k: _inline_refs(v, defs) for k, v in node.items() if k != "$defs"}


def json_schema() -> dict:
    """The JSON Schema sent to the provider, and the one errors are raised against."""
    raw = DocumentExtraction.model_json_schema()
    flat = _inline_refs(raw, raw.get("$defs", {}))
    return _strictify(flat)  # type: ignore[return-value]


def response_format() -> dict:
    """The ``response_format`` block for an OpenRouter chat completion."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "document_extraction",
            "strict": True,
            "schema": json_schema(),
        },
    }
