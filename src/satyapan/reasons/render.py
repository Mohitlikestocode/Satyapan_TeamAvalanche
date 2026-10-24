"""Reason text comes only from the catalogue templates. Placeholders take validated values; HTML pages escape on output."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from ..contracts.models import FusionOutput, Lang, ReasonRef, Tier, Verdict

_PATH = Path(__file__).with_name("catalogue.yaml")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@lru_cache(maxsize=1)
def catalogue() -> dict:
    return yaml.safe_load(_PATH.read_text(encoding="utf-8"))


def render_reason(ref: ReasonRef, lang: Lang) -> str:
    cat = catalogue()
    entry = cat["codes"][ref.code]
    template = entry[lang.value]
    params = dict(ref.params)
    if "trigger" in params:  # only ids from the fixed vocabulary are accepted
        trig = cat["triggers"].get(str(params["trigger"]))
        params["trigger"] = trig[lang.value] if trig else ""
    return _PLACEHOLDER.sub(lambda m: str(params.get(m.group(1), "")), template)


def build_verdict(case_id: str, out: FusionOutput, lang: Lang) -> Verdict:
    cat = catalogue()
    tier = cat["tiers"][out.tier.value]
    return Verdict(
        case_id=case_id,
        tier=out.tier,
        lang=lang,
        headline=tier["headline"][lang.value],
        reasons_text=[render_reason(r, lang) for r in out.reasons],
        action_text=tier["action"][lang.value],
        footer_text=cat["footer"][lang.value],
        reason_codes=[r.code for r in out.reasons],
    )
