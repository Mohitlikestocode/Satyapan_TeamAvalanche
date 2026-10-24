"""Read the measured results in docs/results/ for the Results page.

Nothing here invents a number. A section whose file is missing is shown as "not evaluated". Three file shapes are understood:
- the tamper evaluator's output (training/tamper/evaluate.py) and the real-screenshot evaluator's output (evaluate_real.py),
- the text-kit report (satyapan.eval.report),
- the generic shape below, used by the voice evaluation and anything new:

  {"schema": 1, "dataset": str, "split": str, "held_out": bool, "hardware": str, "date": str, "reproduce": str,
   "rows": [{"name": str, "baseline": bool, "tpr": rate, "fpr": rate, "auroc": float|null, "auroc_ci": [lo, hi]|null, "eer": float|null}],
   "conditions": [{"name": str, "tpr": rate|null, "fpr": rate|null}],
   "failures": [{"kind": "missed"|"false_alarm", "text": str}]}

where a rate is {"k": int, "n": int, "rate": float, "lo": float, "hi": float} (Wilson 95% interval, see metrics.py).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parents[3] / "docs" / "results"

# Bilingual labels for condition keys written by our evaluators. Unknown keys are shown as they are (they are identifiers).
CONDITION_LABELS: dict[str, tuple[str, str]] = {
    "jpeg_q95": ("JPEG quality 95", "JPEG गुणवत्ता 95"), "jpeg_q90": ("JPEG quality 90", "JPEG गुणवत्ता 90"),
    "jpeg_q85": ("JPEG quality 85", "JPEG गुणवत्ता 85"), "jpeg_q70": ("JPEG quality 70", "JPEG गुणवत्ता 70"),
    "jpeg_q55": ("JPEG quality 55", "JPEG गुणवत्ता 55"), "jpeg_q40": ("JPEG quality 40 (heavy chat compression)", "JPEG गुणवत्ता 40 (भारी चैट कम्प्रेशन)"),
    "scale_1.0": ("Full size", "पूरा आकार"), "scale_0.85": ("Shrunk to 85%", "85% तक छोटा"), "scale_0.75": ("Shrunk to 75%", "75% तक छोटा"),
    "scale_0.6": ("Shrunk to 60%", "60% तक छोटा"), "scale_0.5": ("Shrunk to 50%", "50% तक छोटा"),
    "font_seen": ("Font seen in training", "ट्रेनिंग में देखा गया फ़ॉन्ट"), "font_unseen": ("Font never seen in training", "ट्रेनिंग में कभी न देखा गया फ़ॉन्ट"),
    "dark": ("Dark-mode screens", "डार्क-मोड स्क्रीन"), "light": ("Light screens", "हल्की स्क्रीन"),
    "recompressed_twice": ("Compressed twice (forwarded)", "दो बार कम्प्रेस (फ़ॉरवर्ड किया गया)"),
    "edit_fill": ("Edit: painted over", "बदलाव: ऊपर से रंग भरा"), "edit_clone": ("Edit: background copied over", "बदलाव: पृष्ठभूमि कॉपी की"),
    "edit_same_font": ("Edit in the same font", "उसी फ़ॉन्ट में बदलाव"), "edit_other_font": ("Edit in a different font", "दूसरे फ़ॉन्ट में बदलाव"),
    "edit_perfect": ("Perfect edit (exact colour, size and place)", "बिल्कुल सटीक बदलाव (वही रंग, आकार और जगह)"),
    "edit_with_traces": ("Edit with small traces", "हल्के निशान वाला बदलाव"),
    "field_amount": ("Amount edited", "रकम बदली"), "field_payee": ("Payee name edited", "पाने वाले का नाम बदला"),
    "field_ref": ("Reference edited", "रेफ़रेंस बदला"), "field_time": ("Time edited", "समय बदला"), "field_vpa": ("UPI ID edited", "UPI ID बदली"),
    "lang:en": ("English messages", "अंग्रेज़ी संदेश"), "lang:hi": ("Hindi messages", "हिंदी संदेश"), "lang:hinglish": ("Hinglish messages", "हिंग्लिश संदेश"),
    "clean": ("Clean audio", "साफ़ ऑडियो"), "opus24k": ("Opus 24 kbps (WhatsApp-like)", "Opus 24 kbps (WhatsApp जैसा)"),
    "aac64k": ("AAC 64 kbps", "AAC 64 kbps"), "tel8k": ("8 kHz telephone", "8 kHz टेलीफ़ोन"),
}


@dataclass
class Row:
    name: str
    baseline: bool
    tpr: dict | None
    fpr: dict | None
    auroc: float | None = None
    auroc_ci: tuple[float, float] | None = None
    eer: float | None = None


@dataclass
class Section:
    key: str
    title: tuple[str, str]
    what: tuple[str, str]
    pos: tuple[str, str]          # what a "positive" is: edited screenshots, scams, cloned voices
    neg: tuple[str, str]
    held_out: bool = True
    status: str = "not_evaluated"  # or "measured"
    files: list[str] = field(default_factory=list)
    dataset: str = ""
    split: str = ""
    hardware: str = ""
    date: str = ""
    reproduce: str = ""
    rows: list[Row] = field(default_factory=list)
    conditions: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    deliberate: bool = False       # not evaluated on purpose (the "what" text says why), not "not yet"


def _num(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def _rate(r) -> dict | None:
    if not isinstance(r, dict) or not r.get("n"):
        return None
    return {"k": int(r["k"]), "n": int(r["n"]), "rate": float(r["k"]) / int(r["n"]), "lo": float(r["lo"]), "hi": float(r["hi"])}


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def condition_label(key: str, lang: str) -> str:
    if key in CONDITION_LABELS:
        return CONDITION_LABELS[key][1 if lang == "hi" else 0]
    if key.startswith("style_"):
        return ("लेआउट " if lang == "hi" else "Layout ") + key[6:]
    if key.startswith("family:"):
        return ("स्कैम/संदेश प्रकार: " if lang == "hi" else "Message family: ") + key[7:]
    return key


# ---- adapters ------------------------------------------------------------------------------------------------

def _from_tamper(sec: Section, data: dict, name: str, with_baseline: bool) -> None:
    m = data.get("model", {})
    enc = (data.get("config") or {}).get("encoder", "?")
    ci = m.get("auroc_ci")
    sec.rows.append(Row(name=f"{name} ({enc} encoder, epoch {data.get('epoch', '?')})", baseline=False, tpr=_rate(m.get("tpr")),
                        fpr=_rate(m.get("fpr")), auroc=_num(m.get("auroc")), auroc_ci=tuple(ci) if ci and _num(ci[0]) is not None else None))
    if with_baseline and "baseline_ela" in data:
        b = data["baseline_ela"]
        bci = b.get("auroc_ci")
        sec.rows.append(Row(name="Baseline: error-level analysis", baseline=True, tpr=_rate(b.get("tpr")), fpr=_rate(b.get("fpr")),
                            auroc=_num(b.get("auroc")), auroc_ci=tuple(bci) if bci and _num(bci[0]) is not None else None))
    if with_baseline:
        for k, v in (data.get("by_condition") or {}).items():
            sec.conditions.append({"name": k, "tpr": _rate(v.get("tpr")), "fpr": _rate(v.get("fpr"))})
        sec.failures += list(data.get("failures") or [])
        sec.hardware = data.get("hardware", "")
        sec.split = f"{data.get('split', '?')} split ({data.get('n', '?')} images), threshold from the {data.get('threshold_from', 'validation split')}"


def _from_tamper_real(sec: Section, data: dict) -> None:
    sec.rows.append(Row(name="Tamper model", baseline=False, tpr=_rate(data.get("tpr")), fpr=_rate(data.get("fpr")), auroc=_num(data.get("auroc"))))
    if "baseline_ela" in data:
        b = data["baseline_ela"]
        sec.rows.append(Row(name="Baseline: error-level analysis", baseline=True, tpr=_rate(b.get("tpr")), fpr=_rate(b.get("fpr")), auroc=_num(b.get("auroc"))))
    sec.failures += [{"kind": "missed", "text": n} for n in data.get("missed", [])]
    sec.failures += [{"kind": "false_alarm", "text": n} for n in data.get("false_alarms", [])]
    sec.hardware = data.get("hardware", "")
    sec.split = "real screenshots, threshold from the synthetic validation split (not tuned on these)"


def _from_generic(sec: Section, data: dict) -> None:
    for r in data.get("rows", []):
        ci = r.get("auroc_ci")
        sec.rows.append(Row(name=r.get("name", "?"), baseline=bool(r.get("baseline")), tpr=_rate(r.get("tpr")), fpr=_rate(r.get("fpr")),
                            auroc=_num(r.get("auroc")), auroc_ci=tuple(ci) if ci else None, eer=_num(r.get("eer"))))
    for c in data.get("conditions", []):
        sec.conditions.append({"name": c.get("name", "?"), "tpr": _rate(c.get("tpr")), "fpr": _rate(c.get("fpr")),
                               "eer": _num(c.get("eer")), "row": c.get("row", "")})
    sec.failures += list(data.get("failures") or [])
    for k in ("dataset", "split", "hardware", "reproduce"):
        if data.get(k):
            setattr(sec, k, str(data[k]))
    if "held_out" in data:
        sec.held_out = bool(data["held_out"])


def _from_text_cv(sec: Section, data: dict) -> None:
    for mode, m in data.get("modes", {}).items():
        name = {"head": "Frozen encoder + trained head", "full": "Whole encoder fine-tuned"}.get(mode, mode)
        sec.rows.append(Row(name=name + (" (chosen)" if data.get("chosen") == mode else ""), baseline=False,
                            tpr=_rate(m.get("recall_unseen_family")), fpr=_rate(m.get("genuine_flagged_oof"))))
    chosen = data.get("modes", {}).get(data.get("chosen", ""), {})
    for fam, r in (chosen.get("per_family") or {}).items():
        sec.conditions.append({"name": f"family:{fam}", "tpr": _rate(r), "fpr": None})
    sec.hardware = data.get("hardware", "")
    sec.reproduce = data.get("reproduce", "")
    sec.split = "leave one scam family out (the model never saw the family it is scored on); threshold from out-of-fold genuine messages"


def _apply(sec: Section, path: Path, data: dict, first: bool) -> None:
    sec.status = "measured"
    sec.files.append(path.name)
    if first:
        sec.date = data.get("date") or _mtime(path)
    if "modes" in data and "protocol" in data:
        _from_text_cv(sec, data)
    elif data.get("schema") == 1:
        _from_generic(sec, data)
    elif "baseline_ela" in data and "by_condition" in data:
        label = "Tamper model (chosen)" if path.name == "tamper_test.json" else "Tamper model (alternative)"
        _from_tamper(sec, data, label, with_baseline=first)
    elif "missed" in data and "false_alarms" in data:
        _from_tamper_real(sec, data)


# ---- the page's sections, in order ---------------------------------------------------------------------------

def sections(results_dir: Path | None = None) -> list[Section]:
    d = results_dir or RESULTS_DIR
    out = [
        Section("screenshot_system", ("Payment screenshots, whole check as deployed: synthetic, held-out styles; not evaluated on real phone screenshots",
                                      "पेमेंट स्क्रीनशॉट, पूरी जाँच जैसी साइट पर चलती है: बनाई गई स्क्रीन, अलग रखे गए लेआउट; असली फ़ोन स्क्रीनशॉट पर नहीं परखा गया"),
                ("The full screenshot check (text reading, payee and word rules, edit model, verdict rules) on generated screens in layout styles never seen in training.",
                 "पूरी स्क्रीनशॉट जाँच (टेक्स्ट पढ़ना, पाने वाले और शब्दों के नियम, बदलाव मॉडल, नतीजे के नियम), ट्रेनिंग में कभी न देखे गए लेआउट की बनाई गई स्क्रीन पर।"),
                ("edited screenshots", "बदले गए स्क्रीनशॉट"), ("genuine screenshots", "असली स्क्रीनशॉट"),
                dataset="synthetic, held-out styles; not evaluated on real phone screenshots"),
        Section("screenshot_synthetic", ("Payment-screenshot edit model: synthetic, held-out styles; not evaluated on real phone screenshots",
                                         "पेमेंट-स्क्रीनशॉट बदलाव मॉडल: बनाई गई स्क्रीन, अलग रखे गए लेआउट; असली फ़ोन स्क्रीनशॉट पर नहीं परखा गया"),
                ("Generated payment screens in layout styles and fonts the model never saw in training.",
                 "बनाई गई पेमेंट स्क्रीन, ऐसे लेआउट और फ़ॉन्ट में जो मॉडल ने ट्रेनिंग में कभी नहीं देखे।"),
                ("edited screenshots", "बदले गए स्क्रीनशॉट"), ("genuine screenshots", "असली स्क्रीनशॉट"),
                dataset="synthetic, held-out styles (tools/make_payment_screens.py, split by layout family); not evaluated on real phone screenshots"),
        Section("screenshot_real", ("Real phone screenshots", "असली फ़ोन स्क्रीनशॉट"),
                ("Not evaluated, on purpose: we do not use anyone's payment data without permission, so we have no real payment screenshots to test on. "
                 "The screenshot numbers above come from synthetic screens only, and real apps look different, so expect lower numbers on real screenshots.",
                 "जानबूझकर नहीं परखा गया: हम किसी का पेमेंट डेटा बिना अनुमति इस्तेमाल नहीं करते, इसलिए परखने के लिए हमारे पास असली पेमेंट स्क्रीनशॉट नहीं हैं। "
                 "ऊपर के स्क्रीनशॉट नतीजे सिर्फ़ बनाई गई स्क्रीन से हैं, और असली ऐप अलग दिखते हैं, इसलिए असली स्क्रीनशॉट पर कम नतीजे की उम्मीद रखें।"),
                ("edited screenshots", "बदले गए स्क्रीनशॉट"), ("genuine screenshots", "असली स्क्रीनशॉट"), deliberate=True),
        Section("text_holdout", ("Messages: held out, written by teammates", "संदेश: अलग रखे गए, टीम के लोगों ने लिखे"),
                ("Scam and genuine messages written by teammates who did not read the rules. Never used to build or train anything.",
                 "स्कैम और असली संदेश, जो उन टीम सदस्यों ने लिखे जिन्होंने नियम नहीं पढ़े। किसी चीज़ को बनाने या ट्रेन करने में इस्तेमाल नहीं हुए।"),
                ("scam messages", "स्कैम संदेश"), ("genuine messages", "असली संदेश"), dataset="data/kit/holdout_*.jsonl"),
        Section("text_kit", ("Messages: development kit (optimistic)", "संदेश: डेवलपमेंट किट (आशावादी)"),
                ("The messages we looked at while writing the rules. Numbers here are optimistic; the held-out row above is the honest one.",
                 "वे संदेश जिन्हें देखकर नियम लिखे गए। ये नतीजे आशावादी हैं; ऊपर वाला अलग रखा गया नतीजा ईमानदार है।"),
                ("scam messages", "स्कैम संदेश"), ("genuine messages", "असली संदेश"), held_out=False, dataset="data/kit/messages.jsonl"),
        Section("text_model_cv", ("Scam-message model: scam families it never saw", "स्कैम-संदेश मॉडल: स्कैम के वे प्रकार जो उसने कभी नहीं देखे"),
                ("Our fine-tuned message model, scored on each scam family after training without that family. Team-written data, so optimistic.",
                 "हमारा फ़ाइन-ट्यून किया संदेश मॉडल, हर स्कैम प्रकार पर उसे उस प्रकार के बिना ट्रेन करने के बाद परखा गया। टीम का लिखा डेटा, इसलिए आशावादी।"),
                ("scam messages", "स्कैम संदेश"), ("genuine messages", "असली संदेश"), held_out=False,
                dataset="data/corpus/team_*.jsonl (team-written) + UCI SMS Spam Collection; data/kit never used"),
        Section("voice", ("Voice notes: cloned-voice detector", "वॉइस नोट: नकली (क्लोन) आवाज़ पहचान"),
                ("Real and machine-made speech from speakers kept out of calibration, also after chat-app re-encoding.",
                 "असली और मशीन से बनी आवाज़, ऐसे वक्ताओं की जो कैलिब्रेशन में नहीं थे, चैट-ऐप री-एन्कोडिंग के बाद भी।"),
                ("cloned or synthetic voices", "क्लोन या कृत्रिम आवाज़ें"), ("real voices", "असली आवाज़ें")),
    ]
    files = {
        "screenshot_real": ["tamper_real.json"],
        "screenshot_system": ["screenshot_system.json"],
        "screenshot_synthetic": ["tamper_test.json"] + sorted(p.name for p in d.glob("tamper_test_*.json")),
        "text_holdout": ["text_holdout.json"],
        "text_kit": ["text_kit.json"],
        "text_model_cv": ["text_model_cv.json"],
        "voice": ["voice_test.json"],
    }
    for sec in out:
        first = True
        for name in files[sec.key]:
            p = d / name
            data = _load(p) if p.exists() else None
            if data is None:
                continue
            _apply(sec, p, data, first)
            first = False
    return out


def fmt_rate(r: dict | None, lang: str = "en") -> str:
    if not r:
        return "मापा नहीं गया" if lang == "hi" else "not evaluated"
    return f"{r['k']}/{r['n']} = {100 * r['rate']:.0f}% (95% CI {100 * r['lo']:.0f}–{100 * r['hi']:.0f}%)"
