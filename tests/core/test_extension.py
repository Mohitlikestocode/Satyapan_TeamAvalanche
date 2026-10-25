import json
from pathlib import Path

EXT = Path(__file__).resolve().parents[2] / "extension"


def test_manifest_is_valid_v3_with_no_host_permissions():
    m = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert m["manifest_version"] == 3 and m["background"]["service_worker"] == "background.js"
    assert "host_permissions" not in m and "<all_urls>" not in json.dumps(m)       # it never reads the pages you visit
    assert set(m["permissions"]) <= {"contextMenus", "storage"}
    for f in [m["background"]["service_worker"], m["action"]["default_popup"], *m["icons"].values()]:
        assert (EXT / f).is_file(), f


def test_check_page_accepts_text_from_the_extension_fragment():
    js = (EXT.parent / "web" / "static" / "site.js").read_text(encoding="utf-8")
    assert "#t=" in js and "autorun" in js and "history.replaceState" in js
    assert "#t=" in (EXT / "background.js").read_text(encoding="utf-8")
