"""The extension points that let three people build in parallel without touching the same files."""
import sys
import textwrap

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from satyapan.contracts.models import Layer, LayerResult, Signal, Strength
from satyapan.plugins import REGISTRY, Registry, include_ext_routers, load_plugins
from satyapan.reasons import render
from satyapan.service import analyse_text


def make_pkg(tmp_path, name, files):
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    for fname, body in files.items():
        (pkg / fname).write_text(textwrap.dedent(body), encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    return name


def test_plugins_are_discovered_and_register_nav_and_footer(tmp_path):
    pkg = make_pkg(tmp_path, "fakeplug", {
        "a.py": "def setup(r):\n    r.add_nav(35, 'community', '/community', 'Community', 'समुदाय')\n    r.add_footer('Services', 'Scam Watch', '/community/watch')\n",
        "_private.py": "raise RuntimeError('underscore modules are skipped')\n",
        "nosetup.py": "X = 1\n",
    })
    reg = Registry()
    assert load_plugins(pkg, reg) == ["a"]
    core = [("home", "/", "Home", "x"), ("check", "/check", "Check now", "x"), ("dashboard", "/dashboard", "My checks", "x"), ("tools", "/tools", "Is this real?", "x")]
    keys = [row[0] for row in reg.nav(core)]
    assert keys == ["home", "check", "dashboard", "community", "tools"]     # order 35 sits between My checks (30) and Is this real? (40)
    assert reg.footer_extra("Services") == [("Scam Watch", "/community/watch")]


def test_ext_routers_are_mounted_before_core_pages_so_they_can_override(tmp_path):
    pkg = make_pkg(tmp_path, "fakeext", {"r.py": """
        from fastapi import APIRouter
        router = APIRouter()
        @router.get('/learn')
        def learn():
            return {'overridden': True}
        @router.get('/community/ping')
        def ping():
            return {'ok': True}
    """})
    from satyapan.api import routes_pages
    app = FastAPI()
    assert include_ext_routers(app, pkg) == ["r"]
    app.include_router(routes_pages.router)
    c = TestClient(app)
    assert c.get("/learn").json() == {"overridden": True}
    assert c.get("/community/ping").json() == {"ok": True}
    assert c.get("/learn/drill").status_code == 200        # other design pages still served


def test_text_hook_adds_a_layer_and_a_label_and_a_broken_hook_is_ignored(monkeypatch):
    def good(text, found):
        if "needle" not in text:
            return None
        return LayerResult(layer=Layer.L4, signals=[Signal(layer=Layer.L4, code="OFFER_URGENCY", strength=Strength.WEAK_SUSPICIOUS),
                                                    Signal(layer=Layer.L4, code="OFFER_OFFPLATFORM", strength=Strength.WEAK_SUSPICIOUS)],
                           internal={"label_key": "t_hook"})

    def broken(text, found):
        raise RuntimeError("boom")

    monkeypatch.setattr(REGISTRY, "text_hooks", [broken, good])
    monkeypatch.setitem(REGISTRY.layer_labels, "t_hook", ("Test hook", "टेस्ट"))
    res = analyse_text("a needle and nothing else", use_registry=False)
    assert "OFFER_URGENCY" in res.verdicts["en"].reason_codes and "t_hook" in res.layers_run     # two different weak signs are enough to flag
    assert "t_hook" not in analyse_text("plain words", use_registry=False).layers_run


def test_listeners_receive_events_and_a_failing_listener_does_not_break_emit(monkeypatch):
    seen = []
    reg = Registry()
    reg.on("check", lambda p: (_ for _ in ()).throw(RuntimeError("x")))
    reg.on("check", seen.append)
    reg.emit("check", {"a": 1})
    assert seen == [{"a": 1}]


def test_a_handler_owns_a_check_kind(monkeypatch):
    from satyapan.service import analyse_text as base

    def voice(data, topic, case_id):
        return base("Guaranteed 30% a month, pay alpha@ybl", kind="voice", case_id=case_id, use_registry=False)

    monkeypatch.setitem(REGISTRY.handlers, "voice", voice)
    c = TestClient(__import__("satyapan.api.app", fromlist=["app"]).app)
    r = c.post("/api/v1/check", data={"kind": "voice"}, files={"file": ("a.ogg", b"x")}).json()
    assert r["mode"] == "engine" and r["tier"] in ("SUSPICIOUS", "HIGH_RISK")


def test_check_events_are_emitted_with_a_flag_for_internal_traffic(monkeypatch):
    got = []
    monkeypatch.setitem(REGISTRY.listeners, "check", [got.append])
    c = TestClient(__import__("satyapan.api.app", fromlist=["app"]).app)
    c.post("/api/v1/check", data={"kind": "message", "text": "hello there"})
    c.cookies.set("sp_internal", "1")
    c.post("/api/v1/check", data={"kind": "message", "text": "hello again", "channel": "telegram"})
    assert [e["internal"] for e in got] == [False, True] and got[1]["channel"] == "telegram" and got[0]["tier"] == "NO_RED_FLAGS"


def test_ext_reason_codes_merge_and_cannot_redefine_core_codes(tmp_path, monkeypatch):
    ext = tmp_path / "ext"
    ext.mkdir()
    (ext / "area.yaml").write_text("codes:\n  AREA_NEW_CODE:\n    layer: L4\n    priority: 30\n    en: 'x'\n    hi: 'y'\n", encoding="utf-8")
    monkeypatch.setattr(render, "_EXT", ext)
    render.catalogue.cache_clear()
    assert "AREA_NEW_CODE" in render.catalogue()["codes"] and render.priority("AREA_NEW_CODE") == 30
    (ext / "bad.yaml").write_text("codes:\n  OFFER_URGENCY:\n    layer: L4\n    priority: 1\n    en: 'x'\n    hi: 'y'\n", encoding="utf-8")
    render.catalogue.cache_clear()
    with pytest.raises(ValueError):
        render.catalogue()
    (ext / "bad.yaml").unlink()
    (ext / "nohindi.yaml").write_text("codes:\n  AREA_ONLY_EN:\n    layer: L4\n    priority: 1\n    en: 'x'\n", encoding="utf-8")
    render.catalogue.cache_clear()
    with pytest.raises(ValueError):
        render.catalogue()
    monkeypatch.undo()
    render.catalogue.cache_clear()


def test_pages_can_load_extra_css_and_js_and_global_scripts(monkeypatch):
    from satyapan.api.web import screen
    monkeypatch.setattr(REGISTRY, "global_js", ["/static/js/g.js"])
    app = FastAPI()
    r = APIRouter()

    @r.get("/x")
    def x(request: __import__("fastapi").Request):
        from satyapan.api.web import render as rr
        return rr(request, "wrong_status.html" if False else "home.html", screen("x", "X", "check", [], extra_css=["/static/css/x.css"], extra_js=["/static/js/x.js"]))

    app.include_router(r)
    html = TestClient(app).get("/x").text
    assert '/static/css/x.css' in html and '/static/js/x.js' in html and '/static/js/g.js' in html


def test_tr_picks_language_from_the_cookie_and_pages_get_a_device_cookie():
    from satyapan.api.web import templates
    assert templates.env.from_string("{{ tr('a', 'b') }}").render(lang="hi") == "b"
    assert templates.env.from_string("{{ tr('a', 'b') }}").render(lang="en") == "a"
    c = TestClient(__import__("satyapan.api.app", fromlist=["app"]).app)
    r = c.get("/")
    assert "sp_dev" in r.headers.get("set-cookie", "") and "httponly" in r.headers["set-cookie"].lower()
    assert "sp_dev" not in c.get("/").headers.get("set-cookie", "")        # only the first visit sets it
    assert "sp_dev" not in TestClient(__import__("satyapan.api.app", fromlist=["app"]).app).get("/api/v1/health").headers.get("set-cookie", "")
    hi = TestClient(__import__("satyapan.api.app", fromlist=["app"]).app, cookies={"sp_lang": "hi"}).get("/")
    assert '<html lang="hi"' in hi.text
