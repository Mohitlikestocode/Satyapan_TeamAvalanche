"""Learn: lessons, Scam Drill, progress page, leaderboard, certificate, safe-word card and safety guide.

These routes replace the design pages at /learn, /learn/drill, /learn/drill/score, /learn/safe-word and /learn/safety.
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ...community import cards, content, drill, progress
from ..web import lang_of, render
from . import community_common as cc

router = APIRouter()
LEARN = [["Learn", "/learn"]]

DRILL_ERRORS = {
    "limit": ("You have played the most rounds allowed today. Please come back tomorrow.", "आज के लिए अधिकतम राउंड खेले जा चुके हैं। कृपया कल आइए।"),
    "bad_code": ("That challenge code was not found. Ask your relative to send it again.", "यह चुनौती-कोड नहीं मिला। अपने रिश्तेदार से दोबारा भेजने को कहें।"),
    "invalid": ("Please choose an answer first.", "कृपया पहले कोई उत्तर चुनें।"),
    "no_round": ("That round was not found on this phone.", "यह राउंड इस फ़ोन पर नहीं मिला।"),
    "bad_mode": ("Unknown kind of round.", "राउंड का प्रकार पता नहीं।"),
}
HANDLE_ERRORS = {
    "length": ("Use 3 to 20 characters.", "3 से 20 अक्षर रखें।"),
    "chars": ("Use only letters, numbers and the underscore.", "सिर्फ़ अक्षर, अंक और अंडरस्कोर इस्तेमाल करें।"),
    "digits": ("A long number looks like a phone number. Please choose a name.", "लंबा नंबर फ़ोन नंबर जैसा लगता है। कृपया कोई नाम चुनें।"),
    "profanity": ("Please choose a kinder name.", "कृपया कोई अच्छा नाम चुनें।"),
    "reserved": ("That name is kept for the team. Please choose another.", "यह नाम टीम के लिए रखा है। कृपया दूसरा चुनें।"),
    "taken": ("Someone already has that name. Please try another.", "यह नाम पहले से किसी का है। कृपया दूसरा आज़माएँ।"),
    "limit": ("You changed your name too many times today. Try tomorrow.", "आपने आज नाम बहुत बार बदला। कल कोशिश करें।"),
}


def tz(request: Request) -> int:
    c = request.cookies.get("sp_tz", "")
    try:
        return max(-720, min(840, int(c)))
    except ValueError:
        return 330


def _lang(request: Request) -> str:
    return lang_of(request)


def _pg(route: str, title: str, crumbs: list[list], section: str = "learn"):
    return cc.page(route, title, section, crumbs)


def _day(request: Request) -> str:
    return progress.local_day(time.time(), tz(request))


# ---- hub and lessons --------------------------------------------------------------------------------------
@router.get("/learn", response_class=HTMLResponse, include_in_schema=False)
def learn_home(request: Request):
    raw, dev, _ = cc.device(request)
    me = progress.summary(dev)
    return render(request, "ext/community/learn_home.html", _pg("learn", "Learn", [["Learn", None]]), lessons=content.lessons(), me=me,
                  daily=drill.daily_status(dev), board=progress.leaderboard(dev, 5), n_questions=len(content.questions()))


@router.get("/learn/leaderboard", response_class=HTMLResponse, include_in_schema=False)
def leaderboard_page(request: Request):
    _, dev, _ = cc.device(request)
    return render(request, "ext/community/leaderboard.html", _pg("learn/leaderboard", "Leaderboard", [*LEARN, ["Leaderboard", None]]),
                  board=progress.leaderboard(dev, 50), me=progress.summary(dev), fmt=lambda ts: datetime.fromtimestamp(ts, progress.IST).strftime("%d %b"))


@router.get("/learn/safety", response_class=HTMLResponse, include_in_schema=False)
def safety(request: Request):
    return render(request, "ext/community/safety.html", _pg("learn/safety", "Safety guide", [*LEARN, ["Safety guide", None]]), rules=content.safety_rules())


@router.get("/learn/safe-word", response_class=HTMLResponse, include_in_schema=False)
def safe_word(request: Request, word: str = "", who: str = "", card: str = "", suggest: str = ""):
    lang = _lang(request)
    words = content.safe_words()
    pick = lambda: " ".join(w[lang] for w in (secrets.SystemRandom().sample(list(words), 2)))  # noqa: E731
    word = " ".join(word.split())[:40]
    who = " ".join(who.split())[:30]
    if suggest or not word:
        word = pick()
    return render(request, "ext/community/safe_word.html", _pg("learn/safe-word", "Family safe-word card", [*LEARN, ["Safe-word card", None]]),
                  word=word, who=who, show=bool(card), qs=f"word={quote(word)}&who={quote(who)}")


@router.get("/learn/safe-word/card.png", include_in_schema=False)
def safe_word_png(request: Request, word: str = "", who: str = "", lang: str = ""):
    word = " ".join(word.split())[:40]
    if not word:
        raise HTTPException(404)
    png = cards.safe_word_card(word, " ".join(who.split())[:30], lang or _lang(request), cc.origin(request))
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="safe-word-card.png"'})


@router.get("/learn/drill", response_class=HTMLResponse, include_in_schema=False)
def drill_home(request: Request, error: str = ""):
    _, dev, _ = cc.device(request)
    return render(request, "ext/community/drill_home.html", _pg("learn/drill", "Scam Drill", [*LEARN, ["Scam Drill", None]]), me=progress.summary(dev),
                  daily=drill.daily_status(dev), board=progress.leaderboard(dev, 5), error=DRILL_ERRORS.get(error), n_questions=len(content.questions()))


# ---- drill ------------------------------------------------------------------------------------------------
@router.get("/drill/play", response_class=HTMLResponse, include_in_schema=False)
def play(request: Request, r: str = "", c: str = "", done: str = "", error: str = ""):
    lang = _lang(request)
    raw, dev, new = cc.device(request)
    pg = _pg("drill/play", "Scam Drill", [*LEARN, ["Scam Drill", "/learn/drill"], ["Round", None]])
    if not r:
        intro = drill.challenge_intro(c) if c else None
        if c and not intro:
            return RedirectResponse("/learn/drill?error=bad_code", status_code=303)
        if not intro:
            return RedirectResponse("/learn/drill", status_code=303)
        return render(request, "ext/community/drill_challenge.html", pg, intro=intro, me=progress.summary(dev))
    if done:
        seen = drill.answered_view(r, dev, done, lang)
        if not seen:
            return RedirectResponse(f"/drill/play?r={quote(r)}", status_code=303)
        return render(request, "ext/community/drill_play.html", pg, rid=r, view=seen, st=None, error=DRILL_ERRORS.get(error))
    st = drill.state(r, dev, lang)
    if not st:
        return RedirectResponse("/learn/drill?error=no_round", status_code=303)
    if st["finished"] or not st["question"]:
        return RedirectResponse(f"/learn/drill/score?r={quote(r)}", status_code=303)
    return render(request, "ext/community/drill_play.html", pg, rid=r, view=None, st=st, error=DRILL_ERRORS.get(error))


@router.post("/drill/start", include_in_schema=False)
def start(request: Request, mode: str = Form("random"), c: str = Form("")):
    raw, dev, new = cc.device(request)
    try:
        rid = drill.start(dev, "challenge" if c else mode, _lang(request), c)
        url = f"/drill/play?r={quote(rid)}"
    except drill.DrillError as e:
        url = f"/learn/drill/score?r={quote(e.extra['round'])}" if e.key == "daily_done" else f"/learn/drill?error={e.key}"
    return cc.keep_device(RedirectResponse(url, status_code=303), raw, new)


@router.post("/drill/answer", include_in_schema=False)
async def answer(request: Request):
    form = await request.form()
    rid, qid = str(form.get("r", ""))[:40], str(form.get("qid", ""))[:8]
    raw, dev, new = cc.device(request)
    q = content.question(qid)
    given = form.getlist("w") if q and q["type"] == "tap_words" else str(form.get("a", ""))
    try:
        drill.answer(rid, dev, qid, given, _lang(request), tz(request))
        url = f"/drill/play?r={quote(rid)}&done={qid}"
    except drill.DrillError as e:
        url = f"/drill/play?r={quote(rid)}&error={e.key}" if e.key == "invalid" else f"/learn/drill?error={e.key}"
    return cc.keep_device(RedirectResponse(url, status_code=303), raw, new)


@router.get("/learn/drill/score", response_class=HTMLResponse, include_in_schema=False)
def score(request: Request, r: str = ""):
    lang = _lang(request)
    _, dev, _ = cc.device(request)
    res = drill.score(r, dev, lang) if r else None
    pg = _pg("learn/drill/score", "Scam Drill: score", [*LEARN, ["Scam Drill", "/learn/drill"], ["Score", None]])
    if not res:
        return render(request, "ext/community/drill_score.html", pg, res=None, status_code=404 if r else 200, me=None, link="", share="")
    link = f"{cc.origin(request)}/drill/play?c={res['code']}" if res["code"] else ""
    share = cc.whatsapp(({"en": "I scored {s} out of {t} in the Satyapan Scam Drill. Can you beat me? ", "hi": "मैंने सत्यापन स्कैम ड्रिल में {t} में से {s} अंक पाए। क्या आप मुझसे ज़्यादा ला सकते हैं? "}[lang]
                          ).format(s=res["score"], t=res["total"]) + link) if link else ""
    return render(request, "ext/community/drill_score.html", pg, res=res, me=progress.summary(dev), link=link, share=share, lessons=content.lessons())


@router.post("/drill/challenge", include_in_schema=False)
def challenge(request: Request, r: str = Form("")):
    raw, dev, new = cc.device(request)
    try:
        drill.make_challenge(r, dev)
        url = f"/learn/drill/score?r={quote(r)}#challenge"
    except drill.DrillError as e:
        url = f"/learn/drill?error={e.key}"
    return cc.keep_device(RedirectResponse(url, status_code=303), raw, new)


# ---- me ---------------------------------------------------------------------------------------------------
@router.get("/me", response_class=HTMLResponse, include_in_schema=False)
def me_page(request: Request, handle_error: str = "", saved: str = "", recovered: str = ""):
    _, dev, _ = cc.device(request)
    return render(request, "ext/community/me.html", _pg("me", "My progress", [["My progress", None]]), me=progress.summary(dev), lessons=content.lessons(),
                  handle_error=HANDLE_ERRORS.get(handle_error), saved=saved, recovered=recovered, board=progress.leaderboard(dev, 3))


@router.post("/me/handle", include_in_schema=False)
def set_handle(request: Request, handle: str = Form("", max_length=60), website: str = Form("")):
    raw, dev, new = cc.device(request)
    if website:
        return cc.keep_device(RedirectResponse("/me", status_code=303), raw, new)
    err = progress.set_handle(dev, handle)
    return cc.keep_device(RedirectResponse(f"/me?handle_error={err}" if err else "/me?saved=handle", status_code=303), raw, new)


@router.post("/me/recovery", response_class=HTMLResponse, include_in_schema=False)
def make_code(request: Request):
    """The only moment a recovery code exists in readable form: this response. Only its hash is stored."""
    raw, dev, new = cc.device(request)
    if new:                                    # no device cookie yet: there is nothing to attach a code to
        return cc.keep_device(RedirectResponse("/me", status_code=303), raw, new)
    code = progress.new_recovery_code(dev)
    resp = render(request, "ext/community/recovery_code.html", _pg("me", "Recovery code", [["My progress", "/me"], ["Recovery code", None]]), code=code)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@router.get("/me/recover", response_class=HTMLResponse, include_in_schema=False)
def recover_form(request: Request, error: str = ""):
    return render(request, "ext/community/recover.html", _pg("me/recover", "Use a recovery code", [["My progress", "/me"], ["Recover", None]]), error=error)


@router.post("/me/recover", include_in_schema=False)
def recover(request: Request, code: str = Form("", max_length=60)):
    raw, dev, new = cc.device(request)
    out = progress.recover(dev, code)
    return cc.keep_device(RedirectResponse("/me?recovered=1" if out == "ok" else f"/me/recover?error={out}", status_code=303), raw, new)


# ---- certificate ------------------------------------------------------------------------------------------
@router.get("/learn/certificate", response_class=HTMLResponse, include_in_schema=False)
def certificate_page(request: Request):
    lang = _lang(request)
    _, dev, _ = cc.device(request)
    cert = drill.issue_certificate(dev)
    me = progress.summary(dev)
    link = f"{cc.origin(request)}/learn/certificate/{quote(cert['token'])}" if cert else ""
    share = cc.whatsapp({"en": "I finished the Satyapan Scam-Aware course. ", "hi": "मैंने सत्यापन का स्कैम-सजग पाठ्यक्रम पूरा किया। "}[lang] + link) if cert else ""
    return render(request, "ext/community/certificate.html", _pg("learn/certificate", "Scam-Aware certificate", [*LEARN, ["Certificate", None]]),
                  cert=cert, me=me, n_lessons=len(content.lessons()), link=link, share=share)


def _cert_png(cert: dict, lang: str, site: str) -> Response:
    when = datetime.fromtimestamp(cert["issued"], progress.IST)
    return Response(cards.certificate(cert["handle"], cert["level"], lang, when, site), media_type="image/png",
                    headers={"Content-Disposition": 'inline; filename="satyapan-scam-aware.png"'})


@router.get("/learn/certificate.png", include_in_schema=False)
def certificate_png(request: Request, lang: str = ""):
    _, dev, _ = cc.device(request)
    cert = drill.issue_certificate(dev)
    if not cert:
        raise HTTPException(404, "not earned yet")
    return _cert_png(cert, lang or _lang(request), cc.origin(request))


@router.get("/learn/certificate/{token}.png", include_in_schema=False)
def certificate_public_png(request: Request, token: str, lang: str = ""):
    cert = drill.public_certificate(token)
    if not cert:
        raise HTTPException(404)
    return _cert_png(cert, lang or _lang(request), cc.origin(request))


@router.get("/learn/certificate/{token}", response_class=HTMLResponse, include_in_schema=False)
def certificate_public(request: Request, token: str):
    cert = drill.public_certificate(token)
    return render(request, "ext/community/certificate_public.html", _pg("learn/certificate", "Scam-Aware certificate", [*LEARN, ["Certificate", None]]),
                  cert=cert, token=token, status_code=200 if cert else 404)


# ---- one lesson (keep last: it matches any single word after /learn/) ----------------------------------------
@router.get("/learn/{slug}", response_class=HTMLResponse, include_in_schema=False)
def lesson_page(request: Request, slug: str, read: str = ""):
    l = content.lesson(slug)
    _, dev, _ = cc.device(request)
    me = progress.summary(dev)
    if not l:
        return render(request, "ext/community/missing.html", _pg("learn/lesson", "Lesson not found", [*LEARN, ["Lesson", None]]), status_code=404)
    order = content.lessons()
    i = order.index(l)
    return render(request, "ext/community/lesson.html", _pg("learn/lesson", "Lesson", [*LEARN, ["Lesson", None]]), l=l, me=me, read=read,
                  prev=order[i - 1] if i else None, nxt=order[i + 1] if i + 1 < len(order) else None, done=bool(me and slug in me["reads"]))


@router.post("/learn/{slug}/read", include_in_schema=False)
def lesson_read(request: Request, slug: str):
    raw, dev, new = cc.device(request)
    try:
        got = progress.mark_read(dev, slug, _day(request))
    except KeyError:
        raise HTTPException(404) from None
    return cc.keep_device(RedirectResponse(f"/learn/{slug}?read={'new' if got['first'] else 'again'}", status_code=303), raw, new)


# ---- JSON API ---------------------------------------------------------------------------------------------
@router.get("/api/v1/learn/lessons")
def api_lessons(request: Request) -> list[dict]:
    lang = _lang(request)
    return [{"slug": l["slug"], "title": l["title"][lang], "summary": l["summary"][lang]} for l in content.lessons()]


@router.get("/api/v1/learn/lessons/{slug}")
def api_lesson(request: Request, slug: str) -> dict:
    l = content.lesson(slug)
    if not l:
        raise HTTPException(404, "no such lesson")
    lang = _lang(request)
    return {"slug": slug, "title": l["title"][lang], "summary": l["summary"][lang], "story": l["story"][lang], "how": l["how"][lang], "flags": l["flags"][lang],
            "do": l["do"][lang], "check": l["check"][lang], "helpline": "1930 · cybercrime.gov.in"}


@router.post("/api/v1/learn/rounds")
def api_start(request: Request, mode: str = Form("random"), c: str = Form("")):
    raw, dev, new = cc.device(request)
    try:
        rid = drill.start(dev, "challenge" if c else mode, _lang(request), c)
    except drill.DrillError as e:
        raise HTTPException(409 if e.key == "daily_done" else 429 if e.key == "limit" else 400, e.key) from None
    return cc.keep_device(JSONResponse(drill.state(rid, dev, _lang(request)) or {}), raw, new)


@router.get("/api/v1/learn/rounds/{rid}")
def api_state(request: Request, rid: str) -> dict:
    _, dev, _ = cc.device(request)
    st = drill.state(rid, dev, _lang(request))
    if not st:
        raise HTTPException(404, "no such round")
    return st


@router.post("/api/v1/learn/rounds/{rid}/answer")
async def api_answer(request: Request, rid: str):
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    raw, dev, new = cc.device(request)
    try:
        out = drill.answer(rid, dev, str(body.get("qid", "")), body.get("answer"), _lang(request), tz(request))
    except drill.DrillError as e:
        raise HTTPException(404 if e.key in ("no_round", "not_in_round") else 400, e.key) from None
    return cc.keep_device(JSONResponse(out), raw, new)


@router.get("/api/v1/learn/leaderboard")
def api_board(request: Request) -> dict:
    _, dev, _ = cc.device(request)
    b = progress.leaderboard(dev, 20)
    return {"since": b["since"], "top": [{k: r[k] for k in ("rank", "handle", "week", "level")} for r in b["top"]]}


@router.get("/api/v1/learn/stats")
def api_stats() -> dict:
    return progress.stats()


@router.get("/api/v1/learn/me")
def api_me(request: Request) -> dict:
    _, dev, _ = cc.device(request)
    s = progress.summary(dev)
    if not s:
        return {"started": False}
    return {"started": True, "handle": s["handle"], "level": s["level"], "streak": s["streak"], "best_streak": s["best_streak"],
            "badges": [b["id"] for b in s["badges"] if b["got"]], "lessons_read": len(s["reads"]), "rounds": s["rounds"]}
