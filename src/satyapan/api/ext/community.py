"""Scam Watch: the community feed, the report form, post pages, "I saw this too", abuse reports and moderator tools."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ...community import posts, store
from ...community.sanitise import MAX_INPUT, sanitise
from ...store import db
from ..routes_review import fmt_ts, who
from ..web import lang_of, render
from . import community_common as cc

router = APIRouter()
HOME = [["Community", "/community"]]


def _lang(request: Request) -> str:
    return lang_of(request)


def _num(v: str, default: int = 1) -> int:
    return int(v) if v.isdigit() and len(v) < 6 else default


@router.get("/community", response_class=HTMLResponse, include_in_schema=False)
def feed(request: Request, kind: str = "", plang: str = "", sort: str = "new", page: str = "1", thanks: str = "", platform: str = "",
         intent: str = ""):
    lang = _lang(request)
    sort = sort if sort in ("week", "talk") else "new"
    data = posts.feed(lang, kind, plang, sort, _num(page), platform=platform, intent=intent)
    return render(request, "ext/community/feed.html", cc.page("community", "Scam Watch", "community", [["Community", None]]), data=data,
                  trending=posts.trending(lang), stats=posts.stats(), kind=kind, plang=plang, sort=sort, thanks=thanks[:10], platform=platform,
                  intent=intent, recent=posts.recent_comments(5), filtered=bool(kind or plang or platform or intent or sort != "new"))


def _case_info(case_id: str, lang: str) -> dict | None:
    """A result the visitor wants to share: what we can safely start the report with. The check's own text was never kept, so the form
    starts from the payee, link and number that were found, and the visitor adds the rest in their own words."""
    c = db.get_case(case_id) if case_id else None
    if not c:
        return None
    lines = [f"Payee: {p['upi']}" for p in c.payees[:2]] + [f"Link: {u}" for u in c.links[:2]] + [f"Number: {n}" for n in c.phones[:1]]
    return {"id": c.case_id, "headline": c.verdicts["hi" if lang == "hi" else "en"].headline, "tier_class": posts.TIER_CLASS.get(c.tier.value, "n"),
            "text": "\n".join(lines), "kind": "link" if c.kind == "link" else "qr" if c.kind == "qr" else "message"}


def _form(request: Request, status: int = 200, error: str = "", values: dict | None = None):
    _, dev, _ = cc.device(request)
    with store.conn() as c:
        n = store.left(c, dev, "post", posts.LIMITS["post"])
    values = values or {}
    return render(request, "ext/community/report.html", cc.page("community/report", "Report a scam", "community", [["Community", "/community"], ["Report", None]]),
                  error=cc.ERRORS.get(error), values=values, left=n, max_len=MAX_INPUT, status_code=status,
                  case=_case_info(values.get("case_id", ""), _lang(request)))


@router.get("/community/report", response_class=HTMLResponse, include_in_schema=False)
def report_form(request: Request, kind: str = "", case: str = "", intent: str = ""):
    info = _case_info(case[:40], _lang(request))
    values = {"kind": kind if kind in posts.KINDS else (info["kind"] if info else ""), "intent": intent if intent in posts.INTENTS else "warn"}
    if info:
        values.update(case_id=info["id"], text=info["text"])
    return _form(request, values=values)


@router.post("/community/report", include_in_schema=False)
def report_submit(request: Request, kind: str = Form(""), text: str = Form("", max_length=4000), place: str = Form("", max_length=200),
                  lang: str = Form("auto"), consent: str = Form(""), website: str = Form(""), platform: str = Form(""), intent: str = Form("warn"),
                  case_id: str = Form("", max_length=40)):
    raw, dev, new = cc.device(request)
    if website.strip():                                       # honeypot: a person never fills this hidden field
        return cc.keep_device(RedirectResponse("/community?thanks=1", status_code=303), raw, new)
    values = {"kind": kind, "text": text, "place": place, "lang": lang, "consent": bool(consent), "platform": platform, "intent": intent, "case_id": case_id}
    try:
        got = posts.submit(text, kind, lang, place, dev, bool(consent), platform, intent, case_id)
    except posts.SubmitError as e:
        return _form(request, 429 if e.key == "rate_limit" else 422, e.key, values)
    url = f"/community/post/{got.post_id}?new=1" + ("&dup=1" if got.already_counted else "")
    return cc.keep_device(RedirectResponse(url, status_code=303), raw, new)


@router.get("/community/post/{post_id}", response_class=HTMLResponse, include_in_schema=False)
def post_page(request: Request, post_id: int, new: str = "", dup: str = "", seen: str = "", flagged: str = "", err: str = "", note: str = "",
              cerr: str = ""):
    lang = _lang(request)
    _, dev, _ = cc.device(request)
    p = posts.get(post_id, lang, dev, staff=bool(who(request)))
    if p is None:
        return render(request, "ext/community/missing.html", cc.page("community/post", "Post not found", "community", [["Community", "/community"], ["Post", None]]),
                      status_code=404)
    link = f"{cc.origin(request)}/community/post/{p['root_id']}"
    head = {"en": "Scam warning from Satyapan: ", "hi": "सत्यापन की चेतावनी: "}[lang]
    body = (p["excerpt"][:140] + ("…" if len(p["excerpt"]) > 140 else ""))
    share = cc.whatsapp(f"{head}{body}\n{link}\n" + {"en": "Check before you pay.", "hi": "पैसे भेजने से पहले जाँचें।"}[lang])
    return render(request, "ext/community/post.html", cc.page("community/post", "Scam report", "community", [["Community", "/community"], ["Scam report", None]]),
                  p=p, share=share, link=link, new=bool(new), dup=bool(dup), seen=seen, flagged=flagged, err=err,
                  talk=posts.comments(p["root_id"], dev, staff=bool(who(request))), note=note[:20], cerror=cc.ERRORS.get(cerr))


@router.post("/community/post/{post_id}/seen", include_in_schema=False)
def seen(request: Request, post_id: int):
    raw, dev, new = cc.device(request)
    out = posts.vote(post_id, dev)
    return cc.keep_device(RedirectResponse(f"/community/post/{post_id}?seen={out}", status_code=303), raw, new)


@router.post("/community/post/{post_id}/abuse", include_in_schema=False)
def abuse(request: Request, post_id: int, reason: str = Form("other")):
    raw, dev, new = cc.device(request)
    out = posts.report_abuse(post_id, dev, reason)
    return cc.keep_device(RedirectResponse(f"/community/post/{post_id}?flagged={out}", status_code=303), raw, new)


@router.post("/community/post/{post_id}/delete", include_in_schema=False)
def delete(request: Request, post_id: int):
    raw, dev, new = cc.device(request)
    ok = posts.delete_own(post_id, dev)
    return cc.keep_device(RedirectResponse("/community?thanks=deleted" if ok else f"/community/post/{post_id}?err=delete", status_code=303), raw, new)


# ---- discussion ---------------------------------------------------------------------------------------------
@router.post("/community/post/{post_id}/comment", include_in_schema=False)
def comment(request: Request, post_id: int, body: str = Form("", max_length=2000), kind: str = Form("opinion"), platform: str = Form(""),
            website: str = Form("")):
    raw, dev, new = cc.device(request)
    if website.strip():                                       # honeypot
        return cc.keep_device(RedirectResponse(f"/community/post/{post_id}", status_code=303), raw, new)
    try:
        got = posts.add_comment(post_id, dev, body, kind, platform)
        url = f"/community/post/{got['post']}?note=comment_{got['status']}#comments"
    except posts.SubmitError as e:
        url = f"/community/post/{post_id}?cerr={e.key}#comments"
    return cc.keep_device(RedirectResponse(url, status_code=303), raw, new)


@router.post("/community/comment/{comment_id}/helpful", include_in_schema=False)
def comment_helpful(request: Request, comment_id: int, post: int = Form(0)):
    raw, dev, new = cc.device(request)
    out = posts.mark_helpful(comment_id, dev)
    return cc.keep_device(RedirectResponse(f"/community/post/{post}?note=helpful_{out}#c{comment_id}", status_code=303), raw, new)


@router.post("/community/comment/{comment_id}/abuse", include_in_schema=False)
def comment_abuse(request: Request, comment_id: int, post: int = Form(0), reason: str = Form("other")):
    raw, dev, new = cc.device(request)
    out = posts.report_comment(comment_id, dev, reason)
    return cc.keep_device(RedirectResponse(f"/community/post/{post}?note=creport_{out}#comments", status_code=303), raw, new)


@router.post("/community/comment/{comment_id}/delete", include_in_schema=False)
def comment_delete(request: Request, comment_id: int, post: int = Form(0)):
    raw, dev, new = cc.device(request)
    pid = posts.delete_comment_own(comment_id, dev)
    return cc.keep_device(RedirectResponse(f"/community/post/{pid or post}?note={'cdeleted' if pid else 'cnodelete'}#comments", status_code=303), raw, new)


# ---- moderators ---------------------------------------------------------------------------------------------
@router.get("/community/moderate", response_class=HTMLResponse, include_in_schema=False)
def moderate_page(request: Request, done: str = ""):
    me = who(request)
    if not me:
        return RedirectResponse("/console", status_code=303)
    return render(request, "ext/community/moderate.html", cc.page("community/moderate", "Moderate Scam Watch", "community", [["Community", "/community"], ["Moderate", None]]),
                  q=posts.moderation_queue(), trail=posts.audit_trail(), stats=posts.stats(), me=me, fmt_ts=fmt_ts, done=done)


@router.post("/community/moderate/comment/{comment_id}/{action}", include_in_schema=False)
def moderate_comment_do(request: Request, comment_id: int, action: str):
    me = who(request)
    if not me:
        return RedirectResponse("/console", status_code=303)
    if action not in ("approve", "reject", "remove", "dismiss"):
        raise HTTPException(404)
    ok = posts.moderate_comment(comment_id, action, me)
    return RedirectResponse(f"/community/moderate?done={action if ok else 'none'}", status_code=303)


@router.post("/community/moderate/{post_id}/{action}", include_in_schema=False)
def moderate_do(request: Request, post_id: int, action: str):
    me = who(request)
    if not me:
        return RedirectResponse("/console", status_code=303)
    if action not in ("approve", "reject", "remove", "dismiss"):
        raise HTTPException(404)
    ok = posts.moderate(post_id, action, me)
    return RedirectResponse(f"/community/moderate?done={action if ok else 'none'}", status_code=303)


# ---- JSON API -----------------------------------------------------------------------------------------------
def _public(p: dict) -> dict:
    keep = ("id", "created", "kind", "lang", "excerpt", "tier", "tier_label", "reasons", "entity", "entity_kind", "place", "sightings", "weekly",
            "platform", "intent", "comments", "from_check")
    return {k: p[k] for k in keep if k in p}


@router.get("/api/v1/community/posts")
def api_posts(request: Request, kind: str = "", plang: str = "", sort: str = "new", page: int = 1, platform: str = "", intent: str = "") -> dict:
    d = posts.feed(_lang(request), kind, plang, sort if sort in ("week", "talk") else "new", max(1, min(page, 10000)), platform=platform, intent=intent)
    return {**d, "posts": [_public(p) for p in d["posts"]]}


@router.get("/api/v1/community/posts/{post_id}")
def api_post(request: Request, post_id: int) -> dict:
    p = posts.get(post_id, _lang(request))
    if p is None:
        raise HTTPException(404, "no such post")
    return _public(p)


@router.post("/api/v1/community/posts/{post_id}/seen")
def api_seen(request: Request, post_id: int):
    raw, dev, new = cc.device(request)
    out = posts.vote(post_id, dev)
    if out == "missing":
        raise HTTPException(404, "no such post")
    p = posts.get(post_id, _lang(request), dev)
    return cc.keep_device(JSONResponse({"result": out, "sightings": p["sightings"] if p else 0}), raw, new)


@router.get("/api/v1/community/trending")
def api_trending(request: Request) -> list[dict]:
    return posts.trending(_lang(request))


@router.get("/api/v1/community/stats")
def api_stats() -> dict:
    s = posts.stats()
    return {k: s[k] for k in ("posts", "sightings", "sightings_week", "comments")}


@router.post("/api/v1/community/preview")
def api_preview(text: str = Form("", max_length=4000)) -> dict:
    """What would be saved for this text. Nothing is stored; the text is not kept after the reply."""
    s = sanitise(text)
    return {"excerpt": s.excerpt, "masked": s.masked, "clean": s.clean}


@router.get("/api/v1/community/posts/{post_id}/comments")
def api_comments(post_id: int) -> list[dict]:
    if posts.get(post_id, "en") is None:
        raise HTTPException(404, "no such post")
    keep = ("id", "created", "kind", "platform", "body", "name", "helpful")
    return [{k: x[k] for k in keep} for x in posts.comments(post_id) if x["status"] == "approved"]
