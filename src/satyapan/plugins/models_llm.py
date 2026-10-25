"""AI rule check as a text hook: matched ground rules become signs; fusion and our templates decide what the user sees.

A rule marked strong, matched with high confidence, gives STRONG_SUSPICIOUS; anything else gives WEAK_SUSPICIOUS. Never an
"authentic" sign: the model can only add warnings, never clear a message. See layers/l4_semantic/llm_check.py for the safety design.
"""
from __future__ import annotations

from ..contracts.models import Layer, LayerResult, Signal, Strength
from ..layers.l4_semantic import llm_check
from ..layers.l4_semantic.ground_rules import BY_ID
from ..layers.l4_semantic.normalise import normalise

MIN_CHARS = 12


def ai_rules(text: str, found) -> LayerResult | None:
    if len(text.strip()) < MIN_CHARS:
        return None
    res = llm_check.check(normalise(text).text)
    if res is None or not res.matches:
        return None
    signals = []
    for m in res.matches:
        rule = BY_ID[m.rule]
        strong = rule.strong and m.confidence == "high"
        signals.append(Signal(layer=Layer.L4, code=rule.code, strength=Strength.STRONG_SUSPICIOUS if strong else Strength.WEAK_SUSPICIOUS))
    return LayerResult(layer=Layer.L4, signals=signals, model_versions={"ai_rules": f"{res.provider}:{res.model}"},
                       internal={"label_key": "ml_ai_rules", "matches": [m.__dict__ for m in res.matches], "seconds": res.seconds})


# Runs on every kind of input (message, link, voice transcript, PDF text, QR note and the words printed around it, screenshot text).
# One exception: a payment RECEIPT (a screenshot that says "payment successful" with a transaction id and no request to pay) is skipped,
# because its ordinary wording ("paid to ... UPI ID ... amount") made false alarms in measurement.
ai_rules.skip_kinds = ()
ai_rules.skip_receipt = True


def setup(registry) -> None:
    from ..envfile import load_dotenv
    load_dotenv()  # command-line tools get the key from .env too (the site loads it at start)
    registry.add_text_hook(ai_rules, "ml_ai_rules", "AI check against 33 official scam-warning rules (personal numbers masked)",
                           "33 आधिकारिक ठगी-चेतावनी नियमों पर AI जाँच (निजी नंबर छिपाए गए)")
