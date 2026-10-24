"""Measure how the site behaves under load, with realistic inputs, and write the numbers to a JSON file.

usage: python scripts/loadtest.py http://127.0.0.1:8000 --out docs/results/loadtest.json [--levels 1,4,8,16] [--seconds 15] [--price-per-month 500]

Each simulated visitor has its own device cookie (so per-visitor rate limits behave as in real life) and sends a mix of checks:
60% messages, 15% links, 15% QR images, 10% PDFs. The files are generated here (made-up payees). Run it against a server started
WITHOUT RATE_LIMIT=1 (or with generous limits) to measure the engine, and against the real deployment to see throttling.
Every number in the output comes from this run. Nothing is estimated except the cost figure, whose assumptions are printed.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import platform
import random
import statistics
import time
from pathlib import Path

import httpx

MESSAGES = [
    "Guaranteed 30% a month, join our VIP group. Pay upi://pay?pa=alpha.gain88@ybl&pn=Ramesh%20K&am=25000",
    "Your Amazon order will be delivered today between 2 pm and 6 pm. Track it in the Amazon app.",
    "Bank: ICICI Bank IFSC: HDFC0001234. Our bank account has changed, please pay to the new account.",
    "Pay 18% tax before you can withdraw your profit. Send Rs 21600 to tax.desk@ybl.",
    "आपका बैंक खाता बंद हो जाएगा। अभी KYC अपडेट करें: https://axis-kyc-update.example",
    "Sending you Rs 500 for dinner, my UPI is ravi.k@okaxis.",
]
LINKS = ["https://hdfc-bank-kyc-update.example/login", "https://www.hdfcbank.com/personal", "http://sbi-yono-verify.example/secure"]


def make_qr() -> bytes:
    import segno
    b = io.BytesIO()
    segno.make("upi://pay?pa=alpha.gain88@ybl&pn=Ramesh%20K&am=25000").save(b, kind="png", scale=6, border=4)
    return b.getvalue()


def make_pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    for i, line in enumerate(["TAX INVOICE INV-2026-1042", "Bank: ICICI Bank  IFSC: HDFC0001234", "Note: our bank account has changed."]):
        c.drawString(60, 780 - 22 * i, line)
    c.save()
    return b.getvalue()


def pct(sorted_vals: list[float], q: float) -> float | None:
    return round(sorted_vals[min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))] * 1000, 1) if sorted_vals else None


async def visitor(client: httpx.AsyncClient, deadline: float, assets: dict, stats: dict) -> None:
    rnd = random.Random()
    while time.monotonic() < deadline:
        roll = rnd.random()
        t0 = time.perf_counter()
        try:
            if roll < 0.60:
                r = await client.post("/api/v1/check", data={"kind": "message", "text": rnd.choice(MESSAGES)})
            elif roll < 0.75:
                r = await client.post("/api/v1/check", data={"kind": "link", "text": rnd.choice(LINKS)})
            elif roll < 0.90:
                r = await client.post("/api/v1/check", data={"kind": "qr"}, files={"file": ("q.png", assets["qr"], "image/png")})
            else:
                r = await client.post("/api/v1/check", data={"kind": "pdf"}, files={"file": ("i.pdf", assets["pdf"], "application/pdf")})
            dt = time.perf_counter() - t0
            kind = "ok" if r.status_code == 200 else ("throttled" if r.status_code == 429 else "error")
        except httpx.HTTPError:
            dt, kind = time.perf_counter() - t0, "error"
        stats[kind] += 1
        if kind == "ok":
            stats["lat"].append(dt)
        await asyncio.sleep(rnd.uniform(0.05, 0.2))


async def run_level(base: str, users: int, seconds: float, assets: dict) -> dict:
    stats = {"ok": 0, "throttled": 0, "error": 0, "lat": []}
    deadline = time.monotonic() + seconds
    clients = [httpx.AsyncClient(base_url=base, timeout=60, cookies={"sp_dev": f"load-{users}-{i}-{random.random():.6f}", "sp_internal": "1"}) for i in range(users)]
    started = time.monotonic()
    await asyncio.gather(*(visitor(c, deadline, assets, stats) for c in clients))
    elapsed = time.monotonic() - started
    for c in clients:
        await c.aclose()
    lat = sorted(stats["lat"])
    total = stats["ok"] + stats["throttled"] + stats["error"]
    return {"users": users, "seconds": round(elapsed, 1), "requests": total, "ok": stats["ok"], "throttled_429": stats["throttled"], "errors": stats["error"],
            "error_rate": round(stats["error"] / total, 4) if total else None, "checks_per_second": round(stats["ok"] / elapsed, 2),
            "p50_ms": pct(lat, 0.5), "p95_ms": pct(lat, 0.95), "p99_ms": pct(lat, 0.99), "mean_ms": round(statistics.mean(lat) * 1000, 1) if lat else None}


def cost_figures(best_cps: float, price_per_month: float) -> dict:
    """Cost per 1,000 checks at two utilisations. The price is whatever the human pays for the server; nothing here is a quote."""
    if not best_cps or not price_per_month:
        return {"note": "give --price-per-month to compute"}
    month_seconds = 30 * 24 * 3600
    out = {"server_price_per_month": price_per_month, "best_measured_checks_per_second": best_cps}
    for util in (1.0, 0.1):
        checks = best_cps * month_seconds * util
        out[f"cost_per_1000_checks_at_{int(util * 100)}pct_utilisation"] = round(price_per_month / (checks / 1000), 4)
    out["assumption"] = "price divided by checks the server could answer in a month at that utilisation; excludes bandwidth, domain and people"
    return out


async def main_async(a) -> dict:
    assets = {"qr": make_qr(), "pdf": make_pdf()}
    async with httpx.AsyncClient(base_url=a.base, timeout=10) as c:
        health = (await c.get("/healthz")).json()
    levels = []
    for n in [int(x) for x in a.levels.split(",")]:
        print(f"level: {n} visitors for {a.seconds}s ...", flush=True)
        r = await run_level(a.base, n, a.seconds, assets)
        print(f"   {r['checks_per_second']} checks/s  p50 {r['p50_ms']} ms  p95 {r['p95_ms']} ms  throttled {r['throttled_429']}  errors {r['errors']}", flush=True)
        levels.append(r)
    best = max((lv["checks_per_second"] for lv in levels if lv["error_rate"] in (0, 0.0)), default=0)
    return {"target": a.base, "healthz": health, "machine_running_the_test": {"platform": platform.platform(), "python": platform.python_version(), "cpus": os.cpu_count()},
            "note": "the machine running the test is not necessarily the server; the server's own hardware must be stated next to these numbers",
            "mix": {"message": 0.60, "link": 0.15, "qr_image": 0.15, "pdf": 0.10}, "date": time.strftime("%Y-%m-%d %H:%M"), "levels": levels,
            "cost": cost_figures(best, a.price_per_month)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--levels", default="1,4,8,16")
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--price-per-month", type=float, default=0.0)
    a = ap.parse_args()
    a.base = a.base.rstrip("/")
    result = asyncio.run(main_async(a))
    print(json.dumps(result["cost"], indent=1))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print("wrote", a.out)


if __name__ == "__main__":
    main()
