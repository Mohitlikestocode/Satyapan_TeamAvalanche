"""Share cards and posters: warning-card builder (/warn), post and lesson cards, printable A4 posters."""
from __future__ import annotations


from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from ...community import cards, content, posts
from ..web import lang_of, render
from . import community_common as cc

router = APIRouter()


def _png(data: bytes, name: str) -> Response:
    return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=300", "Content-Disposition": f'inline; filename="{name}"'})


def _lang(request: Request, lang: str = "") -> str:
    return lang if lang in ("en", "hi") else lang_of(request)


@router.get("/warn", response_class=HTMLResponse, include_in_schema=False)
def warn(request: Request, type: str = "", post: str = "", lang: str = ""):
    lg = _lang(request, lang)
    lessons = content.lessons()
    post_id = int(post) if post.isdigit() and len(post) < 9 else None
    chosen_post = posts.get(post_id, lg) if post_id else None
    if chosen_post and chosen_post["status"] != "approved":
        chosen_post = None
    slug = type if content.lesson(type) else ""
    if not slug and not chosen_post:
        slug = lessons[0]["slug"]
    recent = posts.feed(lg, size=8)["posts"]
    qs = f"post={chosen_post['root_id']}&lang={lg}" if chosen_post else f"type={slug}&lang={lg}"
    site = cc.origin(request)
    text = (chosen_post["excerpt"][:120] if chosen_post else content.lesson(slug)["title"][lg])
    head = {"en": "Scam warning from Satyapan: ", "hi": "सत्यापन की चेतावनी: "}[lg]
    page_url = f"{site}/community/post/{chosen_post['root_id']}" if chosen_post else f"{site}/learn/{slug}"
    share = cc.whatsapp(f"{head}{text}\n{page_url}\n" + {"en": "Check before you pay.", "hi": "पैसे भेजने से पहले जाँचें।"}[lg])
    return render(request, "ext/community/warn.html", cc.page("warn", "Warning card", "learn", [["Learn", "/learn"], ["Warning card", None]]), lessons=lessons, recent=recent,
                  slug=slug, chosen_post=chosen_post, lg=lg, qs=qs, share=share, page_url=page_url)


@router.get("/warn/card.png", include_in_schema=False)
def warn_png(request: Request, type: str = "", post: str = "", lang: str = ""):
    lg = _lang(request, lang)
    site = cc.origin(request)
    if post.isdigit() and len(post) < 9:
        p = posts.get(int(post), lg)
        if not p or p["status"] != "approved":
            raise HTTPException(404, "no such public report")
        return _png(cards.post_card(p, lg, site), f"satyapan-warning-{post}.png")
    png = cards.lesson_card(type, lg, site)
    if not png:
        raise HTTPException(404, "no such scam type")
    return _png(png, f"satyapan-warning-{type}.png")


@router.get("/community/post/{post_id}/card.png", include_in_schema=False)
def post_card(request: Request, post_id: int, lang: str = ""):
    return warn_png(request, post=str(post_id), lang=lang)


@router.get("/learn/cards/{slug}.png", include_in_schema=False)
def lesson_card(request: Request, slug: str, lang: str = ""):
    return warn_png(request, type=slug, lang=lang)


@router.get("/learn/posters", response_class=HTMLResponse, include_in_schema=False)
def posters(request: Request):
    return render(request, "ext/community/posters.html", cc.page("learn/posters", "Posters to print", "learn", [["Learn", "/learn"], ["Posters", None]], extra_js=[]),
                  lessons=content.lessons(), site=cc.origin(request).replace("https://", "").replace("http://", ""))


@router.get("/learn/posters/{name}.pdf", include_in_schema=False)
def poster_pdf(request: Request, name: str, lang: str = ""):
    lg = _lang(request, lang)
    if name != "all" and not content.lesson(name):
        raise HTTPException(404)
    data = cards.poster_pdf(lg, cc.origin(request), None if name == "all" else name)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="satyapan-posters-{name}-{lg}.pdf"'})
