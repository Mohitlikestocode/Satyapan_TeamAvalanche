"""Hidden-word check: if a message hides its words (look-alike letters, spread-out letters, split UPI IDs), run the same payee
and word rules again on the cleaned-up copy, and say that the message hides words (a weak warning sign on its own).

Uses only the public rule functions; no core file is changed. See layers/l4_semantic/normalise.py.
"""
from __future__ import annotations

from ..contracts.models import Layer, LayerResult, Signal, Strength
from ..extract.entities import extract
from ..layers.l3_payee import layer as l3
from ..layers.l4_rules import layer as l4
from ..layers.l4_semantic.normalise import normalise


def hidden_words(text: str, found) -> LayerResult | None:
    n = normalise(text)
    if not n.changed:
        return None
    from ..service import load_snapshot
    l4res = l4.run(n.text)
    f2 = extract(n.text)
    l3res = l3.run(n.text, f2, l4res.signals, snapshot=load_snapshot())
    seen, signals = set(), []
    for s in [*l4res.signals, *l3res.signals]:
        if s.strength.suspicious and (s.code, s.layer) not in seen:
            seen.add((s.code, s.layer))
            signals.append(s)
    if n.tricks:  # joining ordinary abbreviations like "K.Y.C" is not a warning sign by itself
        signals.append(Signal(layer=Layer.L4, code="ML_TEXT_OBFUSCATED", strength=Strength.WEAK_SUSPICIOUS, params={}))
    if not signals:
        return None
    return LayerResult(layer=Layer.L4, signals=signals, model_versions={"normalise": "v1"},
                       internal={"label_key": "ml_hidden_words", "tricks": n.tricks})


def setup(registry) -> None:
    registry.add_text_hook(hidden_words, "ml_hidden_words", "Hidden-word check (look-alike letters, spaced-out letters, split UPI IDs)",
                           "छिपे शब्दों की जाँच (हूबहू दिखने वाले अक्षर, बिखरे अक्षर, टूटी UPI ID)")
