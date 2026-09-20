"""The arms under test, pinned by exact OpenRouter model id and price.

Why this file exists at all
---------------------------
Project 24 shipped an arm that never executed once: its model id was missing a
suffix, every call 404'd, and the table reported the arm as "no data" rather
than as broken. ``arms verify`` makes that failure impossible to ship. It
resolves every pinned id against ``GET /api/v1/models`` -- a **public**
endpoint, no API key, no spend -- and refuses to pass if an id has vanished, if
the provider no longer advertises structured outputs, or if the price has moved
away from the number this repo publishes.

Pinned prices are not decoration. Every cost figure in the README is computed
from the ``prompt_tokens``/``completion_tokens`` the provider returned times the
price in this file. If OpenRouter reprices a model after the grid is run, the
published cost is still exactly what the run cost; ``arms verify`` then reports
drift so the next reader knows the two no longer agree.

Determinism, and what it cost to get it
---------------------------------------
``temperature=0`` is no longer free at the top of the market. Claude Sonnet 5
advertises neither ``temperature`` nor ``seed``; the GPT-5 reasoning family
takes ``seed`` but not ``temperature``. Including a frontier arm therefore meant
either pretending the knob was set or publishing a grid where one arm could not
be pinned.

The way out was to stop equating "ceiling" with "frontier". DeepSeek V4 Pro is
flagship-class, accepts both controls, and costs a fraction of either. **Every
arm in this grid now advertises both ``temperature`` and ``seed``**, which is a
stronger position than the original line-up and a cheaper one. Each arm still
records what the provider advertises rather than assuming it, the run sends only
the knobs an arm supports, and ``arms verify`` fails if that ever changes --
because the honest version of this note is one a future reader can re-derive.

None of it is load-bearing for reproducibility: every published number replays
from the committed response cache.

Why no ``:free`` ids
--------------------
They are not the same endpoint. ``z-ai/glm-5.2:free`` reports
``structured_outputs=False``, ``response_format=False`` and a 32 k context
against the paid id's 1 M -- it cannot accept the JSON Schema this whole grid is
built on. On top of that, ``:free`` carries OpenRouter's 50-requests/day
account-wide cap, and one arm needs 120 calls before a single repair.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

#: Public model catalogue. No ``Authorization`` header, no spend, no key.
MODELS_URL = "https://openrouter.ai/api/v1/models"

#: Chat completions. The only endpoint the grid calls, and the only one that costs money.
COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"

#: Price drift above this fraction fails ``arms verify``. Providers round prices
#: at more decimal places than they publish, so an exact match is too strict.
PRICE_TOLERANCE = 0.001


@dataclass(frozen=True)
class Arm:
    """One model under test, pinned hard enough that a rerun is the same experiment."""

    key: str
    model_id: str
    label: str
    #: USD per million tokens, as advertised when the grid was pinned.
    price_in: float
    price_out: float
    #: Why this arm is in the grid rather than one of the other 440 models.
    rationale: str
    #: Determinism controls the provider advertises. Filled from the catalogue by
    #: :func:`verify`, and asserted against these expectations.
    supports_temperature: bool = False
    supports_seed: bool = False
    #: Reasoning models bill thinking as completion tokens. Where the provider
    #: allows it the grid turns reasoning off, so the comparison is about
    #: extraction rather than about who was given the larger thinking budget.
    reasoning: bool = False

    def cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """USD for one call, from the token counts the provider reported."""
        return (prompt_tokens * self.price_in + completion_tokens * self.price_out) / 1e6

    def to_json(self) -> dict:
        return {
            "key": self.key,
            "model_id": self.model_id,
            "label": self.label,
            "price_in": self.price_in,
            "price_out": self.price_out,
            "supports_temperature": self.supports_temperature,
            "supports_seed": self.supports_seed,
            "reasoning": self.reasoning,
        }


#: The five hosted arms, holding the *mechanism* constant so that capability is
#: the only thing that varies: every one advertises native structured outputs,
#: so the grid never confuses "the decoder enforced the schema" with "the prompt
#: asked nicely". That contrast belongs to B0/B1, not to H1-H5.
#:
#: Claude Sonnet 5 was the original H1 and was dropped. It is an excellent model
#: and a poor *arm*: at $2.00/$10.00 it was 76% of the grid's cost, and it is the
#: only candidate considered that advertises neither ``temperature`` nor
#: ``seed``. DeepSeek V4 Pro is flagship-class at 7.6x less, accepts both, and
#: its own Flash sibling sits four rows below it -- so the table now carries a
#: within-family comparison for free.
HOSTED: tuple[Arm, ...] = (
    Arm(
        key="H1",
        model_id="deepseek/deepseek-v4-pro",
        label="DeepSeek V4 Pro",
        price_in=0.4223,
        price_out=0.8446,
        rationale=(
            "The ceiling. Without a known-strong arm the grid cannot tell "
            "'this task is hard' from 'these models are small', which is the one "
            "thing only a ceiling buys. Flagship-class, and unlike the frontier "
            "models it takes both temperature and seed."
        ),
        supports_temperature=True,
        supports_seed=True,
        reasoning=True,
    ),
    Arm(
        key="H2",
        model_id="google/gemini-2.5-flash",
        label="Gemini 2.5 Flash",
        price_in=0.30,
        price_out=2.50,
        rationale=(
            "Mid-tier workhorse from a third vendor stack. Its output price is "
            "the highest in the grid, which makes it the arm where a runaway "
            "repair rate would hurt most."
        ),
        supports_temperature=True,
        supports_seed=True,
        reasoning=True,
    ),
    Arm(
        key="H3",
        model_id="openai/gpt-4.1-nano",
        label="GPT-4.1 nano",
        price_in=0.10,
        price_out=0.40,
        rationale=(
            "The small end, where schema violations and invented setting names "
            "should actually appear. Non-reasoning, so its output tokens are the "
            "answer rather than a thinking budget, and it takes temperature=0."
        ),
        supports_temperature=True,
        supports_seed=True,
        reasoning=False,
    ),
    Arm(
        key="H4",
        model_id="openai/gpt-oss-120b",
        label="gpt-oss-120b",
        price_in=0.15,
        price_out=0.60,
        rationale=(
            "Open weights, so it is the like-for-like hosted counterpart to the "
            "L1 Ollama arm: same openness, two orders of magnitude more hardware."
        ),
        supports_temperature=True,
        supports_seed=True,
        reasoning=True,
    ),
    Arm(
        key="H5",
        model_id="z-ai/glm-5.3-flash",
        label="GLM 5.3 Flash",
        price_in=0.090,
        price_out=0.300,
        rationale=(
            "The floor, and the fifth vendor. A very large model served at a "
            "very small price is the case a reader most wants priced: if it "
            "matches the ceiling here, nobody needs the ceiling for this task."
        ),
        supports_temperature=True,
        supports_seed=True,
        reasoning=True,
    ),
)

BY_KEY = {arm.key: arm for arm in HOSTED}


@dataclass
class ArmCheck:
    """What the live catalogue says about one pinned arm."""

    arm: Arm
    found: bool
    structured_outputs: bool = False
    response_format: bool = False
    live_price_in: float = 0.0
    live_price_out: float = 0.0
    live_temperature: bool = False
    live_seed: bool = False
    context_length: int = 0
    max_completion_tokens: int | None = None
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def fetch_catalogue(url: str = MODELS_URL, timeout: float = 30.0) -> dict[str, dict]:
    """Return ``{model_id: model}`` from the public catalogue. No authentication."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"cannot reach {url}: {exc}") from exc
    return {m["id"]: m for m in payload["data"]}


def _drifted(pinned: float, live: float) -> bool:
    if pinned == 0:
        return live != 0
    return abs(live - pinned) / pinned > PRICE_TOLERANCE


def check_arm(arm: Arm, catalogue: dict[str, dict]) -> ArmCheck:
    """Resolve one pinned arm against the live catalogue."""
    model = catalogue.get(arm.model_id)
    if model is None:
        near = sorted(mid for mid in catalogue if mid.startswith(arm.model_id.split("/")[0] + "/"))
        hint = f" ({len(near)} ids from that provider exist)" if near else ""
        return ArmCheck(
            arm=arm,
            found=False,
            problems=[f"model id {arm.model_id!r} does not resolve{hint}"],
        )

    params = set(model.get("supported_parameters") or [])
    pricing = model["pricing"]
    top = model.get("top_provider") or {}
    check = ArmCheck(
        arm=arm,
        found=True,
        structured_outputs="structured_outputs" in params,
        response_format="response_format" in params,
        live_price_in=float(pricing["prompt"]) * 1e6,
        live_price_out=float(pricing["completion"]) * 1e6,
        live_temperature="temperature" in params,
        live_seed="seed" in params,
        context_length=int(model.get("context_length") or 0),
        max_completion_tokens=top.get("max_completion_tokens"),
    )

    if not check.structured_outputs:
        check.problems.append("provider no longer advertises structured_outputs")
    if not check.response_format:
        check.problems.append("provider no longer advertises response_format")
    if _drifted(arm.price_in, check.live_price_in):
        check.problems.append(f"input price {arm.price_in} -> {check.live_price_in}")
    if _drifted(arm.price_out, check.live_price_out):
        check.problems.append(f"output price {arm.price_out} -> {check.live_price_out}")
    if check.live_temperature != arm.supports_temperature:
        check.problems.append(
            f"temperature support {arm.supports_temperature} -> {check.live_temperature}"
        )
    if check.live_seed != arm.supports_seed:
        check.problems.append(f"seed support {arm.supports_seed} -> {check.live_seed}")
    return check


def verify(
    arms: tuple[Arm, ...] = HOSTED, catalogue: dict[str, dict] | None = None
) -> list[ArmCheck]:
    """Resolve every pinned arm. Costs nothing and needs no key."""
    catalogue = fetch_catalogue() if catalogue is None else catalogue
    return [check_arm(arm, catalogue) for arm in arms]
