"""Reason text comes only from the catalogue templates. Placeholders take validated values; HTML pages escape on output.

The catalogue is `catalogue.yaml` plus any `ext/*.yaml` (one file per feature area). Ext files may add codes and triggers but
may not redefine an existing code.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from ..contracts.models import FusionOutput, Lang, ReasonRef, Verdict

_PATH = Path(__file__).with_name("catalogue.yaml")
_EXT = Path(__file__).with_name("ext")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@lru_cache(maxsize=1)
def catalogue() -> dict:
    cat = yaml.safe_load(_PATH.read_text(encoding="utf-8"))
    for p in sorted(_EXT.glob("*.yaml")):
        extra = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for code, entry in (extra.get("codes") or {}).items():
            if code in cat["codes"]:
                raise ValueError(f"{p.name}: reason code {code} already exists")
            for lang in ("en", "hi"):
                if lang not in entry:
                    raise ValueError(f"{p.name}: {code} needs both en and hi text")
            cat["codes"][code] = entry
        for trig, entry in (extra.get("triggers") or {}).items():
            if trig in cat["triggers"]:
                raise ValueError(f"{p.name}: trigger {trig} already exists")
            cat["triggers"][trig] = entry
    return cat


def priority(code: str) -> int:
    return int(catalogue()["codes"].get(code, {}).get("priority", 99))


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
