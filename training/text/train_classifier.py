"""Fine-tune the scam-message classifier and measure it with whole scam families held out.

usage: python training/text/train_classifier.py [--mode head|full|both] [--seed 7] [--target-fpr 0.02]

Data (training only): UCI SMS Spam Collection (data/corpus/uci_sms/, generic spam vs ham, English) and our team corpus
(data/corpus/team_*.jsonl: Indian payment-fraud families in English, Hindi and Hinglish). data/kit/ is NEVER used here.
Base: intfloat/multilingual-e5-small ($SATYAPAN_HOME/models/e5-small).
- head: frozen encoder, train a linear head on mean-pooled embeddings.
- full: fine-tune the whole encoder plus the head.
Protocol: leave-one-scam-family-out cross-validation on the team corpus (UCI always in training). Out-of-fold scores give
(a) recall on each family the model never saw and (b) the threshold: the score that flags --target-fpr of out-of-fold genuine
messages. The final model is trained on everything and saved with that threshold. Writes docs/results/text_model_cv.json.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from satyapan.eval.metrics import rate  # noqa: E402
from satyapan.layers.l4_semantic.scam_model import MAX_LEN, ScamModel  # noqa: E402
from satyapan.store import db  # noqa: E402

CORPUS = ROOT / "data" / "corpus"


def load_rows() -> tuple[list[dict], list[dict]]:
    uci = []
    for line in (CORPUS / "uci_sms" / "SMSSpamCollection").read_text(encoding="utf-8", errors="replace").splitlines():
        lab, _, text = line.partition("\t")
        if text.strip():
            uci.append({"text": text.strip(), "label": "scam" if lab == "spam" else "benign", "lang": "en", "family": "uci_" + lab, "src": "uci"})
    team = []
    for p in sorted(CORPUS.glob("team_*.jsonl")):
        team += [{**json.loads(x), "src": "team"} for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    return uci, team


def encoder(device: str):
    from transformers import AutoModel, AutoTokenizer
    d = db.home() / "models" / "e5-small"
    return AutoTokenizer.from_pretrained(str(d)), AutoModel.from_pretrained(str(d)).to(device)


def train_one(rows: list[dict], mode: str, device: str, seed: int, epochs: int) -> ScamModel:
    torch.manual_seed(seed)
    random.seed(seed)
    tok, enc = encoder(device)
    head = torch.nn.Linear(enc.config.hidden_size, 1).to(device)
    m = ScamModel(enc, tok, head, device, mode)
    y = torch.tensor([1.0 if r["label"] == "scam" else 0.0 for r in rows], device=device)
    w = torch.tensor([5.0 if r["src"] == "team" else 1.0 for r in rows], device=device)  # our families matter more than UK SMS spam
    pos = float((y * w).sum())
    neg = float(((1 - y) * w).sum())
    w = w * torch.where(y > 0, neg / max(pos, 1.0), 1.0)                                    # balance the classes
    texts = [r["text"] for r in rows]
    if mode == "head":
        enc.eval()
        with torch.inference_mode():
            embs = torch.cat([m.embed(texts[i:i + 64]) for i in range(0, len(texts), 64)])
        embs = embs.clone()
        opt = torch.optim.AdamW(head.parameters(), lr=1e-2, weight_decay=1e-3)
        for _ in range(300):
            loss = (torch.nn.functional.binary_cross_entropy_with_logits(head(embs).squeeze(-1), y, reduction="none") * w).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    else:
        enc.train()
        opt = torch.optim.AdamW([{"params": enc.parameters(), "lr": 3e-5}, {"params": head.parameters(), "lr": 1e-3}], weight_decay=0.01)
        idx = list(range(len(rows)))
        for _ in range(epochs):
            random.shuffle(idx)
            for i in range(0, len(idx), 32):
                b = idx[i:i + 32]
                with torch.autocast(device_type="cuda", enabled=device == "cuda"):
                    logits = head(m.embed([texts[j] for j in b])).squeeze(-1).float()
                loss = (torch.nn.functional.binary_cross_entropy_with_logits(logits, y[b], reduction="none") * w[b]).mean()
                opt.zero_grad()
                loss.backward()
                opt.step()
        enc.eval()
    head.eval()
    return m


def cross_validate(uci: list[dict], team: list[dict], mode: str, device: str, seed: int, epochs: int) -> tuple[list[float], list[float], dict]:
    """Leave one scam family out. Genuine team messages are split into as many folds, so each is scored out of fold."""
    fams = sorted({r["family"] for r in team if r["label"] == "scam"})
    gen = [r for r in team if r["label"] != "scam"]
    rnd = random.Random(seed)
    rnd.shuffle(gen)
    gen_fold = {id(r): i % len(fams) for i, r in enumerate(gen)}
    oof_scam: dict[str, list[float]] = {}
    oof_gen: list[float] = []
    for k, fam in enumerate(fams):
        t0 = time.time()
        train = uci + [r for r in team if (r["label"] == "scam" and r["family"] != fam) or (r["label"] != "scam" and gen_fold[id(r)] != k)]
        m = train_one(train, mode, device, seed, epochs)
        held_s = [r["text"] for r in team if r["label"] == "scam" and r["family"] == fam]
        held_g = [r["text"] for r in gen if gen_fold[id(r)] == k]
        oof_scam[fam] = m.prob(held_s)
        oof_gen += m.prob(held_g) if held_g else []
        print(f"  [{mode}] held out {fam:15s} recall@0.5 {np.mean(np.array(oof_scam[fam]) > 0.5):.2f}  ({time.time() - t0:.0f}s)", flush=True)
        del m
        torch.cuda.empty_cache()
    return [s for v in oof_scam.values() for s in v], oof_gen, oof_scam


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["head", "full", "both"], default="both")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--target-fpr", type=float, default=0.02)
    a = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    uci, team = load_rows()
    print(f"UCI {len(uci)} messages, team corpus {len(team)} ({sum(r['label'] == 'scam' for r in team)} scams)")
    report: dict = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "seed": a.seed, "target_fpr": a.target_fpr,
                    "hardware": torch.cuda.get_device_name(0) if device == "cuda" else "cpu", "modes": {},
                    "protocol": "leave-one-scam-family-out on the team corpus; UCI SMS always in training; data/kit never used",
                    "reproduce": "python training/text/fetch.py && python training/text/train_classifier.py"}
    for mode in (["head", "full"] if a.mode == "both" else [a.mode]):
        scam_s, gen_s, per_fam = cross_validate(uci, team, mode, device, a.seed, a.epochs)
        thr = float(np.quantile(gen_s, 1 - a.target_fpr)) if gen_s else 0.5
        report["modes"][mode] = {"threshold": thr, "recall_unseen_family": rate(int(sum(s > thr for s in scam_s)), len(scam_s)),
                                 "genuine_flagged_oof": rate(int(sum(s > thr for s in gen_s)), len(gen_s)),
                                 "per_family": {f: rate(int(sum(s > thr for s in v)), len(v)) for f, v in per_fam.items()}}
        r = report["modes"][mode]
        print(f"[{mode}] threshold {thr:.3f}: unseen-family scams caught {r['recall_unseen_family']['k']}/{r['recall_unseen_family']['n']}, "
              f"genuine flagged {r['genuine_flagged_oof']['k']}/{r['genuine_flagged_oof']['n']}")
    # pick the mode with the best unseen-family recall at the same false-alarm target (ties: the simpler head)
    best = max(report["modes"], key=lambda k: (report["modes"][k]["recall_unseen_family"]["rate"], k == "head"))
    report["chosen"] = best
    m = train_one(uci + team, best, device, a.seed, a.epochs)
    out = db.home() / "models" / "scam_text"
    out.mkdir(parents=True, exist_ok=True)
    torch.save(m.head.state_dict(), out / "head.pt")
    if best == "full":
        m.enc.save_pretrained(out / "encoder")
        m.tok.save_pretrained(out / "encoder")
    cfg = {"made": report["date"], "mode": best, "encoder_dir": "e5-small", "threshold": report["modes"][best]["threshold"], "max_len": MAX_LEN,
           "enabled": False, "enabled_reason": "off until training/text/decide.py compares it with the rules on held-out messages"}
    (out / "config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    (ROOT / "docs" / "results").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "results" / "text_model_cv.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"chosen: {best}; saved to {out} (disabled until decide.py)")


if __name__ == "__main__":
    main()
